import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from api import app


class APITests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_static_frontend_and_periods(self):
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('훈장님', r.text)
        self.assertEqual(self.client.get('/assets/images/teacher-v1.png').status_code, 200)
        self.assertEqual(len(self.client.get('/api/periods').json()), 542)
        self.assertEqual(self.client.get('/assets/app.js').status_code, 200)

    def test_cross_origin_request_cannot_spend_credits(self):
        response = self.client.post('/api/questions', json={'question': '질문'}, headers={'Origin': 'https://example.org', 'X-History-Client': 'annals-local'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.post('/api/questions', json={'question': '질문'}).status_code, 403)

    def test_missing_key_and_invalid_period_preserve_safe_errors(self):
        headers = {'X-History-Client': 'annals-local'}
        with patch.dict(os.environ, {'GMS_KEY': ''}), patch('api.settings', return_value={}):
            self.assertEqual(self.client.post('/api/questions', json={'question': '질문'}, headers=headers).status_code, 503)
        self.assertEqual(self.client.post('/api/questions', json={'question': '질문', 'period_id': 'invented'}, headers=headers).status_code, 422)
        self.assertEqual(self.client.post('/api/questions', json={'question': ' '}, headers=headers).status_code, 422)
        self.assertEqual(self.client.get('/api/jobs/missing').status_code, 404)


if __name__ == '__main__':
    unittest.main()
