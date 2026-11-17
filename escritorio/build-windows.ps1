$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $compiler = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    $iscc = if ($compiler) { $compiler.Source } else { "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" }
    if (!(Test-Path $iscc)) { throw 'Instala Inno Setup 6 antes de compilar.' }
    py -3.12 -m venv .venv
    if ($LASTEXITCODE) { throw 'Se requiere Python 3.12 para Windows.' }
    $python = '.\.venv\Scripts\python.exe'
    & $python -m pip install -r requirements.txt 'pyinstaller>=6,<7'
    if ($LASTEXITCODE) { throw 'Falló la instalación de dependencias.' }
    & $python -m PyInstaller --noconfirm --clean --windowed --collect-all pypdfium2 --collect-all pypdfium2_raw --hidden-import PIL.Image --name MateriaPrima --add-data "AS-REG-018.xlsx:." --add-data "ui:ui" --add-data "tecnicas.json:." --add-data "ejemplo:ejemplo" desktop.py
    if ($LASTEXITCODE) { throw 'Falló la compilación del ejecutable.' }
    & $iscc MateriaPrima.iss
    if ($LASTEXITCODE) { throw 'Falló la compilación del instalador.' }
} finally {
    Pop-Location
}
