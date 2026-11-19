"""Aislamiento, persistencia y uso de decisiones humanas en análisis posteriores."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
import sys
import sqlite3
import json
import aislar  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from materia_prima.infrastructure.learning import LearningMemory
from materia_prima.presentation.desktop import Workspace
from materia_prima.application.analysis_service import Catalog


def field(maker='Fabricante Uno'):
    return SimpleNamespace(section='A', label='Densidad', kind='range',
                           manufacturer_name=maker, value='1,0–1,1')


class LearningTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.memory = LearningMemory(self.temp.name)
        self.spec = SimpleNamespace(sap='123', fields={'a': field()})

    def record(self, final='1,02–1,08', proposals=None, export='expediente-1'):
        return self.memory.record_export(self.spec, {'a': final}, proposals or {},
                                         export, '1.4.0', 'automático')

    def test_preserves_original_proposal_and_manual_correction(self):
        proposals = {'a': [{'value': '1,04', 'pdf': 'fuente.pdf', 'evidence': 'densidad'}]}
        self.assertEqual(self.record(proposals=proposals), 1)
        from contextlib import closing
        with closing(sqlite3.connect(self.memory.path)) as db:
            data = json.loads(db.execute('SELECT datos FROM decision_v1').fetchone()[0])
        self.assertEqual(data['decision'], 'corregida')
        self.assertEqual(data['propuestas'], proposals['a'])
        self.assertEqual(data['final'], '1,02–1,08')
        self.assertEqual(data['antes'], '1,0–1,1')

    def test_persists_and_deduplicates_same_export(self):
        self.record()
        self.assertEqual(self.record(), 0)
        reopened = LearningMemory(self.temp.name)
        self.assertEqual(len(reopened.examples('123', self.spec.fields)), 1)

    def test_does_not_reuse_other_material_or_manufacturer(self):
        self.record()
        self.assertEqual(self.memory.examples('456', self.spec.fields), [])
        self.assertEqual(self.memory.examples('123', {'b': field('Otro fabricante')}), [])
        self.assertEqual(self.memory.examples('', self.spec.fields), [])

    def test_latest_decision_supersedes_prior_value_with_changed_row_id(self):
        self.record()
        self.record(final='1,03–1,07', export='expediente-2')
        examples = self.memory.examples('123', {'new_id': field()})
        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0]['final'], '1,03–1,07')

    def test_acceptance_and_manual_decision_are_distinct(self):
        self.record(final='1,04', proposals={'a': [{'value': '1,04'}]})
        self.assertEqual(self.memory.examples('123', self.spec.fields)[0]['decision'], 'aceptada')
        self.record(export='expediente-2')
        self.assertEqual(self.memory.examples('123', self.spec.fields)[0]['decision'], 'manual')

    def test_preference_is_persistent_and_boolean(self):
        workspace = Workspace()
        self.addCleanup(workspace.tmp.cleanup)
        workspace.catalog = Catalog(Path(self.temp.name))
        workspace.settings_path = Path(self.temp.name) / 'preferencias.json'
        workspace.save_settings({'aprendizaje': False})
        self.assertFalse(json.loads(workspace.settings_path.read_text())['aprendizaje'])
        with self.assertRaises(ValueError):
            workspace.save_settings({'aprendizaje': 'false'})

    def test_exported_correction_reaches_next_analysis_and_can_be_disabled(self):
        from unittest.mock import patch
        from materia_prima.domain.office import Specification
        from materia_prima.presentation import desktop
        workspace = Workspace()
        self.addCleanup(workspace.tmp.cleanup)
        workspace.catalog = Catalog(Path(self.temp.name))
        workspace.settings_path = Path(self.temp.name) / 'preferencias.json'
        workspace.settings = {'salida': self.temp.name, 'solicitante': 'Prueba',
                              'area': 'Laboratorio', 'modelo': 'gemini-test'}
        workspace.word = Path(__file__).resolve().parents[1] / 'ejemplo/entrada_fabricante_modificado.docx'
        workspace.spec = Specification(workspace.word.read_bytes())
        workspace.pdfs = [workspace.word.with_name('FT_PURE_SEDUCTION.pdf')]
        field_id = next(i for i, f in workspace.spec.fields.items() if f.kind == 'manufacturer')
        final = 'Fabricante: Fabricante Validado'
        workspace.proposals = {field_id: [{'value': 'Fabricante: Valor Incorrecto', 'pdf': workspace.pdfs[0].name}]}
        workspace.approve({'id': field_id, 'value': final})
        self.assertEqual(workspace.learning.examples(workspace.spec.sap, workspace.spec.fields), [])
        with patch.object(Specification, 'export', autospec=True) as export_word:
            export_word.side_effect = lambda spec, output, *args, **kwargs: output.write_bytes(b'test')
            workspace.export({'fecha': '2026-11-19'})
        self.assertEqual(workspace.learning.examples(workspace.spec.sap, workspace.spec.fields)[0]['final'], final)

        class InlineThread:
            def __init__(self, target, **kwargs): self.target = target
            def start(self): self.target()

        with patch.object(desktop, 'Thread', InlineThread), \
             patch.object(desktop, 'provider_keys', return_value=(('test-key',), (), ())), \
             patch.object(desktop, 'inspect_document', return_value=([], [], 'test', [])) as inspect, \
             patch.object(workspace, 'second_review'), patch.object(workspace, 'reconcile_roles'):
            workspace.start_analysis()
            self.assertEqual(inspect.call_args.args[3]['aprendizajes_usuario'][0]['final'], final)
            workspace.settings['aprendizaje'] = False
            workspace.start_analysis()
            self.assertIsInstance(inspect.call_args.args[3], list)
        with patch.object(LearningMemory, 'record_export') as record:
            workspace.approve({'id': field_id, 'value': 'Fabricante: Otro Valor'})
            with patch.object(Specification, 'export', autospec=True) as export_word:
                export_word.side_effect = lambda spec, output, *args, **kwargs: output.write_bytes(b'test')
                workspace.export({'fecha': '2026-11-19'})
            record.assert_not_called()
