"""Historial local: un análisis se reabre con propuestas y aprobaciones, sin consultar a la IA."""
from pathlib import Path
import sys, tempfile, unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop import Workspace
from analysis_service import Catalog
from history import History
from office import Specification

CASE = Path(__file__).resolve().parents[2]/'PRUEBAS_MANUALES/05_NUEVO_FABRICANTE_Y_PROVEEDOR'


class HistoryTest(unittest.TestCase):
    def test_saved_analysis_reopens_without_new_queries(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = Workspace(); w.catalog = Catalog(Path(tmp))
            w.word = CASE/'WORD_ENTRADA_V1.docx'; w.spec = Specification(w.word.read_bytes())
            w.pdfs = sorted((CASE/'PDF_ORIGINALES').glob('*.pdf'))
            field = next(i for i, f in w.spec.fields.items() if f.kind == 'manufacturer')
            w.proposals = {field: [{'value': 'Fabricante: Jiujiang Tinci', 'page': 3, 'evidence': 'x', 'pdf': 'COA.pdf'}]}
            w.successes = {w.pdfs[0]: True}
            w.history_id = History.new_id()
            w.action('approve', {'id': field, 'value': 'Fabricante: Jiujiang Tinci'})
            entry = w.history_id
            items = w.history.entries()
            self.assertEqual((items[0]['sap'], items[0]['aprobados'], len(items[0]['pdfs'])), (w.spec.sap, 1, 3))

            other = Workspace(); other.catalog = Catalog(Path(tmp))
            other.action('history_open', {'id': entry})
            state = other.snapshot()
            self.assertEqual(state['history_id'], entry)
            self.assertEqual(state['approved_count'], 1)
            self.assertEqual(len(state['pdfs']), 3)
            self.assertEqual([p.name for p in other.successes], [w.pdfs[0].name])
            self.assertEqual(state['manufacturer_numbers'].get('jiujiangtinci'), 2)
            other.action('history_delete', {'id': entry})
            self.assertEqual(other.history.entries(), [])
            with self.assertRaises(ValueError):
                other.history.folder('../fuera')


if __name__ == '__main__':
    unittest.main()
