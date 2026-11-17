"""Desktop shell and local HTML interface for document review."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Lock, Thread
from urllib.parse import urlparse
import hashlib
import base64
import json
import mimetypes
import os
import re
import secrets
import shutil
import subprocess
import sys
import webbrowser

from analysis_service import Catalog, inspect_document, provider_keys, verify_proposals, word_bytes, norm
from office import ChangeForm, Specification, manufacturer_key, word_text
from techniques import technique_context, validate_section_a
from history import History
import activity_log as alog

ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = 'gemini-2.5-flash'
APP_VERSION = '1.3.0'

def source_revision():
    names = ['desktop.py','office.py','analysis_service.py','preview.py','evidence_view.py','history.py','activity_log.py','connectivity.py','ui/app.js','ui/proposal-groups.js','ui/index.html','ui/style.css']
    return hashlib.sha256(b''.join((ROOT/name).read_bytes() for name in names)).hexdigest()[:10]



class Workspace:
    def __init__(self):
        self.build_id = source_revision()
        self.catalog = Catalog()
        self.settings_path = self.catalog.path.with_name('preferencias.json')
        alog.setup(self.catalog.path.parent)
        alog.log('info', 'Aplicación', f'Materia {APP_VERSION} iniciada', alog.environment())
        try:
            self.settings = json.loads(self.settings_path.read_text())
        except (OSError, ValueError):
            self.settings = {}
        self.tmp = TemporaryDirectory(prefix='materia-prima-')
        self.lock = Lock()
        self.stop = Event()
        self.window = None
        self.busy = False
        self.word = None
        self.spec = None
        self.pdfs = []
        self.approved = {}
        self.proposals = {}
        self.successes = {}
        self.notes = []
        self.sections = ['A', 'B', 'C', 'ID']
        self.progress = {'finished': 0, 'total': 0, 'message': ''}
        self.last_export = ''
        self.demo = False
        self.preview_cache = {}
        self.preview_lock = Lock()
        self.evidence_cache = {}
        self.history_id = None
        self.exported = ''

    @property
    def history(self):
        return History(self.catalog.path.parent / 'historial')

    def persist(self):
        """Guarda el análisis actual en el historial local (sin nuevas consultas a la IA)."""
        with self.lock:
            if not self.history_id or not self.word or not self.spec:
                return
            entry, word, pdfs = self.history_id, self.word, self.pdfs[:]
            record = {'sap': self.spec.sap, 'version': self.spec.version, 'sections': self.sections[:],
                      'proposals': {k: v[:] for k, v in self.proposals.items()}, 'notes': self.notes[:],
                      'approved': dict(self.approved), 'successes': [p.name for p in self.successes],
                      'exportado': self.exported}
        try:
            self.history.save(entry, word, pdfs, record)
        except Exception as exc:
            with self.lock:
                self.notes.append({'type': 'error', 'file': 'Historial', 'text': f'No se pudo guardar el análisis en el historial: {exc}'})

    def open_history(self, entry_id):
        data, word, pdfs = self.history.load(entry_id)
        spec = Specification(word_bytes(word))
        with self.lock:
            self.word, self.spec, self.pdfs = word, spec, pdfs
            self.demo = False
            self.reset_review()
            self.sections = [s for s in data.get('sections', []) if s in {'A', 'B', 'C', 'ID'}] or ['A', 'B', 'C', 'ID']
            self.proposals = {k: v for k, v in data.get('proposals', {}).items() if k in spec.fields}
            self.approved = {k: v for k, v in data.get('approved', {}).items() if k in spec.fields}
            self.notes = data.get('notes', [])
            done = set(data.get('successes', []))
            self.successes = {p: True for p in pdfs if p.name in done}
            self.history_id, self.exported = entry_id, data.get('exportado', '')
            self.last_export = self.exported

    def snapshot(self):
        with self.lock:
            fields = [] if self.spec is None else [
                {'id': i, 'section': f.section, 'label': f.label, 'before': f.value,
                 'kind': f.kind, 'manufacturer_number': f.manufacturer_number, 'manufacturer_name':f.manufacturer_name, 'approved': self.approved.get(i),
                 'proposals': self.proposals.get(i, []),
                 'cell': word_text(f.node).strip() if f.kind in {'range', 'range_add'} else None}
                for i, f in self.spec.fields.items() if f.section in self.sections]
            keys, groq, openrouter = provider_keys()
            return {
                'app_version':APP_VERSION, 'build_id':self.build_id, 'restart_required':self.build_id != source_revision(),
                'word': self.word.name if self.word else '',
                'sap': self.spec.sap if self.spec else '',
                'version': self.spec.version if self.spec else None,
                'manufacturers': [{'number':g['number'],'name':g['name']} for g in self.spec.manufacturers] if self.spec else [],
                'pdfs': [p.name for p in self.pdfs], 'fields': fields,
                'settings': {k: v for k, v in self.settings.items() if k in
                             {'salida', 'plantilla', 'solicitante', 'area', 'modelo', 'groq_model', 'openrouter_model', 'renderizador'}},
                'busy': self.busy, 'progress': self.progress.copy(), 'notes': self.notes[:],
                'sections': self.sections[:], 'last_export': self.last_export, 'demo': self.demo,
                'no_keys': not bool(keys or groq or openrouter),
                'keys_count': {'gemini': len(keys), 'groq': len(groq), 'openrouter': len(openrouter)},
                'commercial_attention': bool(self.spec and 'B' in self.sections and self.successes
                    and not self.busy and not any(f.section == 'B' and
                        (self.proposals.get(i) or self.approved.get(i) or
                         (f.value.strip() and norm(f.label.split(' · ')[0]) in {'fabricante','proveedor'}))
                        for i, f in self.spec.fields.items())),
                'approved_count': len(self.approved),
                'manufacturer_numbers': self.manufacturer_numbers(),
                'history_id': self.history_id or '',
            }

    def manufacturer_numbers(self):
        """Número que tendrá cada fabricante en B: vigentes y bloques nuevos ya aprobados."""
        if not self.spec:
            return {}
        numbers = {manufacturer_key(g['name']): g['number'] for g in self.spec.manufacturers}
        for i, value in self.approved.items():
            if self.spec.fields[i].kind == 'manufacturer':
                for name in re.findall(r'(?im)^fabricante\s*:\s*(.+)$', value):
                    numbers.setdefault(manufacturer_key(name), max(numbers.values(), default=0)+1)
        return numbers

    def reset_review(self):
        self.approved.clear()
        self.proposals.clear()
        self.successes.clear()
        self.notes.clear()
        self.progress = {'finished': 0, 'total': 0, 'message': ''}

    def store_file(self, item, suffixes):
        name = Path(item['name']).name
        if Path(name).suffix.lower() not in suffixes:
            raise ValueError('Selecciona un archivo con el formato indicado.')
        raw = base64.b64decode(item['data'], validate=True)
        if len(raw) > 20_000_000:
            raise ValueError('El archivo supera 20 MB.')
        folder = Path(self.tmp.name) / secrets.token_hex(8)
        folder.mkdir()
        path = folder / name
        path.write_bytes(raw)
        return path

    def upload(self, payload):
        if payload['kind'] == 'word':
            path = self.store_file(payload['files'][0], {'.doc', '.docx'})
            spec = Specification(word_bytes(path))
            with self.lock:
                self.spec, self.word = spec, path
                self.pdfs = []
                self.demo = False
                self.reset_review()
                self.history_id, self.exported = None, ''
        elif payload['kind'] == 'template':
            path = self.store_file(payload['files'][0], {'.xlsx'})
            ChangeForm(path.read_bytes())
            permanent = self.catalog.path.with_name('AS-REG-018-personalizada.xlsx')
            shutil.copy2(path, permanent)
            self.save_settings({'plantilla': str(permanent)})
        else:
            paths = [self.store_file(item, {'.pdf'}) for item in payload['files']]
            with self.lock:
                self.pdfs = paths
                self.reset_review()
                self.history_id, self.exported = None, ''

    def load_demo(self):
        sample = ROOT / 'ejemplo' / 'entrada_fabricante_modificado.docx'
        pdf = ROOT / 'ejemplo' / 'FT_PURE_SEDUCTION.pdf'
        spec = Specification(sample.read_bytes())
        with self.lock:
            self.word, self.spec, self.pdfs = sample, spec, [pdf]
            self.sections = ['B']
            self.demo = True
            self.reset_review()
            self.history_id, self.exported = None, ''

    def save_settings(self, payload):
        if payload.get('modelo'):
            import re
            if not re.fullmatch(r'gemini-[a-zA-Z0-9._-]+', payload['modelo']):
                raise ValueError('Indica un modelo Gemini válido.')
        updated = self.settings.copy()
        for key in ('salida', 'plantilla', 'solicitante', 'area', 'modelo', 'renderizador'):
            if key in payload:
                updated[key] = str(payload[key]).strip()
        if payload.get('renderizador') and not Path(payload['renderizador']).is_file():
            raise ValueError('No se encontró el ejecutable de LibreOffice indicado.')
        if payload.get('salida'):
            directory = Path(payload['salida']).expanduser()
            if not directory.is_dir():
                raise ValueError('Selecciona una carpeta existente.')
            with TemporaryDirectory(dir=directory):
                pass
            updated['salida'] = str(directory)
        temp = self.settings_path.with_suffix('.tmp')
        temp.write_text(json.dumps(updated, ensure_ascii=False), encoding='utf-8')
        temp.replace(self.settings_path)
        self.settings = updated

    def choose_folder(self):
        if self.window:
            import webview
            result = self.window.create_file_dialog(webview.FileDialog.FOLDER)
            path = result[0] if result else ''
        elif sys.platform == 'darwin':
            code = 'POSIX path of (choose folder with prompt "Selecciona la carpeta de expedientes")'
            result = subprocess.run(['osascript', '-e', code], capture_output=True, text=True)
            path = result.stdout.strip() if result.returncode == 0 else ''
        else:
            raise ValueError('Escribe la ruta de la carpeta en Configuración.')
        if path:
            self.save_settings({'salida': path})
        return {'path': path}

    def start_analysis(self):
        if not self.spec or not self.pdfs:
            raise ValueError('Carga el Word y al menos un PDF de respaldo.')
        keys, groq, openrouter = provider_keys()
        alog.register_secrets(*keys, *groq, *openrouter)
        if not keys and not groq and not openrouter:
            raise ValueError('Configura las credenciales del servicio en Configuración o utiliza la edición manual.')
        fields = {i: f for i, f in self.spec.fields.items() if f.section in self.sections}
        if not fields:
            raise ValueError('Selecciona al menos una sección.')
        pending = [(i, p) for i, p in enumerate(self.pdfs) if p not in self.successes]
        if not pending:
            self.successes.clear()
            self.proposals.clear()
            pending = list(enumerate(self.pdfs))
            self.history_id = None
        if self.history_id is None:
            self.history_id, self.exported = History.new_id(), ''
        self.stop.clear()
        self.busy = True
        self.notes = [n for n in self.notes if n['type'] == 'success']
        self.progress = {'finished': len(self.successes), 'total': len(self.pdfs),
                         'message': 'Leyendo documentación técnica'}
        sap = self.spec.sap
        context = self.catalog.context(sap)
        model = self.settings.get('modelo') or DEFAULT_MODEL
        openrouter_model = self.settings.get('openrouter_model')
        alog.log('info', 'Análisis', f'Inicio · {len(pending)} PDF pendiente(s) de {len(self.pdfs)} · secciones {", ".join(self.sections)} · {len(fields)} campos',
                 f'SAP {sap} · modelo {model} · {len(keys)} clave(s) Gemini · {len(groq)} clave(s) Groq · {len(openrouter)} clave(s) OpenRouter · historial {self.history_id or "nuevo"}')

        def analyze(index, path):
            if self.stop.is_set():
                return None
            return inspect_document(path, fields, sap, context, keys, groq, model, index, openrouter_keys=openrouter, openrouter_model=openrouter_model)

        def worker():
            try:
                with ThreadPoolExecutor(max_workers=3) as pool:
                    tasks = {pool.submit(analyze, i, path): path for i, path in pending}
                    for task in as_completed(tasks):
                        path = tasks[task]
                        try:
                            outcome = task.result()
                            if outcome:
                                changes, notes, provider = outcome
                                with self.lock:
                                    self.successes[path] = outcome
                                    for change in changes:
                                        self.proposals.setdefault(change['id'], []).append({
                                            **change, 'pdf': path.name, 'provider': provider})
                                    self.notes.append({'type': 'success', 'file': path.name,
                                                       'text': f'{len(changes)} propuestas · {provider}'})
                                    self.notes.extend({'type': 'info', 'file': path.name, 'text': n}
                                                      for n in notes)
                                alog.log('ok', path.name, f'{len(changes)} propuesta(s) aceptadas · {provider}',
                                         '\n'.join(f'[{c["id"]}] {self.spec.fields[c["id"]].label}: {c["value"]}' for c in changes)
                                         + ('\n\nObservaciones:\n' + '\n'.join(notes) if notes else ''))
                        except Exception as exc:
                            alog.exception(path.name, f'El PDF no se pudo analizar: {exc}')
                            with self.lock:
                                self.notes.append({'type': 'error', 'file': path.name, 'text': str(exc)})
                        with self.lock:
                            self.progress['finished'] += 1
                            self.progress['message'] = f'Procesado {path.name}'
                if not self.stop.is_set():
                    self.second_review(fields, keys, groq, model)
            except Exception:
                alog.exception('Análisis', 'Fallo inesperado del proceso de análisis')
                raise
            finally:
                with self.lock:
                    self.busy = False
                    failed = sum(1 for n in self.notes if n['type'] == 'error')
                alog.log('warn' if failed else 'ok', 'Análisis', f'Fin · {len(self.successes)} de {len(self.pdfs)} PDF analizados'
                         + (f' · {failed} con error' if failed else ''))
                self.persist()

        Thread(target=worker, daemon=True).start()

    def second_review(self, fields, keys, groq, model):
        """Segunda revisión de IA de las propuestas consolidadas que aún no se verificaron."""
        with self.lock:
            pending = {k: [p for p in v if 'verified' not in p] for k, v in self.proposals.items()}
            pending = {k: v for k, v in pending.items() if v}
            if not pending:
                return
            self.progress['message'] = 'Segunda revisión: la IA comprueba que cada propuesta tenga sentido'
        try:
            checked, notes = verify_proposals(fields, pending, keys, groq, model)
        except Exception as exc:
            alog.exception('Segunda revisión', f'No se completó: {exc}')
            with self.lock:
                self.notes.append({'type': 'info', 'file': 'Segunda revisión',
                                   'text': f'No se pudo completar la verificación con IA ({exc}). Las propuestas se muestran sin esa revisión; revísalas con especial atención.'})
            return
        with self.lock:
            merged = {}
            for k, v in self.proposals.items():
                kept = [p for p in v if 'verified' in p] + checked.get(k, [])
                if kept:
                    merged[k] = kept
            self.proposals = merged
            verified = sum(len(v) for v in checked.values())
            self.notes.append({'type': 'success', 'file': 'Segunda revisión', 'text': f'{verified} propuesta(s) verificadas por IA'})
            self.notes.extend({'type': 'info', 'file': 'Segunda revisión', 'text': n} for n in notes)

    def approve(self, payload):
        field_id, value = payload['id'], payload['value']
        field = self.spec.fields[field_id]
        if field.section == 'A':
            validate_section_a(field, value)
        if field.kind == 'range_add':
            lines=[line.strip() for line in value.splitlines() if line.strip()]
            if not lines:
                raise ValueError('Indica Fabricante: nombre completo | rango.')
            names=[]
            from office import manufacturer_key
            for line in lines:
                maker, separator, text = line.partition(' | ')
                if not separator or not maker.lower().startswith('fabricante:') or not maker.partition(':')[2].strip() or not text.strip():
                    raise ValueError('Indica una línea por fabricante: Fabricante: nombre completo | rango.')
                names.append(manufacturer_key(maker.partition(':')[2]))
            if len(names)!=len(set(names)):
                raise ValueError('Hay dos rangos del mismo fabricante. Elige uno o combina su redacción antes de aprobar.')
            known = self.manufacturer_numbers()
            missing = [line.partition(' | ')[0].partition(':')[2].strip() for line, key in zip(lines, names) if key not in known]
            if missing:
                raise ValueError('Aprueba primero en B el bloque de ' + ', '.join(missing) + ' («Agregar fabricante y su bloque comercial»); así recibe su número antes de asignarle rangos.')
        else:
            Specification(self.spec.data).fields[field_id].write(value)
        if value.strip() == field.value.strip():
            self.approved.pop(field_id, None)
        else:
            self.approved[field_id] = value

    def export(self, payload):
        self.save_settings(payload)
        folder = self.settings.get('salida')
        if not folder:
            raise ValueError('Selecciona y autoriza una carpeta de salida.')
        if not self.settings.get('solicitante') or not self.settings.get('area'):
            raise ValueError('Completa el solicitante y el área.')
        effective = date.fromisoformat(payload['fecha'])
        if not self.approved:
            raise ValueError('Aprueba al menos un cambio antes de exportar.')
        spec = Specification(self.spec.data)
        label = f'{spec.sap}_V{spec.version + 1}'
        destination = Path(folder) / label
        count = 2
        while destination.exists():
            destination = Path(folder) / f'{label}_{count}'
            count += 1
        with TemporaryDirectory(dir=folder) as temp:
            stage = Path(temp) / label
            stage.mkdir()
            form = Path(self.settings.get('plantilla') or ROOT / 'AS-REG-018.xlsx')
            ChangeForm(form.read_bytes()).export(
                stage / f'SC_{label}.xlsx', spec, self.approved,
                self.settings['solicitante'], self.settings['area'], effective)
            spec.export(stage / f'ET_{label}.docx', self.approved, effective,
                        payload.get('add_history', True), payload.get('history_text'))
            attachments = stage / 'PDF de respaldo'
            attachments.mkdir()
            for i, pdf in enumerate(self.pdfs, 1):
                shutil.copy2(pdf, attachments / f'{i:02}_{pdf.name}')
            record = {'sap': spec.sap, 'version_anterior': spec.version,
                      'version_nueva': spec.version + 1, 'fecha': effective.isoformat(),
                      'solicitante': self.settings['solicitante'], 'area': self.settings['area'],
                      'word_origen': self.word.name,
                      'registrar_revision_historica': payload.get('add_history', True),
                      'revision_historica': payload.get('history_text', self.spec.history_summary(self.approved)),
                      'pdf_sin_analizar': [p.name for p in self.pdfs if p not in self.successes],
                      'cambios': [{'seccion': spec.fields[i].section, 'campo': spec.fields[i].label,
                                  'antes': spec.fields[i].value, 'despues': value,
                                  'evidencias_propuestas': self.proposals.get(i, [])}
                                 for i, value in self.approved.items()]}
            (stage / 'registro_de_cambios.json').write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
            stage.rename(destination)
        entities = []
        for i, field in spec.fields.items():
            if field.section != 'B':
                continue
            value = self.approved.get(i, field.value)
            if field.kind == 'manufacturer':
                lines = [line.partition(':')[::2] for line in value.splitlines()]
            else:
                role = norm(field.label.split(' · ', 1)[0])
                if role not in {'fabricante', 'proveedor'}:
                    continue
                lines = [(role, line) for line in value.split(':', 1)[-1].splitlines()]
            for role, name in lines:
                if norm(role) in {'fabricante', 'proveedor'} and name.strip(' :'):
                    entities.append((norm(role), name.strip(' :')))
        try:
            self.catalog.save(spec.sap, entities)
        except Exception as exc:
            self.notes.append({'type': 'error', 'file': 'Catálogo', 'text': str(exc)})
        self.last_export = self.exported = str(destination)
        self.persist()
        return {'path': str(destination)}

    def open_path(self, path):
        if sys.platform == 'darwin':
            subprocess.Popen(['open', str(path)])
        elif os.name == 'nt':
            os.startfile(str(path))
        else:
            webbrowser.open(Path(path).resolve().as_uri())

    def action(self, action, payload):
        if action == 'logs':
            return {'events': alog.events(int(payload.get('after', 0))), 'file': alog.log_path(), 'busy': self.busy,
                    'progress': self.progress.copy()}
        if action == 'open_log':
            if alog.log_path():
                self.open_path(Path(alog.log_path()).parent)
            return {}
        if self.busy and action not in {'cancel', 'open_pdf', 'connectivity', 'pdf_page'}:
            raise ValueError('Detén el análisis antes de cambiar los documentos.')
        if action == 'connectivity':
            from connectivity import check
            return check(payload.get('force', False))
        if action == 'upload':
            self.upload(payload)
        elif action == 'demo':
            self.load_demo()
        elif action == 'analyze':
            self.start_analysis()
        elif action == 'cancel':
            self.stop.set()
        elif action == 'approve':
            self.approve(payload)
            self.persist()
        elif action == 'discard':
            self.approved.pop(payload['id'], None)
            self.proposals.pop(payload['id'], None)
            self.persist()
        elif action == 'history_list':
            return {'items': self.history.entries(), 'current': self.history_id or ''}
        elif action == 'history_open':
            self.open_history(payload.get('id'))
        elif action == 'history_delete':
            if payload.get('id') == self.history_id:
                self.history_id = None
            self.history.delete(payload.get('id'))
        elif action == 'sections':
            selected = [s for s in payload['sections'] if s in {'A', 'B', 'C', 'ID'}]
            self.sections = selected
            self.history_id = None
            self.successes.clear()
            self.proposals.clear()
            self.approved = {i: v for i, v in self.approved.items()
                             if self.spec.fields[i].section in selected}
        elif action == 'settings':
            self.save_settings(payload)
        elif action == 'folder':
            return self.choose_folder()
        elif action == 'techniques':
            return {'items': technique_context()}
        elif action == 'history':
            if not self.spec:
                raise ValueError('Carga primero el Word vigente.')
            return {'text': self.spec.history_summary(self.approved)}
        elif action == 'preview':
            if not self.spec:
                raise ValueError('Carga primero el Word vigente.')
            effective = date.fromisoformat(payload['fecha'])
            with self.lock:
                preview_spec = Specification(self.spec.data)
                preview_approved = self.approved.copy()
            if payload.get('mode') == 'content':
                return {'html': preview_spec.preview_html(preview_approved, effective,
                            payload.get('add_history', True), payload.get('history_text'))}
            from preview import render_document
            digest = hashlib.sha256(preview_spec.data + json.dumps([preview_approved, payload, self.settings.get('renderizador','')],sort_keys=True).encode()).hexdigest()
            with self.preview_lock:
                if digest not in self.preview_cache:
                    self.preview_cache = {digest:render_document(preview_spec,preview_approved,effective,
                        payload.get('add_history',True),payload.get('history_text'),self.settings.get('renderizador',''))}
                return self.preview_cache[digest]
        elif action == 'export':
            return self.export(payload)
        elif action == 'credentials':
            mapping = {'gemini': '.gemini-key', 'extra': '.gemini-key-extra', 'groq': '.groq-key', 'openrouter': '.openrouter-key'}
            for key, filename in mapping.items():
                value = payload.get(key, '').strip()
                if value:
                    # Se añade al conjunto de claves (una por línea); las existentes se conservan.
                    path = self.catalog.path.with_name(filename)
                    try:
                        current = [l.strip() for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]
                    except OSError:
                        current = []
                    for line in value.splitlines():
                        line = line.strip()
                        if line and line not in current:
                            current.append(line)
                    with path.open('w', opener=lambda p, flags: os.open(p, flags, 0o600)) as file:
                        file.write('\n'.join(current) + '\n')
                    os.chmod(path, 0o600)
            return {'status': 'ok'}
        elif action == 'pdf_page':
            pdf = next((p for p in self.pdfs if p.name == payload.get('name')), None)
            if pdf is None:
                raise ValueError('El PDF ya no está cargado en esta sesión.')
            key = (str(pdf), int(payload.get('page', 1)), payload.get('evidence', ''), payload.get('value', ''))
            with self.preview_lock:
                cached = self.evidence_cache.get(key)
            if cached is None:
                from evidence_view import page_preview
                cached = page_preview(pdf, key[1], key[2], key[3])
                with self.preview_lock:
                    if len(self.evidence_cache) > 24:
                        self.evidence_cache.clear()
                    self.evidence_cache[key] = cached
            return cached
        elif action == 'open_pdf':
            pdf = next(p for p in self.pdfs if p.name == payload['name'])
            self.open_path(pdf)
        elif action == 'open_export':
            if self.last_export:
                self.open_path(self.last_export)
        elif action == 'catalog':
            return {'entities': self.catalog.entries(self.spec.sap) if self.spec else []}
        else:
            raise ValueError('Acción no disponible.')
        return {}


def serve(workspace, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, data, mime='application/json'):
            raw = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def authorized(self):
            return self.headers.get('X-Session') == token

        def do_GET(self):
            path = urlparse(self.path).path
            if path == '/api/state':
                if not self.authorized():
                    return self.respond(403, {'error': 'Sesión no válida.'})
                return self.respond(200, workspace.snapshot())
            if path == '/session.js':
                if self.headers.get('Sec-Fetch-Site') == 'cross-site':
                    return self.respond(403, {'error': 'Origen no válido.'})
                return self.respond(200, f'window.SESSION={json.dumps(token)};'.encode(), 'text/javascript')
            target = (ROOT / 'ui' / ('index.html' if path == '/' else path.lstrip('/'))).resolve()
            if not target.is_relative_to((ROOT / 'ui').resolve()) or not target.is_file():
                return self.respond(404, {'error': 'Archivo no disponible.'})
            self.respond(200, target.read_bytes(), mimetypes.guess_type(target)[0] or 'application/octet-stream')

        def do_POST(self):
            if not self.authorized():
                return self.respond(403, {'error': 'Sesión no válida.'})
            origin = self.headers.get('Origin')
            if origin and origin != f'http://127.0.0.1:{self.server.server_port}':
                return self.respond(403, {'error': 'Origen no válido.'})
            action = '?'
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if size > 100_000_000:
                    raise ValueError('Carga hasta 70 MB de archivos por operación.')
                payload = json.loads(self.rfile.read(size))
                action = self.path.split('/')[-1]
                result = workspace.action(action, payload)
                self.respond(200, result)
            except Exception as exc:
                if action not in {'logs'}:
                    alog.exception('Interfaz', f'La acción «{action}» falló: {exc}')
                self.respond(400, {'error': str(exc)})

    return ThreadingHTTPServer(('127.0.0.1', 0), Handler)


def main():
    workspace = Workspace()
    server = serve(workspace, secrets.token_urlsafe(32))
    Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}'
    print(f'Aplicación disponible en {url}', flush=True)
    try:
        import webview
    except ImportError:
        webbrowser.open(url)
        try:
            Event().wait()
        except KeyboardInterrupt:
            pass
    else:
        workspace.window = webview.create_window(
            f'Materia {APP_VERSION} · Especificaciones técnicas', url, width=1380, height=900, min_size=(980, 700))
        webview.start()
    finally:
        server.shutdown()
        workspace.tmp.cleanup()


if __name__ == '__main__':
    main()
