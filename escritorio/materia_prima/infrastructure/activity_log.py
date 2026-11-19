"""Registro técnico en tiempo real para diagnóstico (monitor oculto de la interfaz).

Guarda los eventos en memoria para el monitor y en un archivo rotativo junto al catálogo.
Las credenciales se ocultan antes de registrar cualquier texto.
"""
from collections import deque
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
import itertools
import logging
import os
import re
import threading
import traceback

_events = deque(maxlen=3000)
_lock = threading.Lock()
_seq = itertools.count(1)
_file = None
_secrets = set()
SECRET = re.compile(r'(AIza[0-9A-Za-z_\-]{20,}|gsk_[0-9A-Za-z]{20,}|AQ\.[0-9A-Za-z_\-]{20,}|Bearer\s+\S+|x-goog-api-key[^,\n]*)')


def register_secrets(*values):
    _secrets.update(v for v in values if v and len(v) >= 8)


def redact(text):
    text = str(text)
    for value in _secrets:
        text = text.replace(value, '•••')
    return SECRET.sub('•••', text)


def setup(directory):
    global _file
    if _file is not None:
        return
    path = Path(directory) / 'registro_tecnico.log'
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=3, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(message)s'))
    _file = logging.getLogger('materia.registro')
    _file.setLevel(logging.INFO)
    _file.propagate = False
    _file.addHandler(handler)


def log(level, source, message, detail=''):
    """level: info | ok | warn | error | debug."""
    event = {'seq': next(_seq), 'time': datetime.now().strftime('%H:%M:%S.%f')[:-3],
             'level': level, 'source': redact(source), 'message': redact(message),
             'detail': redact(detail)[:6000], 'thread': threading.current_thread().name}
    with _lock:
        _events.append(event)
    if _file is not None:
        line = f"{datetime.now().isoformat(timespec='milliseconds')} {level.upper():5} [{event['source']}] {event['message']}"
        if event['detail']:
            line += '\n    ' + event['detail'].replace('\n', '\n    ')
        try:
            _file.info(line)
        except Exception:
            pass
    return event


def exception(source, message):
    return log('error', source, message, traceback.format_exc())


def events(after=0, limit=800):
    with _lock:
        items = [e for e in _events if e['seq'] > after]
    return items[-limit:]


def log_path():
    if _file is None or not _file.handlers:
        return ''
    return getattr(_file.handlers[0], 'baseFilename', '')


def clear():
    with _lock:
        _events.clear()


def environment():
    import platform
    import sys
    return f'Python {sys.version.split()[0]} · {platform.platform()} · PID {os.getpid()}'
