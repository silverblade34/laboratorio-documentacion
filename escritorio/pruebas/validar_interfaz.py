"""Start a clean desktop session for manual UI acceptance, with isolated settings/catalog.
The existing configured API credentials are read normally, never copied into the report.
"""
from pathlib import Path
from threading import Thread
import json
import secrets
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from desktop import Workspace,serve,APP_VERSION
from analysis_service import Catalog
import webview

report=ROOT.parent/'VALIDACION_INTERFAZ'/'2026-11-16'
report.mkdir(parents=True,exist_ok=True)
workspace=Workspace()
workspace.catalog=Catalog(report/'estado')
workspace.settings_path=report/'estado'/'preferencias.json'
workspace.settings=json.loads(workspace.settings_path.read_text()) if workspace.settings_path.exists() else {k:v for k,v in workspace.settings.items() if k in {'modelo','renderizador'}}
server=serve(workspace,secrets.token_urlsafe(32))
Thread(target=server.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{server.server_port}'
(report/'sesion.json').write_text(json.dumps({'url':url,'version':APP_VERSION,'proposito':'Pruebas manuales desde interfaz; sin respuestas precargadas','carpeta_salida':str(report/'EXPORTACIONES')},ensure_ascii=False,indent=2))
print(url,flush=True)
try:
 workspace.window=webview.create_window(f'Materia {APP_VERSION} · Pruebas de aceptación 16 noviembre',url,width=1440,height=950,min_size=(980,700))
 webview.start()
finally:
 server.shutdown();workspace.tmp.cleanup()
