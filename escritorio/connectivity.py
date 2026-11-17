"""Asynchronous HTTPS reachability, not Wi-Fi signal strength."""
from threading import Lock, Thread
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from time import monotonic
from datetime import datetime, timezone

_lock=Lock()
_status={'state':'checking','checked_at':None}
_last=0
_running=False


def check(force=False):
    global _running
    with _lock:
        if not _running and (force or monotonic()-_last>20):
            _running=True
            Thread(target=_probe,daemon=True).start()
        return _status.copy()


def _probe():
    global _running,_last,_status
    online=False
    for url in ('https://generativelanguage.googleapis.com/','https://www.google.com/generate_204'):
        try:
            with urlopen(Request(url,method='HEAD'),timeout=3):online=True
        except HTTPError:
            online=True # An HTTP response proves HTTPS reachability, not API authorization.
        except (OSError,ValueError):
            pass
        if online:break
    with _lock:
        _status={'state':'online' if online else 'offline','checked_at':datetime.now(timezone.utc).isoformat()}
        _last=monotonic();_running=False
