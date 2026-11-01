import os
import shutil
import sqlite3
import tempfile
import unittest
from datetime import timedelta

from fishtank import migrations
from fishtank.db import utcnow
from fishtank.models.fish import Fish
from fishtank.models.fishtank_record import FishtankRecord
from tests.api_test_case import ApiTestCase
from tests.test_migrations import LEGACY_ROWS, LEGACY_SCHEMA

# Tests for sharing a fishtank read only and copying fishtanks, and for schema versions 7 to 9
# Run from the project root: python -m unittest tests.test_sharing -v


class SharingTest(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.alice = self.register('alice')
        self.bob = self.register('bob')
        self.neon = Fish.get(Fish.scientific_name == 'Paracheirodon innesi')
        self.key = self.new_tank(self.alice, {'name': 'Living room'})
        self.operate('add', self.key, [self.neon.id] * 6, token=self.alice)

    def share(self, token=None):
        return self.call('POST', '/fishtanks/{}/share'.format(self.key), token=token or self.alice,
                         expected_status=200).get_json()['fishtank']['share_token']

    def test_shared_view_shows_the_tank_but_not_its_key(self):
        token = self.share()
        for viewer in (None, self.bob):
            with self.subTest(viewer=viewer):
                tank = self.call('GET', '/shared/' + token, token=viewer, expected_status=200).get_json()['fishtank']
                self.assertEqual((tank['name'], tank['owner'], tank['fish'][0]['count'], tank['stocking']['level']),
                                 ('Living room', 'alice', 6, 'comfortable'))
                self.assertNotIn('key', tank)
                self.assertNotIn(self.key, str(tank))
        # bob still cannot change it
        self.assertEqual(self.operate('add', self.key, [self.neon.id], token=self.bob).status_code, 404)

    def test_sharing_again_keeps_the_link_and_stopping_ends_it(self):
        token = self.share()
        self.assertEqual(self.share(), token)
        stopped = self.call('DELETE', '/fishtanks/{}/share'.format(self.key), token=self.alice, expected_status=200).get_json()
        self.assertIsNone(stopped['fishtank']['share_token'])
        self.call('GET', '/shared/' + token, expected_status=404)
        self.assertNotEqual(self.share(), token)

    def test_only_who_can_use_the_tank_shares_it(self):
        self.call('POST', '/fishtanks/{}/share'.format(self.key), token=self.bob, expected_status=404)
        self.call('POST', '/fishtanks/{}/share'.format(self.key), expected_status=404)
        self.call('GET', '/shared/not-a-token', expected_status=404)

    def test_expired_visitor_tank_is_not_shared(self):
        key = self.new_tank()
        token = self.call('POST', '/fishtanks/{}/share'.format(key), expected_status=200).get_json()['fishtank']['share_token']
        FishtankRecord.update(expires_at=utcnow() - timedelta(seconds=1)).where(FishtankRecord.key == key).execute()
        self.call('GET', '/shared/' + token, expected_status=404)

    def test_copy_of_a_shared_tank(self):
        token = self.share()
        copied = self.call('POST', '/shared/{}/copy'.format(token), token=self.bob, expected_status=201).get_json()
        tank = copied['fishtank']
        self.assertNotEqual(tank['key'], self.key)
        self.assertEqual((tank['name'], tank['saved'], tank['fish'][0]['count'], tank['share_token'], copied['skipped']),
                         ('Living room', True, 6, None, []))
        self.assertEqual([t['key'] for t in self.call('GET', '/fishtanks', token=self.bob).get_json()['fishtanks']], [tank['key']])
        # the copy is bob's own, changing it leaves alice's alone
        self.operate('remove', tank['key'], [self.neon.id], token=self.bob)
        self.assertEqual(self.fish_in_tank(self.key, self.alice), {self.neon.id: 6})
        visitor = self.call('POST', '/shared/{}/copy'.format(token), expected_status=201).get_json()['fishtank']
        self.assertEqual((visitor['saved'], visitor['expires_at'] is not None), (False, True))

    def test_copy_of_your_own_tank_leaves_retired_fish_out(self):
        admin = self.register_admin()
        cory = Fish.get(Fish.scientific_name == 'Corydoras adolfoi')
        self.operate('add', self.key, [cory.id], token=self.alice)
        self.call('POST', '/fish/{}/retire'.format(cory.id), token=admin)
        copied = self.call('POST', '/fishtanks/{}/copy'.format(self.key), token=self.alice, expected_status=201).get_json()
        self.assertEqual([entry['id'] for entry in copied['fishtank']['fish']], [self.neon.id])
        self.assertEqual([fish['id'] for fish in copied['skipped']], [cory.id])
        self.call('POST', '/fishtanks/{}/copy'.format(self.key), token=self.bob, expected_status=404)


class SchemaTest(unittest.TestCase):

    def test_versions_7_to_9_on_a_legacy_database(self):
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory)
        legacy = os.path.join(directory, 'legacy.db')
        connection = sqlite3.connect(legacy)
        connection.execute(LEGACY_SCHEMA)
        connection.executemany('INSERT INTO fish VALUES ({})'.format(', '.join(['?'] * len(LEGACY_ROWS[0]))), LEGACY_ROWS)
        connection.commit()
        connection.close()
        target = os.path.join(directory, 'target.db')
        self.assertEqual(migrations.migrate(legacy, target), 9)
        connection = sqlite3.connect(target)
        self.addCleanup(connection.close)
        connection.execute('PRAGMA foreign_keys = ON')
        connection.execute("INSERT INTO fish_picture (fish_id, url, licence, source_url) VALUES (1, 'https://x/1.jpg', 'CC0', 'https://x')")
        self.assertEqual(connection.execute('SELECT source FROM fish_picture').fetchone(), ('FishBase',))
        suggestion = ("INSERT INTO temperament_suggestion (fish_id, in_species_temperament, cross_species_temperament, status, created_at) "
                      "VALUES (1, 'peaceful', 'peaceful', ?, '2026-01-01')")
        connection.execute(suggestion, ('pending',))
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(suggestion, ('maybe',))
        connection.execute("INSERT INTO fishtank (key, length, width, height, created_at, updated_at, share_token) "
                           "VALUES ('a', 1, 1, 1, '2026-01-01', '2026-01-01', 'shared')")
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO fishtank (key, length, width, height, created_at, updated_at, share_token) "
                               "VALUES ('b', 1, 1, 1, '2026-01-01', '2026-01-01', 'shared')")
        connection.execute("INSERT INTO audit_event (action, created_at) VALUES ('fish.update', '2026-01-01')")
        # removing a fish removes the suggestions for it
        connection.execute('DELETE FROM fish_picture')
        connection.execute('DELETE FROM fish WHERE id = 1')
        self.assertEqual(connection.execute('SELECT count(*) FROM temperament_suggestion').fetchone(), (0,))


if __name__ == '__main__':
    unittest.main()
