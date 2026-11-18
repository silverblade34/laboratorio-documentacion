"""El monitor técnico registra errores del servicio con su detalle y nunca expone claves."""
from io import BytesIO
from pathlib import Path
from unittest import mock
from urllib import error, request
import aislar  # noqa: F401  (antes que los módulos de la aplicación)
import sys, unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import activity_log as alog
from analysis_service import ServiceError, send_request


class ActivityLog(unittest.TestCase):
    def test_http_error_body_is_logged_and_keys_redacted(self):
        alog.register_secrets('clave-secreta-de-prueba-123')
        body = b'{"error":{"code":429,"message":"Quota exceeded for key clave-secreta-de-prueba-123 AIzaSyA1234567890123456789012345"}}'
        failure = error.HTTPError('https://generativelanguage.googleapis.com/v1beta/models/x:generateContent', 429, 'Too Many', {}, BytesIO(body))
        req = request.Request('https://generativelanguage.googleapis.com/v1beta/models/x:generateContent', b'{}', {'x-goog-api-key': 'clave-secreta-de-prueba-123'})
        start = alog.events()[-1]['seq'] if alog.events() else 0
        with mock.patch.object(request, 'urlopen', side_effect=failure):
            with self.assertRaises(ServiceError):
                send_request(req, 5)
        last = [e for e in alog.events(start) if e['level'] == 'error'][-1]
        self.assertIn('429', last['message'])
        self.assertIn('Quota exceeded', last['detail'])
        self.assertNotIn('clave-secreta', last['detail'])
        self.assertNotIn('AIzaSy', last['detail'])


if __name__ == '__main__':
    unittest.main()
