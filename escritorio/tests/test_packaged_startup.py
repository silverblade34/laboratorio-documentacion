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

if __name__ == '__main__':
    unittest.main()
