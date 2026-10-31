import os
import shutil
import tempfile
import unittest

from fishtank import create_app
from fishtank.db import SEED_DATABASE, use_database
from fishtank.models.user import ROLE_ADMIN, User

# The base of the http api tests, every test runs the app on its own copy of data/fish.db

PREFIX = '/fishtank_api'


class ApiTestCase(unittest.TestCase):

    def setUp(self):
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory)
        self.app = create_app(os.path.join(directory, 'fishtank.db'))
        # other test modules read the committed database
        self.addCleanup(use_database, SEED_DATABASE)
        self.client = self.app.test_client()

    def call(self, method, path, json=None, token=None, expected_status=None):
        headers = {'Authorization': 'Bearer ' + token} if token else {}
        response = self.client.open(PREFIX + path, method=method, json=json, headers=headers)
        if expected_status is not None:
            self.assertEqual(response.status_code, expected_status, response.get_json())
        return response

    def register(self, username='alice', password='correct horse'):
        return self.call('POST', '/auth/register', {'username': username, 'password': password},
                         expected_status=201).get_json()['token']

    def register_admin(self, username='admin'):
        token = self.register(username)
        User.update(role=ROLE_ADMIN).where(User.username == username).execute()
        return token

    def new_tank(self, token=None, json=None):
        response = self.call('POST', '/fishtanks', json, token=token, expected_status=201).get_json()
        return response['fishtank']['key']

    def operate(self, action, tank_key, fish, token=None):
        return self.call('POST', '/fishtanks/{}/{}'.format(tank_key, action), {'fish': fish}, token=token)

    def fish_in_tank(self, tank_key, token=None):
        tank = self.call('GET', '/fishtanks/' + tank_key, token=token, expected_status=200).get_json()['fishtank']
        return {entry['id']: entry['count'] for entry in tank['fish']}
