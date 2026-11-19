"""Correcciones de la prueba manual del caso 05 (16-11-2026), con respuestas reales guardadas."""
from pathlib import Path
import aislar  # noqa: F401  (antes que los módulos de la aplicación)
import json
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from materia_prima.domain.office import Specification
from materia_prima.application.analysis_service import validate_result, protect_manufacturer_ranges
from materia_prima.infrastructure.evidence_view import page_preview

CASE = ROOT.parent/'PRUEBAS_MANUALES/05_NUEVO_FABRICANTE_Y_PROVEEDOR'


class ReviewCorrections(unittest.TestCase):
    def setUp(self):
        self.spec = Specification((CASE/'WORD_ENTRADA_V1.docx').read_bytes())
        self.fields = self.spec.fields
        self.inci = next(i for i, f in self.fields.items() if f.section == 'ID' and 'INCI' in f.label)
        self.maker = next(i for i, f in self.fields.items() if f.kind == 'manufacturer')

    def parsed(self, *changes):
        return {'changes': list(changes), 'commercial_entities': [], 'notes': []}

    def test_inci_is_never_translated_or_replaced_by_a_grade(self):
        translated = {'id': self.inci, 'value': 'CARBOMERO', 'page': 1, 'evidence': 'INCI Name: CARBOMER'}
        grade = {'id': self.inci, 'value': 'CARBOMER 940', 'page': 3, 'evidence': '产品名称:TC-CARBOMER 340'}
        changes, notes = validate_result(self.parsed(translated, grade), self.fields)
        self.assertFalse([c for c in changes if c['id'] == self.inci])
        self.assertTrue(any('CARBOMERO' in n for n in notes))

    def test_literal_inci_correction_keeps_word_prefix(self):
        field = self.fields[self.inci]
        field.value = ': CARBOMEER'
        change = {'id': self.inci, 'value': 'CARBOMER', 'page': 1, 'evidence': 'INCI Name: CARBOMER'}
        changes, _ = validate_result(self.parsed(change), self.fields)
        self.assertEqual([c['value'] for c in changes if c['id'] == self.inci], [': CARBOMER'])

    def test_odor_is_not_inferred_from_absence(self):
        target = next(i for i, f in self.fields.items() if f.kind == 'range_add' and 'Olor' in f.label)
        change = {'id': target, 'value': 'Fabricante: GUANGZHOU TINCI | Sin olor detectable', 'page': 1,
                  'evidence': 'no se especifica olor explícito, se deduce ausencia por falta de mención.'}
        self.assertEqual(protect_manufacturer_ranges(self.fields, [change], [])[0], [])

    def test_range_add_trailing_separator_is_removed(self):
        target = next(i for i, f in self.fields.items() if f.kind == 'range_add' and 'Color' in f.label)
        change = {'id': target, 'value': 'Fabricante: Jiujiang Tinci | Blanco |', 'page': 3, 'evidence': 'Fluffy, white powder'}
        changes, _ = validate_result(self.parsed(change), self.fields)
        self.assertEqual(next(c['value'] for c in changes if c['id'] == target), 'Fabricante: Jiujiang Tinci | Blanco')

    def test_commercial_block_with_blank_and_wrapped_lines_is_kept(self):
        value = ('Fabricante: Guangzhou Tinci Materials Technology Co., Ltd\n\nNombre Comercial: TC-CARBOMER 340\n'
                 'Almacenamiento: Lugar fresco, seco\ny ventilado\nTiempo de Vida útil: 24 meses')
        change = {'id': self.maker, 'value': value, 'page': 1,
                  'evidence': 'TC-CARBOMER 340 Storage: Keep in cool, dry, ventilated place. Shelf Life: 24 months.'}
        changes, _ = validate_result(self.parsed(change), self.fields)
        block = next(c['value'] for c in changes if c['id'] == self.maker)
        self.assertIn('Almacenamiento: Lugar fresco, seco y ventilado', block)
        self.assertNotIn('\n\n', block)

    def test_cited_page_is_rendered_with_highlight(self):
        pdf = CASE/'PDF_ORIGINALES'/'MSDS_CARBOMERO 340_XIAN RONGZHI INDUSTRY&TRADE CO_261022_115629.pdf'
        result = page_preview(pdf, 1, 'INCI Name: CARBOMER', 'CARBOMER')
        self.assertTrue(result['found'])
        self.assertEqual(result['method'], 'texto')
        self.assertTrue(result['image'].startswith('data:image/jpeg;base64,'))
        with self.assertRaises(ValueError):
            page_preview(pdf, 99, 'x')

    def test_ui_merges_blocks_of_one_manufacturer_and_resolves_range_numbers(self):
        script = r'''
const G=require(process.argv[1]);
const f={kind:'manufacturer',proposals:[
 {value:'Fabricante: Guangzhou Tinci Materials Technology Co., Ltd\nProveedor: Guangzhou Tinci Materials Technology Co., Ltd',pdf:'MSDS.pdf',page:1},
 {value:'Fabricante: GUANGZHOU TINCI MATERIALS TECHNOLOGY CO., LTD.\nNombre Comercial: TC-CARBOMER 340',pdf:'TDS.pdf',page:1},
 {value:'Fabricante: Jiujiang Tinci Materials Technology Co., Ltd.',pdf:'COA.pdf',page:3}]};
const groups=G.group(f);
const rows=G.mergeManufacturer(groups[0]);
const r=G.rangeResult('(1) Polvo esponjoso',[1],{guangzhoutincimaterialstechnologycoltd:2},'Fabricante: Guangzhou Tinci Materials Technology Co., Ltd | Polvo blanco esponjoso');
console.log(JSON.stringify({groups:groups.length,conflicts:rows.filter(r=>r.options.length>1).length,block:G.composeBlock(rows),range:r.text}));
'''
        out = subprocess.run(['node', '-e', script, str(ROOT/'ui'/'proposal-groups.js')],
                             capture_output=True, text=True, check=True).stdout
        result = json.loads(out)
        self.assertEqual(result['groups'], 2)
        self.assertEqual(result['conflicts'], 0)
        self.assertEqual(result['block'], 'Fabricante: Guangzhou Tinci Materials Technology Co., Ltd\n'
                         'Proveedor: Guangzhou Tinci Materials Technology Co., Ltd\nNombre Comercial: TC-CARBOMER 340')
        self.assertEqual(result['range'], '(1) Polvo esponjoso\n(2) Polvo blanco esponjoso')

    def range_add(self, label):
        return next(i for i, f in self.fields.items() if f.kind == 'range_add' and label in f.label)

    def test_untranslated_description_and_placeholders_are_not_proposed(self):
        maker = 'Fabricante: GUANGZHOU TINCI MATERIALS TECHNOLOGY CO., LTD. | '
        changes = [
            {'id': self.range_add('Aspecto'), 'value': maker+'Fluffy, white powder', 'page': 1, 'evidence': 'Fluffy, white powder'},
            {'id': self.range_add('Color'), 'value': maker+'white', 'page': 1, 'evidence': 'Fluffy, white powder'},
            {'id': self.range_add('Olor'), 'value': maker+'N.D.', 'page': 1, 'evidence': 'Odor: N.D.'},
            {'id': self.range_add('Color'), 'value': maker+'Blanco', 'page': 1, 'evidence': 'Fluffy, white powder'},
        ]
        kept, notes = validate_result(self.parsed(*changes), self.fields)
        self.assertEqual([c['value'] for c in kept if c['id'] != self.maker], [maker+'Blanco'])
        self.assertEqual(len([n for n in notes if 'Se omitió' in n]), 3)

    def test_commercial_block_drops_empty_data_and_translates_shelf_life(self):
        value = ('Fabricante: Guangzhou Tinci Materials Technology Co., Ltd\nNombre Comercial: TC-CARBOMER 340\n'
                 'Tiempo de Vida útil: N.A\nAlmacenamiento: N.D.')
        other = 'Fabricante: Jiujiang Tinci\nNombre Comercial: TC-CARBOMER 340 | Tiempo de Vida útil: 24 months'
        kept, _ = validate_result(self.parsed(
            {'id': self.maker, 'value': value, 'page': 1, 'evidence': 'x'},
            {'id': self.maker, 'value': other, 'page': 3, 'evidence': 'Shelf Life: 24 months'}), self.fields)
        blocks = [c['value'] for c in kept if c['id'] == self.maker]
        self.assertEqual(blocks[0], 'Fabricante: Guangzhou Tinci Materials Technology Co., Ltd\nNombre Comercial: TC-CARBOMER 340')
        self.assertEqual(blocks[1], 'Fabricante: Jiujiang Tinci\nNombre Comercial: TC-CARBOMER 340\nTiempo de Vida útil: 24 meses')

    def test_odor_note_written_as_evidence_is_rejected(self):
        change = {'id': self.range_add('Olor'), 'value': 'Fabricante: X | Inodoro', 'page': 1,
                  'evidence': 'No se describe el olor en el documento.'}
        self.assertEqual(protect_manufacturer_ranges(self.fields, [change], [])[0], [])

    def test_glued_label_copied_and_derived_commercial_data(self):
        """Respuestas reales del 16-11-2026: «LTD.Proveedor:», vida útil de COREL y fecha de vencimiento."""
        cases = [
            ('Fabricante: GUANGZHOU TINCI MATERIALS TECHNOLOGY CO., LTD.Proveedor:\nNombre Comercial: TC-CARBOMER 340\n'
             'Tiempo de Vida útil: 24 meses\nAlmacenamiento: Mantener en lugar fresco, seco, ventilado y sin luz.',
             'GUANGZHOU TINCI MATERIALS TECHNOLOGY CO., LTD.\nShelf Life: 24 months.\nStorage: Keep in cool, dry, ventilated and lightless place.',
             'Fabricante: GUANGZHOU TINCI MATERIALS TECHNOLOGY CO., LTD.\nNombre Comercial: TC-CARBOMER 340\n'
             'Tiempo de Vida útil: 24 meses\nAlmacenamiento: Mantener en lugar fresco, seco, ventilado y sin luz.'),
            ('Fabricante: Jiujiang Tinci Materials Technology Co., Ltd.\nNombre Comercial: TC-CARBOMER 340\n'
             'Tiempo de Vida útil: 2 años\nAlmacenamiento: Almacenar en un recipiente bien cerrado',
             'Manufacturer: Jiujiang Tinci Materials Technology Co., Ltd.\nProduct Name: TC-CARBOMER 340\nExpiration Date: 2027年11月03日',
             'Fabricante: Jiujiang Tinci Materials Technology Co., Ltd.\nNombre Comercial: TC-CARBOMER 340'),
            ('Fabricante: Guangzhou Tinci Materials Technology Co., Ltd\nTiempo de Vida útil: 3 años',
             'Manufacture/Supplier: Guangzhou Tinci Materials Technology Co., Ltd',
             'Fabricante: Guangzhou Tinci Materials Technology Co., Ltd'),
        ]
        for value, evidence, expected in cases:
            kept, notes = validate_result(self.parsed({'id': self.maker, 'value': value, 'page': 1, 'evidence': evidence}), self.fields)
            self.assertEqual([c['value'] for c in kept if c['id'] == self.maker], [expected])

    def test_schema_echo_from_free_models_is_unwrapped(self):
        """Respuesta real de nemotron-3.5-super-vl (17-11-2026): datos dentro de una copia del esquema."""
        aspect = self.range_add('Aspecto')
        echoed = {'type': 'object', 'properties': {'changes': {'type': 'array', 'items': [
            {'id': aspect, 'value': 'Fabricante: Guangzhou Tinci Materials Technology Co., Ltd. | Polvo esponjoso, blanco',
             'page': 3, 'evidence': '9.1 Physical State: Fluffy, white powder'}]}}}
        kept, notes = validate_result(echoed, self.fields)
        self.assertEqual([c['id'] for c in kept], [aspect])


if __name__ == '__main__':
    unittest.main()
