"""Salud de las claves de API: resultado de cada llamada real y pruebas a pedido.

Nunca se guarda la clave: solo una huella (SHA-256 truncado) y una versión enmascarada.
"""
from datetime import datetime
from pathlib import Path
from threading import Lock
import hashlib
import json
import time

SATURATION_WINDOW = 15 * 60  # Un 429/503 reciente marca la clave como saturada durante 15 minutos.
_lock = Lock()
_data = {}
_path = None


def fingerprint(key):
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def masked(key):
    return key[:4] + '…' + key[-4:] if len(key) > 10 else '…'


def setup(directory):
    global _path, _data
    _path = Path(directory) / 'salud_claves.json'
    try:
        _data = json.loads(_path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        _data = {}


def _save():
    if _path is None:
        return
    try:
        temp = _path.with_suffix('.tmp')
        temp.write_text(json.dumps(_data, ensure_ascii=False), encoding='utf-8')
        temp.replace(_path)
    except OSError:
        pass


def provider_of(url):
    if 'generativelanguage.googleapis.com' in url:
        return 'gemini'
    if 'groq.com' in url:
        return 'groq'
    if 'openrouter.ai' in url:
        return 'openrouter'
    return ''


def record(provider, key, ok, code=None, message='', seconds=None, detail=None):
    """Registra el resultado de una llamada hecha con esa clave."""
    if not provider or not key:
        return
    with _lock:
        item = _data.setdefault(fingerprint(key), {'provider': provider, 'ok': 0, 'fail': 0})
        item.update({'provider': provider, 'masked': masked(key), 'last_at': time.time(),
                     'last_ok': bool(ok), 'last_code': code, 'last_message': message})
        if seconds is not None:
            item['last_seconds'] = round(seconds, 1)
        if detail is not None:
            item['detail'] = detail
        if ok:
            item['ok'] += 1
            item['last_success'] = item['last_at']
        else:
            item['fail'] += 1
            if code in (429, 503):
                item['saturated_at'] = item['last_at']
        _save()


def set_detail(key, detail):
    """Dato extra de la última prueba (p. ej. crédito restante en OpenRouter), sin contar otra llamada."""
    with _lock:
        item = _data.get(fingerprint(key))
        if item is not None:
            item['detail'] = detail
            _save()


def status(item):
    """ok | saturada | invalida | error | sin_uso."""
    if not item or 'last_at' not in item:
        return 'sin_uso'
    if item.get('last_ok'):
        return 'ok'
    code = item.get('last_code')
    if code in (401, 403):
        return 'invalida'
    if code in (429, 503) or time.time() - item.get('saturated_at', 0) < SATURATION_WINDOW:
        return 'saturada'
    return 'error'


def usable(key):
    """False si la clave está saturada o es inválida según su última respuesta reciente."""
    with _lock:
        return status(_data.get(fingerprint(key))) not in ('saturada', 'invalida')


def report(keys):
    """keys: [(proveedor, clave, origen)] configuradas. Devuelve filas para la interfaz."""
    rows = []
    with _lock:
        for provider, key, source in keys:
            item = dict(_data.get(fingerprint(key), {}))
            when = item.get('last_at')
            rows.append({'provider': provider, 'id': fingerprint(key), 'masked': masked(key), 'source': source,
                         'status': status(item), 'ok': item.get('ok', 0), 'fail': item.get('fail', 0),
                         'last_at': datetime.fromtimestamp(when).isoformat(timespec='seconds') if when else '',
                         'last_message': item.get('last_message', ''), 'last_code': item.get('last_code'),
                         'last_seconds': item.get('last_seconds'), 'detail': item.get('detail'),
                         'saturated_at': datetime.fromtimestamp(item['saturated_at']).isoformat(timespec='seconds')
                         if item.get('saturated_at') else ''})
    return rows
