"""Checks startup metadata for PyInstaller's frozen application layout."""
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1]))
import desktop

class PackagedStartup(unittest.TestCase):
    def test_frozen_revision_does_not_read_source_files(self):
        with patch.object(sys, 'frozen', True, create=True):
            self.assertEqual(desktop.source_revision(), f'packaged-{desktop.APP_VERSION}')

    def test_smoke_test_succeeds_without_a_console(self):
        class Temp:
            def cleanup(self): pass
        class FakeWorkspace:
            def __init__(self): self.tmp=Temp()
        with patch.object(sys, 'stdout', None), patch.object(sys, 'argv', ['MateriaPrima.exe','--smoke-test']), patch.object(desktop, 'Workspace', FakeWorkspace):
            self.assertIsNone(desktop.main())

if __name__ == '__main__':
    unittest.main()
