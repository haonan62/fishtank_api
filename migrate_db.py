import os
import shutil
import sqlite3
import sys

# Upgrades a copy of the fish database to the latest schema, the source file is never changed
# The schema version is kept in sqlite's user_version, each upgrade step runs only once,
# so migrating an up to date database just copies it
# Usage: python migrate_db.py data/fish.db data/fish_migrated.db

LATEST_VERSION = 2

FISH_COLUMNS = ['scientific_name', 'common_name', 'family_name', 'size_min', 'size_max', 'ph_min', 'ph_max',
                'water_hardness_min', 'water_hardness_max', 'temperature_min', 'temperature_max', 'reproduce_method',
                'origin', 'in_species_temperament', 'cross_species_temperament', 'fishtank_position']


# Version 1: every fish gets a stable integer id as primary key, scientific names stay unique but are now
# an ordinary attribute, so a species can be renamed without changing its identity
# Ids follow the order of scientific names, so the same data always gets the same ids
# AUTOINCREMENT makes sure the id of a removed fish is never handed to another fish
def upgrade_to_version_1(connection):
    connection.execute('''CREATE TABLE fish_new(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scientific_name char(100) not null unique,
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
)''')
    column_list = ', '.join(FISH_COLUMNS)
    rows = connection.execute('SELECT {} FROM fish ORDER BY scientific_name'.format(column_list)).fetchall()
    connection.executemany('INSERT INTO fish_new (id, {}) VALUES ({})'.format(column_list, ', '.join(['?'] * (len(FISH_COLUMNS) + 1))),
                           [(new_id,) + tuple(row) for new_id, row in enumerate(rows, start=1)])
    connection.execute('DROP TABLE fish')
    connection.execute('ALTER TABLE fish_new RENAME TO fish')


# Version 2: prepares for fish from other sources, which do not describe every attribute
# Attributes FishBase does not provide become optional, the water parameters and temperaments stay required
# Every fish records where its data comes from and, when known, its FishBase species code
# Pictures are not stored, only the url where they are hosted, with author, licence and source page for attribution
# Sqlite cannot drop a not null constraint, so the fish table is rebuilt, keeping every id and the id sequence
def upgrade_to_version_2(connection):
    sequence_row = connection.execute("SELECT seq FROM sqlite_sequence WHERE name = 'fish'").fetchone()
    connection.execute('''CREATE TABLE fish_new(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scientific_name char(100) not null unique,
    common_name char(100),
    family_name char(50) not null,
    size_min int,
    size_max int,
    ph_min double not null,
    ph_max double not null,
    water_hardness_min int not null,
    water_hardness_max int not null,
    temperature_min int not null,
    temperature_max int not null,
    reproduce_method char(20),
    origin char(36),
    in_species_temperament char(36) not null,
    cross_species_temperament char(36) not null,
    fishtank_position char(20),
    fishbase_spec_code int unique,
    data_source char(50) not null
)''')
    column_list = ', '.join(['id'] + FISH_COLUMNS)
    connection.execute("INSERT INTO fish_new ({0}, data_source) SELECT {0}, 'aqua-fish.net' FROM fish".format(column_list))
    connection.execute('DROP TABLE fish')
    connection.execute('ALTER TABLE fish_new RENAME TO fish')
    if sequence_row is not None:
        connection.execute("UPDATE sqlite_sequence SET seq = max(seq, ?) WHERE name = 'fish'", (sequence_row[0],))
    connection.execute('''CREATE TABLE fish_picture(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fish_id int not null references fish(id),
    url text not null unique,
    author text,
    licence text not null,
    source_url text not null
)''')
    connection.execute('CREATE INDEX fish_picture_fish_id ON fish_picture(fish_id)')


UPGRADE_STEPS = {1: upgrade_to_version_1, 2: upgrade_to_version_2}


def migrate(source_path, target_path):
    if os.path.abspath(source_path) == os.path.abspath(target_path):
        raise Exception('The target must be a different file from the source')
    if os.path.exists(target_path):
        raise Exception('{} already exists, please choose a new target'.format(target_path))

    shutil.copyfile(source_path, target_path)
    # transactions are opened explicitly, so table changes are part of them as well
    connection = sqlite3.connect(target_path, isolation_level=None)
    try:
        version = connection.execute('PRAGMA user_version').fetchone()[0]
        for next_version in range(version + 1, LATEST_VERSION + 1):
            # each step and its version number are committed together, or not at all
            connection.execute('BEGIN')
            try:
                UPGRADE_STEPS[next_version](connection)
                connection.execute('PRAGMA user_version = {}'.format(next_version))
                connection.execute('COMMIT')
            except Exception:
                connection.execute('ROLLBACK')
                raise
        return connection.execute('PRAGMA user_version').fetchone()[0]
    finally:
        connection.close()


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: python migrate_db.py <source database> <target database>')
        sys.exit(1)
    print('Migrated to version {}'.format(migrate(sys.argv[1], sys.argv[2])))
