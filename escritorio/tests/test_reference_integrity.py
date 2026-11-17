"""Regressions found during manual desktop acceptance on 2026-11-16."""
from pathlib import Path
from datetime import date
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from office import Specification
from analysis_service import protect_manufacturer_ranges

CASE=Path(__file__).resolve().parents[2]/'PRUEBAS_MANUALES/05_NUEVO_FABRICANTE_Y_PROVEEDOR/WORD_ENTRADA_V1.docx'
class ReferenceIntegrity(unittest.TestCase):
 def setUp(self):self.s=Specification(CASE.read_bytes())
 def test_new_manufacturer_cannot_add_parameters_to_existing_one(self):
  target=next(i for i,f in self.s.fields.items() if f.kind=='additional')
  change={'id':target,'value':'Impurezas | ≤ 0,25 % | Del fabricante','evidence':'Jiujiang Tinci','source_manufacturers':['Jiujiang Tinci Materials Technology Co., Ltd.']}
  changes,notes=protect_manufacturer_ranges(self.s.fields,[change],[])
  self.assertEqual(changes,[]);self.assertTrue(notes)
 def test_unknown_attribute_is_not_a_proposed_range(self):
  target=next(i for i,f in self.s.fields.items() if f.kind=='range_add' and 'Olor' in f.label)
  change={'id':target,'value':'Fabricante: Jiujiang Tinci | Sin olor (no deducible)','source_manufacturers':['Jiujiang Tinci']}
  changes,_=protect_manufacturer_ranges(self.s.fields,[change],[])
  self.assertEqual(changes,[])
 def test_assumed_attribute_without_entity_is_not_a_range(self):
  target=next(i for i,f in self.s.fields.items() if f.kind=='range_add' and 'Olor' in f.label)
  change={'id':target,'value':'Sin olor (no explícito, se asume neutro)'}
  self.assertEqual(protect_manufacturer_ranges(self.s.fields,[change],[])[0],[])
 def test_two_new_ranges_preserve_the_existing_manufacturer(self):
  maker=next(i for i,f in self.s.fields.items() if f.kind=='manufacturer')
  target=next(i for i,f in self.s.fields.items() if f.kind=='range_add' and 'Aspecto' in f.label)
  approved={maker:'Fabricante: Guangzhou Tinci\nProveedor: Guangzhou Tinci\n\nFabricante: Jiujiang Tinci',target:'Fabricante: Guangzhou Tinci | Polvo blanco\nFabricante: Jiujiang Tinci | Polvo esponjoso'}
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'result.docx';self.s.export(out,approved,date(2026,11,16));r=Specification(out.read_bytes())
  self.assertEqual([g['number'] for g in r.manufacturers],[1,2,3]);self.assertEqual(r.manufacturers[0]['name'],'COREL PHARMA CHEM')
  values={f.manufacturer_number:f.value for f in r.fields.values() if f.kind=='range' and 'Aspecto' in f.label}
  self.assertEqual(values,{1:'Polvo esponjoso',2:'Polvo blanco',3:'Polvo esponjoso'})
if __name__=='__main__':unittest.main()
