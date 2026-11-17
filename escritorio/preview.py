"""Local Word-to-PDF preview. No document leaves the computer."""
from pathlib import Path
from tempfile import TemporaryDirectory
from io import BytesIO
import base64
import os
import shutil
import subprocess


def renderer_path(configured=''):
    candidates = [configured, os.getenv('MATERIA_SOFFICE', ''), shutil.which('soffice'),
        '/Applications/LibreOffice.app/Contents/MacOS/soffice',
        str(Path(os.getenv('PROGRAMFILES', 'C:/Program Files'))/'LibreOffice/program/soffice.exe'),
        str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/soffice')]
    return next((str(p) for p in candidates if p and Path(p).is_file()), None)


def render_document(spec, approved, effective, add_history, history_text, renderer=''):
    from office import Specification, W, replace_parts
    import pypdfium2 as pdfium
    draft = Specification(spec.data)
    original = set(draft.parts['word/document.xml'].iter())
    with TemporaryDirectory(prefix='materia-preview-') as folder:
        folder = Path(folder)
        word = folder/'documento.docx'
        if approved:
            draft.export(word, approved, effective,
                         add_history and bool((history_text if history_text is not None else spec.history_summary(approved)).strip()), history_text)
        else:
            word.write_bytes(spec.data)
        # Only the preview copy receives highlighting; final export remains clean.
        marked = {draft.fields[i].node for i in approved if draft.fields[i].kind in {'text','range','range_add'}}
        marked.update(n for n in draft.parts['word/document.xml'].iter() if n not in original and n.tag in {W+'tc',W+'p'})
        from lxml import etree as ET
        for node in marked:
            for run in node.iter(W+'r'):
                props = run.find(W+'rPr')
                if props is None:
                    props=ET.Element(W+'rPr');run.insert(0,props)
                existing=props.find(W+'highlight')
                if existing is None:existing=ET.SubElement(props,W+'highlight')
                existing.set(W+'val','yellow')
        if approved:
            replace_parts(spec.data, word, draft.parts)
        output=folder/'documento.pdf'
        converter=renderer_path(renderer)
        if converter:
            result=subprocess.run([converter,'-env:UserInstallation='+ (folder/'profile').as_uri(),
                '--headless','--convert-to','pdf','--outdir',str(folder),str(word)],
                capture_output=True,timeout=90)
            if result.returncode or not output.is_file():
                raise ValueError('El renderizador no pudo convertir el Word. Revisa su instalación en Configuración o usa la vista de contenido.')
        elif os.name == 'nt':
            script=folder/'preview.ps1'
            script.write_text('''param([string]$Source,[string]$Destination)
$ErrorActionPreference='Stop'
$word=New-Object -ComObject Word.Application
try {$word.Visible=$false;$word.DisplayAlerts=0;$word.AutomationSecurity=3
$doc=$word.Documents.Open($Source,$false,$true)
try {$doc.ExportAsFixedFormat($Destination,17)} finally {$doc.Close(0)}} finally {$word.Quit(0)}
''')
            subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-File',str(script),str(word),str(output)],capture_output=True,timeout=90,check=True)
        else:
            raise ValueError('Para ver las páginas reales instala LibreOffice o indica su ejecutable en Configuración. Puedes usar Vista de contenido mientras tanto.')
        if not output.exists():raise ValueError('No se generó el PDF de previsualización.')
        pages=[]
        from evidence_view import PDFIUM_LOCK
        with PDFIUM_LOCK:  # PDFium no admite llamadas simultáneas desde varios hilos.
            document=pdfium.PdfDocument(str(output))
            try:
                for index in range(len(document)):
                    page=document[index];bitmap=page.render(scale=1.65)
                    try:
                        im=bitmap.to_pil();buf=BytesIO();im.save(buf,format='PNG');im.close()
                        pages.append('data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode())
                    finally:bitmap.close();page.close()
            finally:document.close()
        return {'pages':pages,'renderer':'LibreOffice' if converter else 'Microsoft Word'}
