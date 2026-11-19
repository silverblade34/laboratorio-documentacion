"""Vista de revisión en el documento, roles comerciales (contexto peruano) y guardado de claves."""
from datetime import date
from pathlib import Path
from unittest import mock
import aislar  # noqa: F401  (antes que los módulos de la aplicación)
import sys, tempfile, unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import materia_prima.application.analysis_service as analysis_service
from materia_prima.application.analysis_service import (complete_explicit_relations, entity_origin, fix_commercial_block,
                              reconcile_commercial_roles, validate_result)
from materia_prima.presentation.desktop import Workspace
from materia_prima.application.analysis_service import Catalog
from materia_prima.domain.office import Specification

CASE = Path(__file__).resolve().parents[2]/'PRUEBAS_MANUALES/05_NUEVO_FABRICANTE_Y_PROVEEDOR'
G = 'Guangzhou Tinci Materials Technology Co., Ltd'
GOICOCHEA = {'name': 'QUÍMICOS GOICOCHEA', 'country': 'Perú', 'where': 'logo', 'page': 1,
             'same_product': False, 'evidence': 'QUÍMICOS GOICOCHEA', 'pdf': 'COA.pdf'}


class CommercialRoles(unittest.TestCase):
    def setUp(self):
        self.spec = Specification((CASE/'WORD_ENTRADA_V1.docx').read_bytes())
        self.f = self.spec.fields
        self.maker = next(i for i, f in self.f.items() if f.kind == 'manufacturer')

    def test_origin_heuristics(self):
        self.assertEqual(entity_origin(G), 'foreign')
        self.assertEqual(entity_origin('NEO DETER DEL PERU S.A.C.'), 'peru')
        self.assertEqual(entity_origin('Químicos Goicochea SAC'), 'peru')
        self.assertEqual(entity_origin('TC-CARBOMER 340'), '')

    def test_foreign_supplier_is_replaced_by_peruvian_logo(self):
        notes = []
        block = fix_commercial_block(f'Fabricante: {G}\nProveedor: {G}\nNombre Comercial: TC-CARBOMER 340', [GOICOCHEA], notes)
        self.assertEqual(block, f'Fabricante: {G}\nProveedor: QUÍMICOS GOICOCHEA\nNombre Comercial: TC-CARBOMER 340')
        self.assertTrue(any('Confírmalo' in n for n in notes))

    def test_swapped_roles_and_company_as_trade_name(self):
        block = fix_commercial_block('Fabricante: NEO DETER DEL PERU S.A.C.\nProveedor: Jiujiang Tinci Co., Ltd.\n'
                                     'Nombre Comercial: Jiujiang Tinci Co., Ltd.', [], [])
        self.assertEqual(block, 'Fabricante: Jiujiang Tinci Co., Ltd.\nProveedor: NEO DETER DEL PERU S.A.C.')

    def test_model_answer_uses_local_companies(self):
        parsed = {'changes': [{'id': self.maker, 'value': f'Fabricante: {G}\nNombre Comercial: TC-CARBOMER 340',
                               'page': 1, 'evidence': f'Manufacture/Supplier: {G}'}],
                  'commercial_entities': [{'manufacturer': G, 'supplier': G, 'page': 1, 'evidence': G}],
                  'local_companies': [GOICOCHEA], 'notes': []}
        kept, _ = validate_result(parsed, self.f)
        self.assertEqual([c['value'] for c in kept if c['id'] == self.maker],
                         [f'Fabricante: {G}\nProveedor: QUÍMICOS GOICOCHEA\nNombre Comercial: TC-CARBOMER 340'])

    def test_manufacture_supplier_header_is_only_the_manufacturer(self):
        pdf = CASE/'PDF_ORIGINALES'/'MSDS_CARBOMERO 340_XIAN RONGZHI INDUSTRY&TRADE CO_261022_115629.pdf'
        changes, notes = complete_explicit_relations(pdf, self.f, [], [])
        values = [c['value'] for c in changes if c['id'] == self.maker]
        self.assertEqual(len(values), 1)
        self.assertNotIn('Proveedor', values[0])

    def test_reconcile_uses_google_classification_across_documents(self):
        proposals = {self.maker: [{'id': self.maker, 'value': 'Fabricante: COREL TRADING\nProveedor: ACME CHEMICALS',
                                   'page': 1, 'evidence': 'x', 'pdf': 'SDS.pdf'}]}
        answer = ({'coreltrading': {'nombre': 'COREL TRADING', 'pais': 'Perú', 'peruana': True, 'rol': 'proveedor',
                                    'confianza': 'alta', 'motivo': 'RUC 20…', 'fuente': 'Google'},
                   'acmechemicals': {'nombre': 'ACME CHEMICALS', 'pais': 'India', 'peruana': False, 'rol': 'fabricante',
                                     'confianza': 'alta', 'motivo': 'Planta en Gujarat', 'fuente': 'Google'}}, 'Google')
        with mock.patch.object(analysis_service, 'classify_companies', return_value=answer) as classify:
            result, notes = reconcile_commercial_roles(self.f, proposals, [], ['k'], (), 'gemini-2.5-flash')
        classify.assert_called_once()
        entry = result[self.maker][0]
        self.assertEqual(entry['value'], 'Fabricante: ACME CHEMICALS\nProveedor: COREL TRADING')
        self.assertEqual([r['fuente'] for r in entry['roles']], ['Google', 'Google'])
        self.assertTrue(notes)

    def test_reconcile_without_service_falls_back_to_rules(self):
        proposals = {self.maker: [{'id': self.maker, 'value': f'Fabricante: {G}\nProveedor: {G}', 'page': 1, 'evidence': 'x'}]}
        with mock.patch.object(analysis_service, 'classify_companies', side_effect=analysis_service.ServiceError('sin red')):
            result, notes = reconcile_commercial_roles(self.f, proposals, [GOICOCHEA], [], (), 'gemini-2.5-flash')
        self.assertEqual(result[self.maker][0]['value'], f'Fabricante: {G}\nProveedor: QUÍMICOS GOICOCHEA')
        self.assertTrue(any('reglas habituales' in n for n in notes))


class ReviewView(unittest.TestCase):
    def workspace(self, tmp):
        w = Workspace(); w.catalog = Catalog(Path(tmp))
        w.word = CASE/'WORD_ENTRADA_V1.docx'; w.spec = Specification(w.word.read_bytes()); w.pdfs = []
        return w

    def test_credentials_are_saved(self):
        """En Windows fallaba con «Path.open() got an unexpected keyword argument 'opener'»."""
        with tempfile.TemporaryDirectory() as tmp:
            w = self.workspace(tmp)
            w.action('credentials', {'gemini': 'clave-uno'})
            w.action('credentials', {'gemini': 'clave-dos\nclave-uno'})
            saved = (Path(tmp)/'.gemini-key').read_text(encoding='utf-8').split()
            self.assertEqual(saved, ['clave-uno', 'clave-dos'])
            w.tmp.cleanup()

    def test_draft_preview_colors_each_change_and_skips_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = self.workspace(tmp)
            fields = w.spec.fields
            maker = next(i for i, f in fields.items() if f.kind == 'manufacturer')
            aspect = next(i for i, f in fields.items() if f.kind == 'range_add' and 'Aspecto' in f.label)
            color = next(i for i, f in fields.items() if f.kind == 'range_add' and 'Color' in f.label)
            draft = {maker: f'Fabricante: {G}\nProveedor: QUÍMICOS GOICOCHEA',
                     aspect: f'Fabricante: {G} | Polvo esponjoso, blanco\nFabricante: Otro Co., Ltd | Polvo',
                     color: f'Fabricante: {G} | Blanco'}
            w.action('reject', {'id': color})
            merged, skipped = w.merged_changes(draft)
            self.assertEqual(set(merged), {maker, aspect})
            self.assertEqual(merged[aspect], f'Fabricante: {G} | Polvo esponjoso, blanco')
            self.assertEqual(skipped, [])
            html = w.action('preview', {'fecha': '2026-11-17', 'mode': 'content', 'draft': draft,
                                        'colors': {maker: 3, aspect: 5, color: 6}})['html']
            self.assertIn(f'chg-3" data-change="{maker}"', html)
            self.assertIn(f'chg-5" data-change="{aspect}"', html)
            self.assertNotIn(f'data-change="{color}"', html)
            self.assertIn('QUÍMICOS GOICOCHEA', html)
            # Volver a incluir y aprobar limpia el estado «quitado».
            w.action('restore', {'id': color})
            self.assertNotIn(color, w.rejected)
            self.assertEqual(w.approved, {})
            w.tmp.cleanup()

    def test_export_order_still_writes_new_manufacturer_before_ranges(self):
        spec = Specification((CASE/'WORD_ENTRADA_V1.docx').read_bytes())
        maker = next(i for i, f in spec.fields.items() if f.kind == 'manufacturer')
        aspect = next(i for i, f in spec.fields.items() if f.kind == 'range_add' and 'Aspecto' in f.label)
        approved = {aspect: f'Fabricante: {G} | Polvo esponjoso, blanco', maker: f'Fabricante: {G}'}
        owners = Specification(spec.data).apply_changes(approved)
        self.assertEqual(set(owners.values()), {maker, aspect})
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'r.docx'
            Specification(spec.data).export(out, approved, date(2026, 11, 17))
            cell = {f.manufacturer_number: f.value for f in Specification(out.read_bytes()).fields.values()
                    if f.kind == 'range' and 'Aspecto' in f.label}
            self.assertEqual(cell[2], 'Polvo esponjoso, blanco')


    def test_new_block_copies_format_of_existing_block(self):
        """Los bloques nuevos usan la tabla, el interlineado y el «: valor» del fabricante vigente."""
        from materia_prima.domain.office import W, manufacturer_blocks, word_text
        spec = Specification((CASE/'WORD_ENTRADA_V1.docx').read_bytes())
        maker = next(i for i, f in spec.fields.items() if f.kind == 'manufacturer')
        spec.apply_changes({maker: f'Fabricante: {G}\nProveedor: QUÍMICOS GOICOCHEA S.A.C.\n'
                                   'Parámetro adicional: Densidad | 19.5–23.5 | Del fabricante'})
        blocks = manufacturer_blocks(spec.parts['word/document.xml'].find(W+'body'))
        self.assertEqual([(b['number'], b['name']) for b in blocks], [(1, 'COREL PHARMA CHEM'), (2, G)])
        old, new = blocks[0]['table'], blocks[1]['table']
        first = new.findall(W+'tr')[0]
        self.assertEqual([word_text(c).strip() for c in first.findall(W+'tc')], ['2)', 'Fabricante', ': ' + G, ''])
        spacing = lambda t: {s.get(W+'line') for s in t.iter(W+'spacing')}
        self.assertTrue(spacing(new) <= spacing(old) and '360' in spacing(new))
        self.assertEqual(new.find(W+'tblGrid').findall(W+'gridCol')[0].get(W+'w'), old.find(W+'tblGrid').findall(W+'gridCol')[0].get(W+'w'))


if __name__ == '__main__':
    unittest.main()
