"""Conversión local de documentos heredados mediante Microsoft Word."""
from pathlib import Path
import os
import subprocess
import tempfile

def word_bytes(path):
    if path.suffix.lower() == '.docx':
        return path.read_bytes()
    if os.name != 'nt':
        raise ValueError('Para abrir .doc, conviértelo a .docx o usa Windows con Microsoft Word.')
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp)/'converted.docx'
        script = Path(tmp)/'convert.ps1'
        script.write_text(r"""
param([string]$Source, [string]$Destination)
$ErrorActionPreference = 'Stop'
$word = New-Object -ComObject Word.Application
try {
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $doc = $word.Documents.Open($Source, $false, $true)
    try { $doc.SaveAs2($Destination, 16) } finally { $doc.Close(0) }
} finally { $word.Quit(0) }
""", encoding='utf-8')
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive',
                                 '-ExecutionPolicy', 'Bypass', '-File', str(script),
                                 str(path.resolve()), str(dest)], capture_output=True,
                                timeout=90, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode or not dest.exists():
            raise ValueError('No se pudo convertir el .doc. Abre el archivo en Word y guárdalo como .docx.')
        return dest.read_bytes()

