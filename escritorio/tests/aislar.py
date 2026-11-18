"""Las pruebas nunca escriben en la carpeta real de la aplicación (registro, claves, salud, catálogo)."""
import atexit
import os
import tempfile

_folder = tempfile.TemporaryDirectory(prefix='materia-pruebas-')
os.environ['LOCALAPPDATA'] = _folder.name
atexit.register(_folder.cleanup)
