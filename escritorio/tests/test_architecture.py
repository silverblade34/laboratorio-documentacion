"""Comprueba límites de dominio y recursos de distribución."""
import ast
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from materia_prima.paths import RESOURCE_ROOT


class ArchitectureTests(unittest.TestCase):
    def test_domain_does_not_import_outer_layers(self):
        forbidden = ('materia_prima.application', 'materia_prima.presentation',
                     'materia_prima.infrastructure')
        for path in (ROOT / 'materia_prima/domain').glob('*.py'):
            with self.subTest(module=path.name):
                tree = ast.parse(path.read_text(encoding='utf-8'))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        self.assertFalse((node.module or '').startswith(forbidden))
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            self.assertFalse(alias.name.startswith(forbidden))

    def test_required_resources_resolve_from_source(self):
        for name in ('ui/index.html', 'tecnicas.json', 'AS-REG-018.xlsx',
                     'ejemplo/entrada_fabricante_modificado.docx'):
            with self.subTest(resource=name):
                self.assertTrue((RESOURCE_ROOT / name).is_file())


if __name__ == '__main__':
    unittest.main()
