import os
import shutil
import sqlite3
import tempfile
import unittest
from unittest import mock

import migrate_db
from models.fish import Fish, DATABASE

# Tests for migrate_db.py and for the committed data/fish.db
# Run from the project root: python -m unittest test_database -v

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

COLUMNS = migrate_db.FISH_COLUMNS


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
        migrate_db.migrate(self.legacy_path, self.target_path)
        migrated = read_rows_by_name(self.target_path)
        self.assertEqual(len(migrated), len(LEGACY_ROWS))
        for legacy_row in LEGACY_ROWS:
            with self.subTest(fish=legacy_row[0]):
                self.assertEqual(migrated[legacy_row[0]][1:], legacy_row)

    def test_ids_follow_scientific_name_order(self):
        migrate_db.migrate(self.legacy_path, self.target_path)
        migrated = read_rows_by_name(self.target_path)
        expected = {name: new_id for new_id, name in enumerate(sorted(row[0] for row in LEGACY_ROWS), start=1)}
        self.assertEqual({name: row[0] for name, row in migrated.items()}, expected)

    def test_reports_and_stores_latest_version(self):
        self.assertEqual(read_version(self.legacy_path), 0)
        self.assertEqual(migrate_db.migrate(self.legacy_path, self.target_path), 1)
        self.assertEqual(read_version(self.target_path), 1)

    def test_scientific_names_stay_unique(self):
        migrate_db.migrate(self.legacy_path, self.target_path)
        connection = sqlite3.connect(self.target_path)
        self.addCleanup(connection.close)
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute('INSERT INTO fish ({}) VALUES ({})'.format(', '.join(COLUMNS), ', '.join(['?'] * len(COLUMNS))),
                               LEGACY_ROWS[0])

    def test_id_of_a_removed_fish_is_never_reused(self):
        migrate_db.migrate(self.legacy_path, self.target_path)
        connection = sqlite3.connect(self.target_path)
        self.addCleanup(connection.close)
        connection.execute('DELETE FROM fish WHERE id = ?', (len(LEGACY_ROWS),))
        new_fish = ('Corydoras acrensis',) + LEGACY_ROWS[0][1:]
        cursor = connection.execute('INSERT INTO fish ({}) VALUES ({})'.format(', '.join(COLUMNS), ', '.join(['?'] * len(COLUMNS))),
                                    new_fish)
        self.assertEqual(cursor.lastrowid, len(LEGACY_ROWS) + 1)

    def test_migrating_an_up_to_date_database_changes_nothing(self):
        migrate_db.migrate(self.legacy_path, self.target_path)
        again_path = self.target_path + '.again'
        self.assertEqual(migrate_db.migrate(self.target_path, again_path), 1)
        self.assertEqual(read_rows_by_name(again_path), read_rows_by_name(self.target_path))

    def test_source_is_never_changed(self):
        before = read_bytes(self.legacy_path)
        migrate_db.migrate(self.legacy_path, self.target_path)
        self.assertEqual(read_bytes(self.legacy_path), before)

    def test_refuses_to_overwrite_an_existing_file(self):
        with open(self.target_path, 'wb') as existing_file:
            existing_file.write(b'keep me')
        before = read_bytes(self.legacy_path)
        for target in (self.target_path, self.legacy_path):
            with self.subTest(target=os.path.basename(target)):
                with self.assertRaises(Exception):
                    migrate_db.migrate(self.legacy_path, target)
        self.assertEqual(read_bytes(self.target_path), b'keep me')
        self.assertEqual(read_bytes(self.legacy_path), before)

    def test_failed_step_leaves_the_copy_at_its_previous_version(self):
        def failing_step(connection):
            migrate_db.upgrade_to_version_1(connection)
            raise RuntimeError('step failed')

        with mock.patch.dict(migrate_db.UPGRADE_STEPS, {1: failing_step}):
            with self.assertRaises(RuntimeError):
                migrate_db.migrate(self.legacy_path, self.target_path)
        connection = sqlite3.connect(self.target_path)
        self.addCleanup(connection.close)
        self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0], 0)
        self.assertEqual(connection.execute('SELECT name FROM sqlite_master WHERE type = ?', ('table',)).fetchall(),
                         [('fish',)])
        self.assertEqual(connection.execute('SELECT * FROM fish ORDER BY scientific_name').fetchall(), sorted(LEGACY_ROWS))


class CommittedDatabaseTest(unittest.TestCase):

    def test_is_at_latest_version(self):
        self.assertEqual(read_version(DATABASE), migrate_db.LATEST_VERSION)

    def test_ids_follow_scientific_name_order(self):
        rows = read_rows_by_name(DATABASE)
        self.assertEqual(len(rows), 743)
        expected = {name: new_id for new_id, name in enumerate(sorted(rows), start=1)}
        self.assertEqual({name: row[0] for name, row in rows.items()}, expected)


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
        self.assertEqual(set(dic), previous_keys | {'id'})
        self.assertEqual(dic['id'], fish.id)
        self.assertEqual(dic['scientific_name'], 'Corydoras acrensis')


if __name__ == '__main__':
    unittest.main()
