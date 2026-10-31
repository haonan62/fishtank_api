import os
import shutil
import sqlite3
import tempfile
import unittest
from unittest import mock

from fishtank import migrations
from fishtank.models.fish import Fish, FishPicture, DATABASE

# Tests for fishtank/migrations.py and for the committed data/fish.db
# Run from the project root: python -m unittest tests.test_migrations -v

# The fish table exactly as it was before version 1, keyed by scientific name
LEGACY_SCHEMA = '''CREATE TABLE fish(
    scientific_name char(100) PRIMARY KEY not null,
    common_name char(100),
    family_name char(50) not null,
    size_min int not null,
    size_max int not null,
    ph_min double not null,
    ph_max double not null,
    water_hardness_min int not null,
    water_hardness_max int not null,
    temperature_min int not null,
    temperature_max int not null,
    reproduce_method char(20) not null,
    origin char(36) not null,
    in_species_temperament char(36) not null,
    cross_species_temperament char(36) not null,
    fishtank_position char(20) not null

)'''

# inserted out of alphabetical order on purpose, one fish has no common name
LEGACY_ROWS = [
    ('Corydoras adolfoi', 'Adolfo\'s catfish', 'Callichthyidae', 4, 5, 6.0, 7.5, 2, 12, 22, 26,
     'Spawning', 'South America', 'peaceful', 'peaceful', 'Bottom levels'),
    ('Ancistrus sp. L182', None, 'Loricariidae', 10, 12, 6.0, 7.5, 5, 15, 24, 28,
     'Spawning', 'South America', 'peaceful', 'peaceful', 'Bottom levels'),
    ('Cynotilapia afra', 'Dogtooth cichlid', 'Cichlidae', 8, 10, 7.5, 8.5, 10, 20, 23, 27,
     'Spawning', 'Africa', 'peaceful to females', 'aggressive/territorial', 'Middle levels'),
    ('Blood parrot cichlid', 'Blood parrot', 'Cichlidae', 15, 20, 6.5, 7.4, 6, 15, 24, 27,
     'Spawning', 'Hybrid', 'peaceful', 'aggressive to smaller', 'Middle levels'),
]

COLUMNS = migrations.FISH_COLUMNS


def read_rows_by_name(path):
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute('SELECT id, {} FROM fish'.format(', '.join(COLUMNS))).fetchall()
    finally:
        connection.close()
    return {row[1]: row for row in rows}


def read_version(path):
    connection = sqlite3.connect(path)
    try:
        return connection.execute('PRAGMA user_version').fetchone()[0]
    finally:
        connection.close()


def insert_columns(connection, row):
    columns = sorted(row)
    return connection.execute('INSERT INTO fish ({}) VALUES ({})'.format(', '.join(columns), ', '.join(['?'] * len(columns))),
                              [row[column] for column in columns])


# inserts a legacy row with every column the latest schema requires
def insert_complete_fish(connection, legacy_row):
    row = dict(zip(COLUMNS, legacy_row))
    row['data_source'] = 'aqua-fish.net'
    return insert_columns(connection, row)


def read_bytes(path):
    with open(path, 'rb') as database_file:
        return database_file.read()


class MigrationTest(unittest.TestCase):

    def setUp(self):
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory)
        self.legacy_path = os.path.join(directory, 'legacy.db')
        self.target_path = os.path.join(directory, 'migrated.db')
        connection = sqlite3.connect(self.legacy_path)
        connection.execute(LEGACY_SCHEMA)
        connection.executemany('INSERT INTO fish VALUES ({})'.format(', '.join(['?'] * len(COLUMNS))), LEGACY_ROWS)
        connection.commit()
        connection.close()

    def test_every_value_is_preserved(self):
        migrations.migrate(self.legacy_path, self.target_path)
        migrated = read_rows_by_name(self.target_path)
        self.assertEqual(len(migrated), len(LEGACY_ROWS))
        for legacy_row in LEGACY_ROWS:
            with self.subTest(fish=legacy_row[0]):
                self.assertEqual(migrated[legacy_row[0]][1:], legacy_row)

    def test_ids_follow_scientific_name_order(self):
        migrations.migrate(self.legacy_path, self.target_path)
        migrated = read_rows_by_name(self.target_path)
        expected = {name: new_id for new_id, name in enumerate(sorted(row[0] for row in LEGACY_ROWS), start=1)}
        self.assertEqual({name: row[0] for name, row in migrated.items()}, expected)

    def test_reports_and_stores_latest_version(self):
        self.assertEqual(read_version(self.legacy_path), 0)
        self.assertEqual(migrations.migrate(self.legacy_path, self.target_path), migrations.LATEST_VERSION)
        self.assertEqual(read_version(self.target_path), migrations.LATEST_VERSION)

    def test_scientific_names_stay_unique(self):
        migrations.migrate(self.legacy_path, self.target_path)
        connection = sqlite3.connect(self.target_path)
        self.addCleanup(connection.close)
        with self.assertRaises(sqlite3.IntegrityError) as raised:
            insert_complete_fish(connection, LEGACY_ROWS[0])
        self.assertIn('UNIQUE', str(raised.exception))

    def test_id_of_a_removed_fish_is_never_reused(self):
        migrations.migrate(self.legacy_path, self.target_path)
        connection = sqlite3.connect(self.target_path)
        self.addCleanup(connection.close)
        connection.execute('DELETE FROM fish WHERE id = ?', (len(LEGACY_ROWS),))
        cursor = insert_complete_fish(connection, ('Corydoras acrensis',) + LEGACY_ROWS[0][1:])
        self.assertEqual(cursor.lastrowid, len(LEGACY_ROWS) + 1)

    def test_id_removed_before_version_2_is_never_reused_after_it(self):
        version_1_path = self.target_path + '.v1'
        with mock.patch.object(migrations, 'LATEST_VERSION', 1):
            migrations.migrate(self.legacy_path, version_1_path)
        connection = sqlite3.connect(version_1_path)
        connection.execute('DELETE FROM fish WHERE id = ?', (len(LEGACY_ROWS),))
        connection.commit()
        connection.close()

        migrations.migrate(version_1_path, self.target_path)
        connection = sqlite3.connect(self.target_path)
        self.addCleanup(connection.close)
        cursor = insert_complete_fish(connection, ('Corydoras acrensis',) + LEGACY_ROWS[0][1:])
        self.assertEqual(cursor.lastrowid, len(LEGACY_ROWS) + 1)

    def test_version_2_makes_attributes_fishbase_lacks_optional(self):
        migrations.migrate(self.legacy_path, self.target_path)
        connection = sqlite3.connect(self.target_path)
        self.addCleanup(connection.close)
        connection.execute('''INSERT INTO fish (scientific_name, family_name, ph_min, ph_max, water_hardness_min,
            water_hardness_max, temperature_min, temperature_max, in_species_temperament, cross_species_temperament,
            fishbase_spec_code, data_source) VALUES ('Ameca splendens', 'Goodeidae', 6.0, 8.0, 9, 19, 26, 32,
            'unknown', 'unknown', 6228, 'FishBase 25.04')''')
        for missing_column in ('ph_min', 'temperature_max', 'water_hardness_min', 'in_species_temperament', 'data_source'):
            with self.subTest(required=missing_column):
                row = dict(zip(COLUMNS, ('Aphyocharax erythrurus',) + LEGACY_ROWS[0][1:]))
                row['data_source'] = 'FishBase 25.04'
                row[missing_column] = None
                with self.assertRaises(sqlite3.IntegrityError):
                    insert_columns(connection, row)

    def test_version_2_records_the_source_of_existing_fish(self):
        migrations.migrate(self.legacy_path, self.target_path)
        connection = sqlite3.connect(self.target_path)
        self.addCleanup(connection.close)
        self.assertEqual(connection.execute('SELECT DISTINCT data_source, fishbase_spec_code FROM fish').fetchall(),
                         [('aqua-fish.net', None)])
        self.assertEqual(connection.execute('SELECT count(*) FROM fish_picture').fetchone()[0], 0)

    def test_fishbase_species_code_and_picture_url_are_unique(self):
        migrations.migrate(self.legacy_path, self.target_path)
        connection = sqlite3.connect(self.target_path)
        self.addCleanup(connection.close)
        connection.execute('UPDATE fish SET fishbase_spec_code = 2001 WHERE id = 1')
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute('UPDATE fish SET fishbase_spec_code = 2001 WHERE id = 2')
        picture = "INSERT INTO fish_picture (fish_id, url, licence, source_url) VALUES (1, 'https://www.fishbase.se/images/species/Coado_u0.jpg', 'free use', 'https://www.fishbase.se/summary/2001')"
        connection.execute(picture)
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(picture)

    def test_migrating_an_up_to_date_database_changes_nothing(self):
        migrations.migrate(self.legacy_path, self.target_path)
        again_path = self.target_path + '.again'
        self.assertEqual(migrations.migrate(self.target_path, again_path), migrations.LATEST_VERSION)
        self.assertEqual(read_rows_by_name(again_path), read_rows_by_name(self.target_path))

    def test_upgrade_in_place_runs_each_step_once(self):
        shutil.copyfile(self.legacy_path, self.target_path)
        self.assertEqual(migrations.upgrade(self.target_path), migrations.LATEST_VERSION)
        before = read_bytes(self.target_path)
        self.assertEqual(migrations.upgrade(self.target_path), migrations.LATEST_VERSION)
        self.assertEqual(read_bytes(self.target_path), before)

    def test_version_3_adds_users_and_fishtanks(self):
        migrations.migrate(self.legacy_path, self.target_path)
        connection = sqlite3.connect(self.target_path)
        self.addCleanup(connection.close)
        connection.execute('PRAGMA foreign_keys = ON')
        user = "INSERT INTO user (username, password_hash, role, created_at) VALUES (?, 'hash', ?, '2026-01-01')"
        connection.execute(user, ('alice', 'user'))
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(user, ('ALICE', 'user'))
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(user, ('bob', 'owner'))
        connection.execute("INSERT INTO fishtank (key, owner_id, length, width, height, created_at, updated_at) VALUES ('k', 1, 1, 1, 1, '2026-01-01', '2026-01-01')")
        connection.execute('INSERT INTO fishtank_fish (fishtank_id, fish_id, count) VALUES (1, 1, 2)')
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute('INSERT INTO fishtank_fish (fishtank_id, fish_id, count) VALUES (1, 2, 0)')
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute('INSERT INTO fishtank_fish (fishtank_id, fish_id, count) VALUES (1, 999, 1)')
        # a fish living in a fishtank cannot be removed
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute('DELETE FROM fish WHERE id = 1')
        # removing a user removes their fishtanks and the fish in them
        connection.execute('DELETE FROM user')
        self.assertEqual(connection.execute('SELECT count(*) FROM fishtank_fish').fetchone(), (0,))

    def test_source_is_never_changed(self):
        before = read_bytes(self.legacy_path)
        migrations.migrate(self.legacy_path, self.target_path)
        self.assertEqual(read_bytes(self.legacy_path), before)

    def test_refuses_to_overwrite_an_existing_file(self):
        with open(self.target_path, 'wb') as existing_file:
            existing_file.write(b'keep me')
        before = read_bytes(self.legacy_path)
        for target in (self.target_path, self.legacy_path):
            with self.subTest(target=os.path.basename(target)):
                with self.assertRaises(Exception):
                    migrations.migrate(self.legacy_path, target)
        self.assertEqual(read_bytes(self.target_path), b'keep me')
        self.assertEqual(read_bytes(self.legacy_path), before)

    def test_failed_step_leaves_the_copy_at_its_previous_version(self):
        def failing_step(connection):
            migrations.upgrade_to_version_1(connection)
            raise RuntimeError('step failed')

        with mock.patch.dict(migrations.UPGRADE_STEPS, {1: failing_step}):
            with self.assertRaises(RuntimeError):
                migrations.migrate(self.legacy_path, self.target_path)
        connection = sqlite3.connect(self.target_path)
        self.addCleanup(connection.close)
        self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0], 0)
        self.assertEqual(connection.execute('SELECT name FROM sqlite_master WHERE type = ?', ('table',)).fetchall(),
                         [('fish',)])
        self.assertEqual(connection.execute('SELECT * FROM fish ORDER BY scientific_name').fetchall(), sorted(LEGACY_ROWS))


class CommittedDatabaseTest(unittest.TestCase):

    def test_is_at_latest_version(self):
        self.assertEqual(read_version(DATABASE), migrations.LATEST_VERSION)

    def read(self, sql):
        connection = sqlite3.connect(DATABASE)
        try:
            return connection.execute(sql).fetchall()
        finally:
            connection.close()

    def test_aqua_fish_ids_follow_scientific_name_order(self):
        rows = self.read("SELECT id, scientific_name FROM fish WHERE data_source = 'aqua-fish.net'")
        self.assertEqual(len(rows), 743)
        expected = {name: new_id for new_id, name in enumerate(sorted(name for _, name in rows), start=1)}
        self.assertEqual({name: fish_id for fish_id, name in rows}, expected)

    def test_fishbase_fish_follow_in_scientific_name_order(self):
        rows = self.read("SELECT id, scientific_name FROM fish WHERE data_source = 'FishBase 25.04' ORDER BY id")
        self.assertEqual(len(rows), 297)
        self.assertEqual([fish_id for fish_id, _ in rows], list(range(744, 744 + 297)))
        self.assertEqual([name for _, name in rows], sorted(name for _, name in rows))

    def test_fishbase_fish_have_unknown_temperament_and_a_species_code(self):
        self.assertEqual(self.read("SELECT DISTINCT in_species_temperament, cross_species_temperament, fishbase_spec_code IS NULL FROM fish WHERE data_source = 'FishBase 25.04'"),
                         [('unknown', 'unknown', 0)])

    def test_no_other_source_or_temperament_is_present(self):
        self.assertEqual(self.read('SELECT DISTINCT data_source FROM fish ORDER BY 1'), [('FishBase 25.04',), ('aqua-fish.net',)])
        self.assertEqual(self.read("SELECT count(*) FROM fish WHERE data_source = 'aqua-fish.net' AND 'unknown' IN (in_species_temperament, cross_species_temperament)"),
                         [(0,)])

    def test_every_picture_is_a_reusable_fishbase_photo_of_a_known_fish(self):
        self.assertEqual(self.read('SELECT count(*) FROM fish_picture WHERE fish_id NOT IN (SELECT id FROM fish)'), [(0,)])
        self.assertEqual(self.read("SELECT count(*) FROM fish_picture WHERE url NOT LIKE 'https://www.fishbase.se/images/species/%' OR source_url NOT LIKE 'https://www.fishbase.se/summary/%'"),
                         [(0,)])
        self.assertEqual(set(self.read('SELECT DISTINCT licence FROM fish_picture')),
                         {('free use',), ('non-commercial use',), ('public domain',)})


class FishModelTest(unittest.TestCase):

    def test_fish_can_be_found_by_id_and_by_scientific_name(self):
        by_name = Fish.get(Fish.scientific_name == 'Corydoras acrensis')
        self.assertIsInstance(by_name.id, int)
        self.assertEqual(Fish.get_by_id(by_name.id).scientific_name, 'Corydoras acrensis')

    def test_to_dic_adds_id_to_previous_keys(self):
        fish = Fish.get(Fish.scientific_name == 'Corydoras acrensis')
        previous_keys = {'scientific_name', 'common_name', 'family_name', 'minimum_size', 'maximum_size', 'minimum_ph',
                         'maximum_ph', 'minimum_water_hardness', 'maximum_water_hardness', 'minimum_temperature',
                         'maximum_temperature', 'reproduce_method', 'origin', 'in_species_temperament',
                         'cross_species_temperament', 'fishtank_position'}
        dic = fish.to_dic()
        self.assertEqual(set(dic), previous_keys | {'id', 'data_source', 'fishbase_spec_code', 'fishbase_url', 'retired', 'pictures'})
        self.assertEqual(dic['id'], fish.id)
        self.assertEqual(dic['data_source'], 'aqua-fish.net')
        self.assertIsNotNone(fish.fishbase_spec_code)
        self.assertEqual(dic['fishbase_url'], 'https://www.fishbase.se/summary/{}'.format(fish.fishbase_spec_code))
        self.assertEqual(dic['scientific_name'], 'Corydoras acrensis')

    def test_fish_without_species_code_has_no_fishbase_url(self):
        self.assertIsNone(Fish(scientific_name='Blood parrot cichlid').fishbase_url())

    def test_to_dic_lists_pictures_with_fishbase_credit(self):
        picture = FishPicture.select().where(FishPicture.author.is_null(False)).order_by(FishPicture.id).get()
        dic = picture.fish.to_dic()
        self.assertIn({'url': picture.url, 'author': picture.author, 'licence': picture.licence,
                       'credit': picture.author + ', from FishBase', 'source_url': picture.source_url}, dic['pictures'])
        self.assertEqual(FishPicture(author=None).credit(), 'from FishBase')


if __name__ == '__main__':
    unittest.main()
