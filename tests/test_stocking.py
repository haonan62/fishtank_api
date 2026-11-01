import os
import shutil
import sqlite3
import tempfile
import unittest

from fishtank import migrations
from fishtank.db import SEED_DATABASE
from fishtank.models.fish import Fish
from fishtank.simulation import stocking
from tests.api_test_case import ApiTestCase
from tests.test_accounts import NEW_FISH
from tests.test_fishtank import make_fish

# Tests for stocking and schooling: how crowded a tank is, groups of schooling fish, room to swim,
# and the curated group sizes of schema version 6
# Run from the project root: python -m unittest tests.test_stocking -v

# 100 x 100 x 30 cm: 300 litres, 255 litres of water, room for about 171 cm of adult fish
DEFAULT_SIZE = (100, 100, 30)


def fish(name, size_max=5, group=None, fish_id=1, common_name=None):
    entry = make_fish(name, size=(max(1, size_max - 1), size_max))
    entry.id = fish_id
    entry.common_name = common_name
    entry.minimum_group_size = group
    return entry


class AssessStockingTest(unittest.TestCase):

    def test_volume_and_capacity(self):
        result = stocking.assess_stocking(DEFAULT_SIZE, [])
        self.assertEqual((result['litres'], result['net_litres']), (300.0, 255.0))
        self.assertAlmostEqual(result['capacity_cm'], 255 * 2.54 / 3.785, places=1)
        self.assertEqual((result['fish_cm'], result['level'], result['uncounted_fish']), (0, 'empty', 0))

    def test_counts_adult_size_times_number(self):
        result = stocking.assess_stocking(DEFAULT_SIZE, [(fish('A', 4), 10), (fish('B', 12, fish_id=2), 2)])
        self.assertEqual(result['fish_cm'], 64)
        self.assertEqual(result['level'], 'comfortable')

    def test_levels(self):
        capacity = stocking.assess_stocking(DEFAULT_SIZE, [])['capacity_cm']
        for share, level in ((0.5, 'comfortable'), (0.8, 'nearly full'), (1.0, 'nearly full'), (1.01, 'overstocked')):
            with self.subTest(share=share):
                self.assertEqual(stocking.stocking_level(share, True), level)
        crowded = stocking.assess_stocking(DEFAULT_SIZE, [(fish('A', 10), int(capacity // 10) + 1)])
        self.assertEqual(crowded['level'], 'overstocked')

    def test_fish_without_size_are_counted_apart(self):
        unknown = fish('Unknown')
        unknown.size_max = None
        result = stocking.assess_stocking(DEFAULT_SIZE, [(unknown, 3), (fish('A', 4, fish_id=2), 1)])
        self.assertEqual((result['fish_cm'], result['uncounted_fish']), (4, 3))


class WarningsTest(unittest.TestCase):

    def warnings(self, residents, size=DEFAULT_SIZE):
        return stocking.tank_warnings(size, residents, stocking.assess_stocking(size, residents))

    def test_schooling_fish_below_its_group(self):
        neon = fish('Paracheirodon innesi', 3, group=6, common_name='Neon tetra')
        [warning] = self.warnings([(neon, 2)])
        self.assertEqual((warning['kind'], warning['count'], warning['minimum'], warning['fish_id']), ('group', 2, 6, 1))
        self.assertIn('Neon tetra', warning['message'])
        self.assertEqual(self.warnings([(neon, 6)]), [])

    def test_fish_without_group_size_never_warn(self):
        self.assertEqual(self.warnings([(fish('Solitary', 5), 1)]), [])

    def test_short_tank_for_a_large_fish(self):
        big = fish('Astronotus ocellatus', 35)
        [warning] = self.warnings([(big, 1)], size=(100, 50, 50))
        self.assertEqual((warning['kind'], warning['minimum_length']), ('room', 140))
        self.assertEqual(self.warnings([(big, 1)], size=(140, 50, 50)), [])

    def test_overstocked_comes_first(self):
        neon = fish('Paracheirodon innesi', 3, group=6)
        warnings = self.warnings([(neon, 2), (fish('Big', 30, fish_id=2), 10)], size=(60, 30, 30))
        self.assertEqual([warning['kind'] for warning in warnings], ['overstocked', 'group', 'room'])


class TankAnswerTest(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.neon = Fish.get(Fish.scientific_name == 'Paracheirodon innesi')

    def tank(self, key):
        return self.call('GET', '/fishtanks/' + key, expected_status=200).get_json()['fishtank']

    def test_new_tank_is_empty(self):
        tank = self.tank(self.new_tank())
        self.assertEqual((tank['stocking']['level'], tank['stocking']['litres'], tank['warnings']), ('empty', 300.0, []))

    def test_group_warning_until_the_school_is_complete(self):
        key = self.new_tank()
        tank = self.operate('add', key, [self.neon.id, self.neon.id]).get_json()['fishtank']
        self.assertEqual([(w['kind'], w['count'], w['minimum']) for w in tank['warnings']], [('group', 2, 6)])
        tank = self.operate('add', key, [self.neon.id] * 4).get_json()['fishtank']
        self.assertEqual(tank['warnings'], [])
        self.assertEqual(tank['stocking']['fish_cm'], 6 * self.neon.size_max)

    def test_warnings_never_block_adding(self):
        key = self.new_tank(json={'size': {'length': 20, 'width': 20, 'height': 20}})
        response = self.operate('add', key, [self.neon.id] * 40)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['fishtank']['stocking']['level'], 'overstocked')

    def test_saved_tank_list_carries_warnings(self):
        token = self.register('alice')
        key = self.new_tank(token)
        self.operate('add', key, [self.neon.id], token=token)
        [tank] = self.call('GET', '/fishtanks', token=token).get_json()['fishtanks']
        self.assertEqual(tank['warnings'][0]['kind'], 'group')


class GroupSizeAdminTest(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.register_admin()
        self.neon = Fish.get(Fish.scientific_name == 'Paracheirodon innesi')

    def patch(self, fish_id, payload, expected_status=200):
        return self.call('PATCH', '/fish/{}'.format(fish_id), payload, token=self.admin, expected_status=expected_status).get_json()

    def test_curated_value_is_shown_with_its_source(self):
        dic = self.call('GET', '/fish/{}'.format(self.neon.id)).get_json()['fish']
        self.assertEqual((dic['minimum_group_size'], dic['group_size_source']), (6, 'Fishtank list'))

    def test_admin_change_becomes_manual(self):
        changed = self.patch(self.neon.id, {'minimum_group_size': 10})['fish']
        self.assertEqual((changed['minimum_group_size'], changed['group_size_source']), (10, 'manual entry'))
        cleared = self.patch(self.neon.id, {'minimum_group_size': None})['fish']
        self.assertEqual((cleared['minimum_group_size'], cleared['group_size_source']), (None, None))

    def test_other_changes_keep_the_source(self):
        changed = self.patch(self.neon.id, {'common_name': 'Neon'})['fish']
        self.assertEqual(changed['group_size_source'], 'Fishtank list')
        self.assertEqual(self.patch(self.neon.id, {'minimum_group_size': 6})['fish']['group_size_source'], 'Fishtank list')

    def test_invalid_group_sizes(self):
        for value in (1, 51, 'six', 6.5, True):
            with self.subTest(value=value):
                self.assertEqual(self.patch(self.neon.id, {'minimum_group_size': value}, 400)['field'], 'minimum_group_size')
        self.assertEqual(self.patch(self.neon.id, {'group_size_source': 'me'}, 400)['field'], 'group_size_source')

    def test_only_fish_peaceful_with_their_kind_get_a_group(self):
        answer = self.patch(self.neon.id, {'in_species_temperament': 'aggressive/territorial'}, 400)
        self.assertEqual(answer['field'], 'minimum_group_size')
        self.patch(self.neon.id, {'in_species_temperament': 'aggressive/territorial', 'minimum_group_size': None})
        created = self.call('POST', '/fish', dict(NEW_FISH, minimum_group_size=8), token=self.admin, expected_status=201)
        self.assertEqual(created.get_json()['fish']['group_size_source'], 'manual entry')
        unknown = dict(NEW_FISH, scientific_name='Testus solus', cross_species_temperament='unknown', minimum_group_size=6)
        self.call('POST', '/fish', unknown, token=self.admin, expected_status=400)


class CuratedGroupSizeTest(unittest.TestCase):

    def read(self, sql, path=SEED_DATABASE):
        connection = sqlite3.connect(path)
        try:
            return connection.execute(sql).fetchall()
        finally:
            connection.close()

    def test_committed_database_has_the_curated_values(self):
        rows = self.read('SELECT scientific_name, in_species_temperament, cross_species_temperament, minimum_group_size, '
                         'group_size_source FROM fish WHERE minimum_group_size IS NOT NULL')
        self.assertEqual(len(rows), 227)
        for name, in_species, cross_species, size, source in rows:
            self.assertIn(name.split()[0], migrations.SCHOOLING_GENERA)
            self.assertEqual((in_species, size, source), ('peaceful', 6, 'Fishtank list'))
            self.assertNotEqual(cross_species, 'unknown')

    def test_known_fish(self):
        sizes = dict(self.read("SELECT scientific_name, minimum_group_size FROM fish WHERE scientific_name IN "
                               "('Paracheirodon innesi', 'Danio rerio', 'Pterophyllum scalare', 'Puntius tetrazona')"))
        self.assertEqual(sizes, {'Paracheirodon innesi': 6, 'Danio rerio': 6, 'Pterophyllum scalare': None,
                                 'Puntius tetrazona': None})

    def test_step_on_a_version_5_copy(self):
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory)
        path = os.path.join(directory, 'fish.db')
        shutil.copyfile(SEED_DATABASE, path)
        connection = sqlite3.connect(path)
        # the fish as version 5 had them: no group size columns yet, then only the version 6 step
        connection.execute('ALTER TABLE fish DROP COLUMN group_size_source')
        connection.execute('ALTER TABLE fish DROP COLUMN minimum_group_size')
        migrations.upgrade_to_version_6(connection)
        connection.commit()
        connection.close()
        self.assertEqual(self.read('SELECT count(*) FROM fish WHERE minimum_group_size = 6', path), [(227,)])
        with self.assertRaises(sqlite3.IntegrityError):
            connection = sqlite3.connect(path)
            self.addCleanup(connection.close)
            connection.execute('UPDATE fish SET minimum_group_size = 1 WHERE id = 1')


if __name__ == '__main__':
    unittest.main()
