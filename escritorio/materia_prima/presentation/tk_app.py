from materia_prima.paths import RESOURCE_ROOT
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from queue import Empty, Queue
from tempfile import TemporaryDirectory
from threading import Event, Thread
import os
import json
import shutil
from copy import deepcopy
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from materia_prima.application.analysis_service import Catalog, MODEL, inspect_document, provider_keys, word_bytes
from materia_prima.domain.office import ChangeForm, Specification, norm

FORM = (RESOURCE_ROOT / 'AS-REG-018.xlsx')

SECTIONS = {'A': 'A · Especificación', 'B': 'B · Información adicional',
            'C': 'C · Observaciones', 'ID': 'Identificación'}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Especificaciones de materias primas')
        self.geometry('1050x740')
        self.minsize(860, 650)
        self.catalog = Catalog()
        self.settings_path = self.catalog.path.with_name('preferencias.json')
        try:
            self.settings = json.loads(self.settings_path.read_text())
        except (OSError, ValueError):
            self.settings = {}
        style = ttk.Style(self)
        style.configure('Treeview', rowheight=34)
        style.configure('Treeview.Heading', font=('', 11, 'bold'))
        style.configure('TButton', padding=(10, 6))
        self.results = Queue()
        self.word = self.spec = None
        self.pdfs = ()
        self.suggestions = {}
        self.analysis_successes = {}
        self.discarded = set()
        self.approved = {}
        self.sections = {s: tk.BooleanVar(value=True) for s in SECTIONS}
        self.applicant = tk.StringVar(value=self.settings.get('solicitante', ''))
        self.area = tk.StringVar(value=self.settings.get('area', ''))
        self.output_dir = tk.StringVar(value=self.settings.get('salida', ''))
        self.form_path = tk.StringVar(value=self.settings.get('plantilla', str(FORM)))
        self.search = tk.StringVar()
        self.date = tk.StringVar(value=date.today().isoformat())
        self.status = tk.StringVar()
        self.review_hint = tk.StringVar()
        self.inputs = ttk.Frame(self, padding=12)
        self.inputs.pack(fill='x')
        self.inputs.columnconfigure(1, weight=1)
        ttk.Label(self.inputs, text='Especificaciones de materias primas', font=('', 15, 'bold')).grid(
            row=0, columnspan=2, sticky='w', pady=(0, 6))
        for row, (label, kind) in enumerate((('Elegir Word vigente…', 'word'),
                                               ('Elegir PDF de respaldo…', 'pdfs')), 1):
            ttk.Button(self.inputs, text=label, command=lambda k=kind: self.pick(k)).grid(
                row=row, column=0, sticky='ew', pady=2)
            display = tk.StringVar(value='Sin seleccionar')
            setattr(self, kind+'_display', display)
            ttk.Label(self.inputs, textvariable=display, anchor='w', wraplength=670).grid(
                row=row, column=1, sticky='ew', padx=8)
        controls = ttk.Frame(self.inputs)
        controls.grid(row=3, columnspan=2, sticky='ew', pady=(10, 2))
        self.analyze_button = ttk.Button(controls, text='Analizar documentos', command=self.analyze)
        self.analyze_button.pack(side='left')
        ttk.Button(controls, text='Elegir secciones…', command=self.toggle_scope).pack(side='left', padx=8)
        self.scope_label = tk.StringVar(value='Todas las secciones')
        ttk.Label(controls, textvariable=self.scope_label).pack(side='left')
        ttk.Button(controls, text='Carpeta y plantilla…', command=self.configure_output).pack(side='right', padx=8)
        ttk.Button(controls, text='Catálogo local', command=self.show_catalog).pack(side='right')
        self.scope = ttk.Frame(self.inputs)
        self.scope.grid(row=4, columnspan=2, sticky='ew', pady=4)
        for section, label in SECTIONS.items():
            ttk.Checkbutton(self.scope, text=label, variable=self.sections[section],
                            command=self.scope_changed).pack(side='left', padx=(0, 12))
        self.scope.grid_remove()
        ttk.Label(self.inputs, text='Los PDF seleccionados se envían al servicio de análisis.').grid(
            row=5, columnspan=2, sticky='w', pady=(5, 0))

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill='both', expand=True, padx=12)
        review = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(review, text='Cambios propuestos')
        ttk.Label(review, textvariable=self.review_hint).pack(anchor='w', pady=(0, 6))
        notes = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(notes, text='Observaciones del análisis')
        self.notes = self.text_area(notes, 10)
        self.notes.configure(state='disabled')
        search_row = ttk.Frame(review)
        search_row.pack(fill='x', pady=(0, 8))
        ttk.Label(search_row, text='Buscar campo').pack(side='left', padx=(0, 8))
        ttk.Entry(search_row, textvariable=self.search).pack(side='left', fill='x', expand=True)
        self.search.trace_add('write', lambda *_: self.refresh())
        ttk.Button(search_row, text='Editar manualmente', command=self.manual_mode).pack(side='right', padx=8)
        table = ttk.Frame(review)
        table.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(table, columns=('section', 'field', 'current', 'proposed', 'state'), show='headings',
                                 selectmode='browse')
        for col, title, width in [('section', 'Sección', 65), ('field', 'Campo', 245),
                                  ('current', 'Antes', 220), ('proposed', 'Después', 220),
                                  ('state', 'Estado', 110)]:
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width)
        self.scroll(table, self.tree)
        self.tree.bind('<Double-1>', lambda _: self.edit())
        actions = ttk.Frame(review)
        actions.pack(fill='x', pady=(6, 0))
        self.edit_button = ttk.Button(actions, text='Revisar o editar', command=self.edit)
        self.edit_button.pack(side='left')
        self.discard_button = ttk.Button(actions, text='Descartar cambio', command=self.discard)
        self.discard_button.pack(side='left', padx=5)
        self.tree.bind('<<TreeviewSelect>>', self.update_review_actions)
        self.filter = tk.BooleanVar(value=True)
        ttk.Checkbutton(actions, text='Solo mostrar propuestas', variable=self.filter,
                        command=self.refresh).pack(side='left', padx=8)
        footer = ttk.Frame(self, padding=12)
        footer.pack(fill='x')
        ttk.Label(footer, textvariable=self.status).pack(side='left')
        self.export_button = ttk.Button(footer, text='Exportar expediente', command=self.export)
        self.export_button.pack(side='right')
        self.refresh()
        self.after(100, self.poll)

    @staticmethod
    def entry(parent, label, variable, width, show=''):
        ttk.Label(parent, text=label).pack(side='left', padx=(0, 4))
        ttk.Entry(parent, textvariable=variable, width=width, show=show).pack(side='left', padx=(0, 10))

    @staticmethod
    def scroll(parent, widget):
        bar = ttk.Scrollbar(parent, command=widget.yview)
        widget.configure(yscrollcommand=bar.set)
        bar.pack(side='right', fill='y')
        widget.pack(side='left', fill='both', expand=True)

    def text_area(self, parent, height):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True)
        widget = tk.Text(frame, height=height, wrap='word', padx=6, pady=5, undo=True)
        self.scroll(frame, widget)
        return widget

    def pick(self, kind):
        if kind == 'pdfs':
            location = {'initialdir': str(self.word.parent)} if self.word else {}
            chosen = filedialog.askopenfilenames(parent=self, title='Elegir PDF de respaldo',
                                                 filetypes=[('PDF', '*.pdf *.PDF')], **location)
            if not chosen:
                return
            self.pdfs = tuple(map(Path, chosen))
            names = ', '.join(p.name for p in self.pdfs[:2])
            extra = f' y {len(self.pdfs)-2} más' if len(self.pdfs) > 2 else ''
            self.pdfs_display.set(f'{len(self.pdfs)} PDF · {names}{extra}')
        else:
            chosen = filedialog.askopenfilename(parent=self, title='Elegir especificación vigente',
                                                 filetypes=[('Word', '*.docx *.doc')])
            if not chosen:
                return
            path = Path(chosen)
            try:
                loaded = Specification(word_bytes(path))
            except Exception as exc:
                messagebox.showerror('No se pudo cargar el Word', str(exc), parent=self)
                return
            if self.word and self.word != path:
                self.pdfs = ()
                self.pdfs_display.set('Sin seleccionar')
                for section in self.sections.values():
                    section.set(True)
                self.scope_changed()
            self.spec, self.word = loaded, path
            self.word_display.set(f'{path.name} · Versión vigente {loaded.version}')
        self.approved.clear()
        self.suggestions.clear()
        self.analysis_successes.clear()
        self.discarded.clear()
        self.filter.set(True)
        self.set_notes([])
        self.tabs.select(0)
        self.refresh()

    def toggle_scope(self):
        if self.scope.winfo_ismapped():
            self.scope.grid_remove()
        else:
            self.scope.grid()

    def scope_changed(self):
        active = [s for s, enabled in self.sections.items() if enabled.get()]
        label = 'Todas las secciones' if len(active) == len(SECTIONS) else ', '.join(
            'Identificación' if s == 'ID' else s for s in active)
        self.scope_label.set(label or 'Ninguna sección seleccionada')
        self.analysis_successes.clear()
        if self.spec:
            self.approved = {i: v for i, v in self.approved.items() if self.spec.fields[i].section in active}
        self.refresh()

    def selected_fields(self):
        return {i: f for i, f in self.spec.fields.items() if self.sections[f.section].get()}

    def refresh(self):
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        if self.spec:
            for i, f in self.selected_fields().items():
                proposals = self.suggestions.get(i, [])
                if norm(self.search.get()) not in norm(f'{f.label} {f.value}'):
                    continue
                if self.filter.get() and not (proposals or i in self.approved):
                    continue
                distinct = len({p['value'].strip() for _, p in proposals})
                state = ('Aprobado' if i in self.approved else 'En conflicto' if distinct > 1
                         else 'Por revisar' if proposals else '')
                proposed = self.approved.get(i, proposals[0][1]['value'] if proposals else '')
                after = 'Varias propuestas' if state == 'En conflicto' else ' '.join(proposed.split())
                self.tree.insert('', 'end', iid=i, values=(f.section, f.label,
                                                          ' '.join(f.value.split()), after, state))
        if selected and self.tree.exists(selected[0]):
            self.tree.selection_set(selected[0])
        ready = self.spec and self.pdfs and self.selected_fields()
        pending = set(self.pdfs) - self.analysis_successes.keys()
        retry = bool(self.analysis_successes and pending)
        self.analyze_button.configure(state='normal' if ready else 'disabled',
                                      text='Reintentar PDF pendientes' if retry else 'Analizar documentos')
        self.export_button.configure(state='normal' if self.approved else 'disabled')
        if not self.spec or not self.pdfs:
            self.status.set('Selecciona un Word vigente y sus PDF de respaldo.')
        elif self.approved:
            self.status.set(f'{len(self.approved)} cambio(s) aprobado(s) para exportar.')
        else:
            self.status.set('Archivos listos. Aprueba los cambios que quieras exportar.')
        if self.tree.get_children():
            self.review_hint.set('Selecciona un campo para consultar su evidencia, editarlo o aprobarlo.')
        elif self.spec:
            self.review_hint.set('Aquí aparecerán las propuestas. También puedes mostrar todos los campos para editarlos.')
        else:
            self.review_hint.set('Carga la documentación para comenzar la revisión.')
        self.update_review_actions()

    def update_review_actions(self, _event=None):
        selected = self.tree.selection()
        self.edit_button.configure(state='normal' if selected else 'disabled')
        has_change = selected and (selected[0] in self.approved or selected[0] in self.suggestions)
        self.discard_button.configure(state='normal' if has_change else 'disabled')

    def set_notes(self, notes):
        self.notes.configure(state='normal')
        self.notes.delete('1.0', 'end')
        self.notes.insert('1.0', '\n\n'.join(notes))
        self.notes.configure(state='disabled')

    def analyze(self):
        if not self.spec or not self.pdfs:
            return
        gemini_keys, groq_key = provider_keys()
        if not (gemini_keys or groq_key):
            messagebox.showinfo('Análisis no disponible',
                                'El servicio de análisis requiere configuración por parte del administrador.',
                                parent=self)
            return
        fields = self.selected_fields()
        if not fields:
            return
        pdfs, sap = self.pdfs, self.spec.sap
        model = os.getenv('MATERIA_PRIMA_GEMINI_MODEL', self.settings.get('modelo', MODEL))
        catalog = self.catalog.context(sap)
        successes = self.analysis_successes.copy()
        pending = tuple(path for path in pdfs if path not in successes)
        if not pending:
            pending = pdfs
            successes = {}
        if not successes:
            self.discarded.clear()
        stopped = Event()
        self.busy = tk.Toplevel(self)
        self.busy.title('Analizando documentación')
        self.busy.transient(self)
        self.busy.grab_set()
        panel = ttk.Frame(self.busy, padding=20)
        panel.pack(fill='both', expand=True)
        self.progress = ttk.Label(panel, text='Preparando documentos…', width=48)
        self.progress.pack(anchor='w')
        self.progress_bar = ttk.Progressbar(panel, maximum=len(pdfs), value=len(successes))
        self.progress_bar.pack(fill='x', pady=10)

        def cancel():
            stopped.set()
            self.progress.configure(text='Deteniendo el análisis…')
            cancel_button.configure(state='disabled')

        cancel_button = ttk.Button(panel, text='Detener', command=cancel)
        cancel_button.pack(anchor='e')
        self.busy.protocol('WM_DELETE_WINDOW', cancel)

        def analyze_file(path, index):
            if stopped.is_set():
                return None
            try:
                return inspect_document(path, fields, sap, catalog, gemini_keys, groq_key, model, index)
            except (OSError, ValueError) as exc:
                return exc

        def worker():
            errors = {}
            batch_error = ''
            try:
                with ThreadPoolExecutor(max_workers=3) as pool:
                    running = {pool.submit(analyze_file, path, pdfs.index(path)): path for path in pending}
                    for task in as_completed(running):
                        path = running[task]
                        outcome = task.result()
                        if isinstance(outcome, Exception):
                            errors[path] = str(outcome)
                        elif outcome is not None:
                            successes[path] = outcome
                        self.results.put(('progress', len(successes) + len(errors)))
            except Exception as exc:
                batch_error = str(exc)
            self.results.put(('done', (pdfs, successes, errors, batch_error)))

        Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            while True:
                event, value = self.results.get_nowait()
                if event == 'progress':
                    self.progress_bar.configure(value=value)
                    if 'Deteniendo' not in str(self.progress['text']):
                        self.progress.configure(text=f'{value} de {len(self.pdfs)} PDF procesados')
                else:
                    self.busy.destroy()
                    self.finish_analysis(*value)
        except Empty:
            pass
        self.after(100, self.poll)

    def finish_analysis(self, pdfs, successes, errors, batch_error):
        self.analysis_successes = successes
        self.suggestions = defaultdict(list)
        notes = [batch_error] if batch_error else []
        for path in pdfs:
            if path not in successes:
                reason = errors.get(path, 'Pendiente de análisis.')
                notes.append(f'{path.name} · {reason}')
                continue
            changes, remarks, provider = successes[path]
            for change in changes:
                if change['id'] not in self.discarded:
                    self.suggestions[change['id']].append((path, change))
            notes.append(f'{path.name} · {provider} · {len(changes)} propuesta(s)')
            notes.extend(f'{path.name} · {remark}' for remark in remarks)
        self.set_notes(notes)
        self.filter.set(bool(self.suggestions))
        self.refresh()
        remaining = len(pdfs) - len(successes)
        if remaining:
            self.status.set(f'{len(successes)} de {len(pdfs)} PDF analizados. Consulta las observaciones.')
        elif not self.suggestions:
            self.status.set('Todos los PDF analizados. Sin cambios detectados.')
        else:
            self.status.set(f'Todos los PDF analizados. {len(self.suggestions)} campos por revisar.')
        self.tabs.select(0 if self.suggestions else 1)

    def edit(self):
        selected = self.tree.selection()
        if not selected:
            return
        i = selected[0]
        field = self.spec.fields[i]
        proposals = self.suggestions.get(i, [])
        dialog = tk.Toplevel(self)
        dialog.title(f'{field.section} · {field.label}')
        dialog.geometry('760x570')
        dialog.transient(self)
        dialog.grab_set()
        main = ttk.Frame(dialog, padding=12)
        main.pack(fill='both', expand=True)
        ttk.Label(main, text='Valor vigente').pack(anchor='w')
        current = self.text_area(main, 3)
        current.insert('1.0', field.value or '—')
        current.configure(state='disabled')
        options = ttk.Frame(main)
        options.pack(fill='x', pady=6)
        source = tk.StringVar()
        choice = ttk.Combobox(options, textvariable=source, state='readonly',
                              values=[f'{n+1}. {p.name} · página {c["page"]}'
                                      for n, (p, c) in enumerate(proposals)])
        choice.pack(side='left', fill='x', expand=True)
        def open_source():
            if choice.current() >= 0:
                path = proposals[choice.current()][0]
                if os.name == 'nt':
                    os.startfile(str(path))
                else:
                    import webbrowser
                    webbrowser.open(path.resolve().as_uri())
        ttk.Button(options, text='Abrir PDF', command=open_source).pack(side='right')
        ttk.Label(main, text='Evidencia citada').pack(anchor='w')
        evidence = self.text_area(main, 3)
        evidence.configure(state='disabled')
        ttk.Label(main, text='Valor final editable').pack(anchor='w', pady=(6, 0))
        target = self.text_area(main, 6)

        def show_proposal(update=True):
            index = choice.current()
            if index < 0:
                return
            _, change = proposals[index]
            evidence.configure(state='normal')
            evidence.delete('1.0', 'end')
            evidence.insert('1.0', change['evidence'])
            evidence.configure(state='disabled')
            if update:
                target.delete('1.0', 'end')
                target.insert('1.0', change['value'])

        target.insert('1.0', self.approved.get(i, field.value))
        if proposals and (i in self.approved or len({p['value'] for _, p in proposals}) == 1):
            choice.current(0)
            show_proposal(update=i not in self.approved)
        elif proposals:
            source.set('Elige una fuente para comparar propuestas en conflicto')
        choice.bind('<<ComboboxSelected>>', lambda _: show_proposal())

        def approve():
            value = target.get('1.0', 'end-1c')
            try:
                deepcopy(field).write(value)
            except ValueError as exc:
                messagebox.showerror('Revisa el valor', str(exc), parent=dialog)
                return
            if value.strip() == field.value.strip():
                self.approved.pop(i, None)
            else:
                self.approved[i] = value
            dialog.destroy()
            self.refresh()

        ttk.Button(main, text='Aprobar este valor', command=approve).pack(anchor='e', pady=(6, 0))

    def discard(self):
        for i in self.tree.selection():
            self.approved.pop(i, None)
            self.suggestions.pop(i, None)
            self.discarded.add(i)
        self.refresh()

    def show_catalog(self):
        if not self.spec:
            messagebox.showinfo('Catálogo local', 'Carga un Word para consultar sus entidades.', parent=self)
            return
        entries = self.catalog.entries(self.spec.sap)
        messagebox.showinfo(f'Catálogo · {self.spec.sap}',
                            '\n'.join(f'{role}: {name}' for role, name in entries)
                            or 'Se incorporan entidades cuando exportas cambios aprobados.', parent=self)

    def manual_mode(self):
        self.filter.set(False)
        self.search.set('')
        self.tabs.select(0)
        self.refresh()
        self.review_hint.set('Selecciona el campo, escribe el valor correcto y apruébalo para incluirlo en la exportación.')

    def choose_directory(self, parent=None):
        directory = filedialog.askdirectory(parent=parent or self, title='Carpeta de expedientes')
        if directory:
            self.output_dir.set(directory)

    def configure_output(self):
        dialog = tk.Toplevel(self)
        dialog.title('Carpeta y plantilla')
        dialog.transient(self)
        dialog.grab_set()
        main = ttk.Frame(dialog, padding=20)
        main.pack(fill='both', expand=True)
        ttk.Label(main, text='Carpeta de expedientes').pack(anchor='w')
        ttk.Entry(main, textvariable=self.output_dir, width=65).pack(fill='x', pady=5)
        ttk.Button(main, text='Elegir carpeta…', command=lambda: self.choose_directory(dialog)).pack(anchor='e')
        ttk.Label(main, text='Plantilla de solicitud de cambio').pack(anchor='w', pady=(12, 0))
        ttk.Entry(main, textvariable=self.form_path, width=65).pack(fill='x', pady=5)
        def choose_form():
            path = filedialog.askopenfilename(parent=dialog, filetypes=[('Excel', '*.xlsx')])
            if path:
                try:
                    ChangeForm(Path(path).read_bytes())
                except Exception as exc:
                    messagebox.showerror('Plantilla incompatible', str(exc), parent=dialog)
                    return
                self.form_path.set(path)
        ttk.Button(main, text='Elegir plantilla…', command=choose_form).pack(anchor='e')
        def save():
            if self.output_dir.get() and not Path(self.output_dir.get()).is_dir():
                messagebox.showerror('Carpeta no disponible', 'Selecciona una carpeta existente.', parent=dialog)
                return
            try:
                ChangeForm(Path(self.form_path.get()).read_bytes())
                self.save_preferences()
            except Exception as exc:
                messagebox.showerror('No se pudo guardar', str(exc), parent=dialog)
                return
            dialog.destroy()
        ttk.Button(main, text='Configurar servicio de análisis…',
                   command=self.configure_service).pack(anchor='w', pady=(15, 0))
        ttk.Button(main, text='Guardar configuración', command=save).pack(anchor='e', pady=(15, 0))

    def configure_service(self):
        dialog = tk.Toplevel(self)
        dialog.title('Configuración del servicio')
        dialog.transient(self)
        dialog.grab_set()
        main = ttk.Frame(dialog, padding=20)
        main.pack(fill='both', expand=True)
        ttk.Label(main, text='Si falla el acceso, puedes actualizar las credenciales del servicio.').pack(anchor='w')
        ttk.Label(main, text='Modelo de Gemini').pack(anchor='w', pady=(10, 0))
        model = tk.StringVar(value=self.settings.get('modelo', MODEL))
        ttk.Combobox(main, textvariable=model, values=[MODEL, 'gemini-2.5-flash'], width=45).pack(fill='x')
        values = []
        for label, filename in [('Gemini principal', '.gemini-key'), ('Gemini adicional', '.gemini-key-extra'),
                                ('Groq', '.groq-key')]:
            path = self.catalog.path.parent / filename
            fallback = (RESOURCE_ROOT / filename)
            try:
                current = (path if path.exists() else fallback).read_text().strip()
            except OSError:
                current = ''
            variable = tk.StringVar(value=current)
            ttk.Label(main, text=label).pack(anchor='w', pady=(8, 0))
            ttk.Entry(main, textvariable=variable, show='*', width=55).pack(fill='x')
            values.append((path, variable))
        def save():
            try:
                if not re.fullmatch(r'gemini-[a-zA-Z0-9._-]+', model.get().strip()):
                    raise ValueError('Indica un modelo Gemini válido.')
                for path, value in values:
                    temporary = path.with_suffix('.tmp')
                    temporary.touch(mode=0o600, exist_ok=True)
                    temporary.write_text(value.get().strip(), encoding='utf-8')
                    temporary.chmod(0o600)
                    temporary.replace(path)
                self.settings['modelo'] = model.get().strip()
                self.save_preferences()
            except (OSError, ValueError) as exc:
                messagebox.showerror('No se pudo guardar', str(exc), parent=dialog)
                return
            dialog.destroy()
        ttk.Button(main, text='Guardar credenciales', command=save).pack(anchor='e', pady=(15, 0))

    def save_preferences(self):
        settings = {**self.settings, 'salida': self.output_dir.get(), 'plantilla': self.form_path.get(),
                    'solicitante': self.applicant.get(), 'area': self.area.get()}
        temporary = self.settings_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(settings, ensure_ascii=False), encoding='utf-8')
        temporary.replace(self.settings_path)

    def export(self):
        dialog = tk.Toplevel(self)
        dialog.title('Exportar documentos')
        dialog.transient(self)
        dialog.grab_set()
        main = ttk.Frame(dialog, padding=16)
        main.pack(fill='both', expand=True)
        ttk.Label(main, text=f'{len(self.approved)} cambio(s) aprobado(s) · Versión {self.spec.version+1}').pack(anchor='w')
        ttk.Label(main, text='Se generarán el Word y la solicitud AS-REG-018.').pack(anchor='w', pady=(2, 10))
        for label, value in [('Solicitante (opcional)', self.applicant), ('Área (opcional)', self.area),
                             ('Fecha (AAAA-MM-DD)', self.date)]:
            row = ttk.Frame(main)
            row.pack(fill='x', pady=3)
            self.entry(row, label, value, 24)
        ttk.Label(main, text='Carpeta de expedientes').pack(anchor='w', pady=(12, 0))
        ttk.Entry(main, textvariable=self.output_dir, width=60).pack(fill='x', pady=4)
        ttk.Button(main, text='Elegir carpeta…', command=lambda: self.choose_directory(dialog)).pack(anchor='e')
        ttk.Label(main, text='El expediente incluirá el Word, la solicitud, los PDF y el registro de cambios.').pack(anchor='w', pady=8)
        ttk.Button(main, text='Crear expediente',
                   command=lambda: self.save_export(dialog)).pack(anchor='e', pady=(10, 0))

    def save_export(self, dialog):
        try:
            effective = date.fromisoformat(self.date.get())
        except ValueError:
            messagebox.showerror('Fecha inválida', 'Usa AAAA-MM-DD.', parent=dialog)
            return
        directory = self.output_dir.get().strip()
        if not directory or not Path(directory).is_dir():
            messagebox.showinfo('Elige la carpeta de salida', 'Selecciona dónde guardar los expedientes.', parent=dialog)
            self.choose_directory(dialog)
            return
        if not self.applicant.get().strip() or not self.area.get().strip():
            messagebox.showinfo('Completa los datos del solicitante',
                                'Indica solicitante y área para documentar la solicitud.', parent=dialog)
            return
        label = f'{self.spec.sap}_V{self.spec.version+1}'
        dest = Path(directory)/label
        suffix = 2
        while dest.exists():
            dest = Path(directory) / f'{label}_{suffix}'
            suffix += 1
        try:
            with TemporaryDirectory(dir=directory) as tmp:
                stage = Path(tmp)/label
                stage.mkdir()
                spec = Specification(self.spec.data)
                approved = self.approved.copy()
                ChangeForm(Path(self.form_path.get()).read_bytes()).export(
                    stage/f'SC_{label}.xlsx', spec, approved, self.applicant.get().strip(),
                    self.area.get().strip(), effective)
                spec.export(stage/f'ET_{label}.docx', approved, effective)
                attachments = stage / 'PDF de respaldo'
                attachments.mkdir()
                for index, source in enumerate(self.pdfs, 1):
                    shutil.copy2(source, attachments / f'{index:02d}_{source.name}')
                record = {
                    'sap': spec.sap, 'version_anterior': spec.version,
                    'version_nueva': spec.version + 1, 'fecha': effective.isoformat(),
                    'solicitante': self.applicant.get().strip(), 'area': self.area.get().strip(),
                    'word_origen': self.word.name,
                    'pdf_sin_analizar': [p.name for p in self.pdfs if p not in self.analysis_successes],
                    'cambios': [
                        {'seccion': spec.fields[i].section, 'campo': spec.fields[i].label,
                         'antes': spec.fields[i].value, 'despues': value,
                         'evidencias_propuestas': [
                             {'pdf': path.name, 'pagina': change['page'], 'cita': change['evidence']}
                             for path, change in self.suggestions.get(i, [])]}
                        for i, value in approved.items()],
                }
                (stage / 'registro_de_cambios.json').write_text(
                    json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
                self.save_preferences()
                stage.rename(dest)
        except Exception as exc:
            messagebox.showerror('No se pudo exportar', str(exc), parent=self)
            return

        dialog.destroy()
        entities = set()
        for i, field in spec.fields.items():
            if field.section != 'B':
                continue
            value = approved.get(i, field.value)
            if field.kind == 'manufacturer':
                pairs = (line.partition(':')[::2] for line in value.splitlines())
            else:
                role = norm(field.label.split(' · ', 1)[0])
                if role not in {'fabricante', 'proveedor'}:
                    continue
                if ':' in value:
                    value = value.split(':', 1)[1]
                pairs = ((role, line) for line in value.splitlines())
            for role, name in pairs:
                role = norm(role)
                name = re.sub(r'^\s*\(?\d+\)\s*', '', name).strip(' :')
                if role in {'fabricante', 'proveedor'} and norm(name) not in {'', '-', 'n.a.', 'no aplica'}:
                    entities.add((role, name))
        try:
            self.catalog.save(spec.sap, entities)
        except Exception as exc:
            messagebox.showwarning('Archivos exportados', f'{dest}\n\nCatálogo pendiente: {exc}', parent=self)
        else:
            messagebox.showinfo('Archivos exportados', str(dest), parent=self)


if __name__ == '__main__':
    from materia_prima.presentation.desktop import main
    main()
