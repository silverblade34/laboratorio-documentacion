"""Segunda revisión de IA (respuesta simulada) y orden fabricante → rango."""
from pathlib import Path
from unittest import mock
import sys, tempfile, unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analysis_service
from analysis_service import validate_result, verify_proposals
from desktop import Workspace
from analysis_service import Catalog
from office import Specification

CASE = Path(__file__).resolve().parents[2]/'PRUEBAS_MANUALES/05_NUEVO_FABRICANTE_Y_PROVEEDOR'
G = 'Fabricante: Guangzhou Tinci Materials Technology Co., Ltd'
J = 'Fabricante: Jiujiang Tinci Materials Technology Co., Ltd.'


class SecondReview(unittest.TestCase):
    def setUp(self):
        self.spec = Specification((CASE/'WORD_ENTRADA_V1.docx').read_bytes())
        self.f = self.spec.fields
        self.range = lambda label: next(i for i, f in self.f.items() if f.kind == 'range_add' and label in f.label)
        self.maker = next(i for i, f in self.f.items() if f.kind == 'manufacturer')

    def test_range_with_manufacturer_name_is_rejected(self):
        change = {'id': self.range('Olor'), 'value': G + ' | Guangzhou Tinci Materials Technology Co., Ltd', 'page': 1, 'evidence': 'Odor: slight'}
        kept, notes = validate_result({'changes': [change], 'commercial_entities': [], 'notes': []}, self.f)
        self.assertFalse([c for c in kept if c['id'] == change['id']])
        self.assertTrue(any('nombre de un fabricante' in n for n in notes))

    def test_verifier_rejects_corrects_and_keeps(self):
        proposals = {self.range('Aspecto'): [
            {'id': self.range('Aspecto'), 'value': G + ' | Powder fluffy', 'page': 1, 'evidence': 'Fluffy, white powder', 'pdf': 'TDS.pdf'},
            {'id': self.range('Aspecto'), 'value': J + ' | Polvo esponjoso, blanco', 'page': 3, 'evidence': 'Fluffy, white powder', 'pdf': 'COA.pdf'}],
            self.range('Olor'): [{'id': self.range('Olor'), 'value': J + ' | Micro-ácido', 'page': 3, 'evidence': '微酸性粉末 micro-acidic powder', 'pdf': 'COA.pdf'}]}
        answer = [{'n': 1, 'veredicto': 'corregir', 'valor': 'Polvo esponjoso, blanco', 'motivo': 'Traducción.'},
                  {'n': 2, 'veredicto': 'ok', 'valor': 'Polvo esponjoso, blanco', 'motivo': ''},
                  {'n': 3, 'veredicto': 'rechazar', 'valor': 'Micro-ácido', 'motivo': 'La acidez no describe el olor.'}]
        with mock.patch.object(analysis_service, 'ask_verifier', return_value=answer):
            result, notes = verify_proposals(self.f, proposals, ['k'], '', 'gemini-2.5-flash')
        aspect = result[self.range('Aspecto')]
        self.assertEqual([p['value'] for p in aspect], [G + ' | Polvo esponjoso, blanco', J + ' | Polvo esponjoso, blanco'])
        self.assertEqual(aspect[0]['original'], G + ' | Powder fluffy')
        self.assertTrue(all(p['verified'] for p in aspect))
        self.assertNotIn(self.range('Olor'), result)
        self.assertEqual(len(notes), 2)

    def test_two_new_manufacturers_then_both_ranges(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = Workspace(); w.catalog = Catalog(Path(tmp))
            w.word = CASE/'WORD_ENTRADA_V1.docx'; w.spec = self.spec; w.pdfs = []
            target = self.range('Aspecto')
            both = G + ' | Polvo esponjoso, blanco\n' + J + ' | Polvo esponjoso, blanco, micro-ácido'
            with self.assertRaises(ValueError):
                w.action('approve', {'id': target, 'value': both})
            w.action('approve', {'id': self.maker, 'value': G + '\nProveedor: Guangzhou Tinci Materials Technology Co., Ltd\n\n' + J})
            w.action('approve', {'id': target, 'value': both})
            self.assertEqual(w.manufacturer_numbers()['jiujiangtincimaterialstechnologycoltd'], 3)
            out = Path(tmp)/'r.docx'
            Specification(self.spec.data).export(out, w.approved, __import__('datetime').date(2026, 11, 16))
            result = Specification(out.read_bytes())
            cell = {f.manufacturer_number: f.value for f in result.fields.values() if f.kind == 'range' and 'Aspecto' in f.label}
            self.assertEqual(cell, {1: 'Polvo esponjoso', 2: 'Polvo esponjoso, blanco', 3: 'Polvo esponjoso, blanco, micro-ácido'})
            self.assertEqual([g['number'] for g in result.manufacturers], [1, 2, 3])


if __name__ == '__main__':
    unittest.main()
