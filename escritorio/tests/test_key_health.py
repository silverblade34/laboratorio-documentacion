"""Monitor de salud de las claves de API (sin llamadas reales)."""
from io import BytesIO
from pathlib import Path
from unittest import mock
from urllib import error, request
import aislar  # noqa: F401  (antes que los módulos de la aplicación)
import json, os, sys, tempfile, unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analysis_service
import key_health


class Response(BytesIO):
    status = 200
    def __enter__(self): return self
    def __exit__(self, *args): return False


class KeyHealth(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        key_health.setup(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, key, outcome):
        req = request.Request('https://generativelanguage.googleapis.com/v1beta/models/x:generateContent', b'{}',
                              {'x-goog-api-key': key})
        with mock.patch.object(analysis_service.request, 'urlopen', side_effect=outcome):
            try:
                analysis_service.send_request(req, 5)
            except analysis_service.ServiceError:
                pass

    def test_calls_update_status_without_storing_the_key(self):
        rate_limit = error.HTTPError('u', 429, 'Too Many Requests', {}, BytesIO(b'{}'))
        self.call('clave-saturada-123', [rate_limit])
        self.call('clave-buena-4567', [Response(json.dumps({'candidates': []}).encode())])
        rows = {r['masked']: r for r in key_health.report([('gemini', 'clave-saturada-123', 'configuración'),
                                                           ('gemini', 'clave-buena-4567', 'configuración'),
                                                           ('groq', 'clave-nueva-0000', 'configuración')])}
        self.assertEqual(rows['clav…-123']['status'], 'saturada')
        self.assertEqual(rows['clav…4567']['status'], 'ok')
        self.assertEqual(rows['clav…0000']['status'], 'sin_uso')
        saved = (Path(self.tmp.name)/'salud_claves.json').read_text(encoding='utf-8')
        self.assertNotIn('clave-saturada-123', saved)

    def test_invalid_key_is_reported(self):
        body = json.dumps({'error': {'details': [{'reason': 'API_KEY_INVALID'}]}}).encode()
        self.call('clave-invalida-99', [error.HTTPError('u', 400, 'Bad Request', {}, BytesIO(body))])
        self.assertEqual(key_health.report([('gemini', 'clave-invalida-99', 'configuración')])[0]['status'], 'invalida')

    def test_delete_key_only_removes_that_key(self):
        with mock.patch.dict(os.environ, {'LOCALAPPDATA': self.tmp.name}):
            folder = Path(self.tmp.name)/'MateriaPrima'; folder.mkdir()
            (folder/'.groq-key').write_text('uno-aaaaaaaa\ndos-bbbbbbbb\n', encoding='utf-8')
            analysis_service.delete_key('groq', key_health.fingerprint('uno-aaaaaaaa'))
            self.assertEqual((folder/'.groq-key').read_text(encoding='utf-8').split(), ['dos-bbbbbbbb'])
            with self.assertRaises(ValueError):
                analysis_service.delete_key('groq', 'no-existe')

    def test_saturated_gemini_model_falls_back(self):
        """Un 503 del modelo elegido pasa al modelo de respaldo sin gastar las demás claves."""
        calls = []
        def fake(path, fields, sap, entries, key, model):
            calls.append((key, model))
            if model == 'gemini-3.5-flash':
                raise analysis_service.ServiceError('saturado', True, 503)
            return [], [], []
        pdf = Path(self.tmp.name)/'a.pdf'; pdf.write_bytes(b'%PDF-1.4')
        available = ['gemini-3.8-flash', 'gemini-3.5-flash', 'gemini-2.5-flash']
        with mock.patch.object(analysis_service, 'inspect_pdf', side_effect=fake), \
             mock.patch.object(analysis_service, 'gemini_models', return_value=available):
            changes, notes, provider, companies = analysis_service.inspect_document(
                pdf, {}, '1', [], ('k1', 'k2'), (), 'gemini-3.5-flash', 0)
        self.assertEqual(calls, [('k1', 'gemini-3.5-flash'), ('k1', 'gemini-3.8-flash')])
        self.assertEqual(provider, 'Gemini (gemini-3.8-flash)')
        self.assertTrue(any('saturado' in n for n in notes))

    def test_retired_model_is_remembered_and_skipped(self):
        calls = []
        def fake(path, fields, sap, entries, key, model):
            calls.append(model)
            if model == 'gemini-2.5-flash':
                raise analysis_service.ServiceError('no disponible', True, 404)
            return [], [], []
        pdf = Path(self.tmp.name)/'a.pdf'; pdf.write_bytes(b'%PDF-1.4')
        analysis_service._unavailable_models.clear()
        with mock.patch.object(analysis_service, 'inspect_pdf', side_effect=fake), \
             mock.patch.object(analysis_service, 'gemini_models', return_value=['gemini-3.8-flash']):
            analysis_service.inspect_document(pdf, {}, '1', [], ('k1',), (), 'gemini-2.5-flash', 0)
            analysis_service.inspect_document(pdf, {}, '1', [], ('k1',), (), 'gemini-2.5-flash', 0)
        analysis_service._unavailable_models.clear()
        self.assertEqual(calls, ['gemini-2.5-flash', 'gemini-3.8-flash', 'gemini-3.8-flash'])

    def test_daily_quota_message_says_when_it_renews(self):
        body = json.dumps({'error': {'message': 'Quota exceeded for metric: generate_content_free_tier_requests, limit: 20, '
                                     'description: Generate content requests per day limit exceeded on Free Tier. Please retry in 4h14m53.9s.'}}).encode()
        self.call('clave-diaria-1234', [error.HTTPError('u', 429, 'Too Many Requests', {}, BytesIO(body))])
        row = key_health.report([('gemini', 'clave-diaria-1234', 'configuración')])[0]
        self.assertEqual(row['status'], 'saturada')
        self.assertIn('cuota diaria', row['last_message'])
        self.assertIn('4 h 14 min', row['last_message'])

    def test_openrouter_list_keeps_only_free_text_models(self):
        data = {'data': [
            {'id': 'google/gemma:free', 'name': 'Gemma (free)', 'context_length': 1000, 'pricing': {'prompt': '0', 'completion': '0'},
             'supported_parameters': ['response_format'], 'architecture': {'input_modalities': ['text', 'image'], 'output_modalities': ['text']}},
            {'id': 'google/lyria', 'name': 'Lyria', 'pricing': {'prompt': '0', 'completion': '0'}, 'supported_parameters': ['response_format'],
             'architecture': {'output_modalities': ['text', 'audio']}},
            {'id': 'openai/gpt-paid', 'name': 'Paid', 'pricing': {'prompt': '0.1', 'completion': '0.2'}, 'supported_parameters': ['response_format']},
            {'id': 'acme/no-json:free', 'name': 'No JSON', 'pricing': {'prompt': '0', 'completion': '0'}, 'supported_parameters': []}]}
        analysis_service._openrouter_cache.clear()
        with mock.patch.object(analysis_service.request, 'urlopen', return_value=Response(json.dumps(data).encode())):
            models, live = analysis_service.openrouter_free_models()
        analysis_service._openrouter_cache.clear()
        self.assertTrue(live)
        self.assertEqual([m['id'] for m in models], ['google/gemma:free'])


if __name__ == '__main__':
    unittest.main()
