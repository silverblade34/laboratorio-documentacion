#!/bin/zsh
set -eu
cd -- "${0:A:h}"
if [[ -x .venv-mac/bin/python ]] && .venv-mac/bin/python -c 'import webview, lxml, pypdf' 2>/dev/null; then
    if ! .venv-mac/bin/python -c 'import pypdfium2, PIL' 2>/dev/null; then
        .venv-mac/bin/python -m pip install -r requirements.txt
    fi
    exec .venv-mac/bin/python desktop.py
fi
runtime="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
if [[ -x "$runtime" ]] && "$runtime" -c 'import tkinter, lxml, pypdf, pypdfium2, PIL' 2>/dev/null; then
    exec "$runtime" desktop.py
fi
python_bin=${MP_PYTHON:-python3}
if ! "$python_bin" -c 'import tkinter' 2>/dev/null; then
    echo 'Se requiere Python con Tkinter. Instala Python para macOS desde python.org.'
    exit 1
fi
if [[ ! -x .venv/bin/python ]]; then
    "$python_bin" -m venv .venv
fi
if ! .venv/bin/python -c 'import lxml, pypdf, pypdfium2, PIL' 2>/dev/null; then
    .venv/bin/python -m pip install -r requirements.txt
fi
exec .venv/bin/python desktop.py
