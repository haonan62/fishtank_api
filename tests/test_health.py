from unittest import mock

from peewee import OperationalError

from fishtank.db import database
from tests.api_test_case import ApiTestCase


class HealthTest(ApiTestCase):

    def test_both_answer_without_a_login(self):
        for path in ('/healthz', '/readyz'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json(), {'status': 'success'})
            self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_a_database_that_cannot_be_read_only_fails_readiness(self):
        with mock.patch.object(database, 'connect', side_effect=OperationalError('disk I/O error')):
            self.assertEqual(self.client.get('/healthz').status_code, 200)
            response = self.client.get('/readyz')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()['status'], 'error')
        self.assertNotIn('disk', response.get_data(as_text=True))

    def test_an_expired_cookie_does_not_matter_to_monitoring(self):
        response = self.client.get('/healthz', headers={'Authorization': 'Bearer wrong'})
        self.assertEqual(response.status_code, 200)
