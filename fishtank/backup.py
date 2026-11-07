import gzip
import os
import re
import shutil
import sqlite3
import tempfile
from datetime import timedelta

from fishtank.db import utcnow

# Four weekly backups stay below a few MB, and a mistake noticed a week later can still be undone
DEFAULT_KEEP = 4
BACKUP_NAME = re.compile(r'^fishtank-\d{8}-\d{6}\.db\.gz$')
# longer than the window of any rate limit
RATE_LIMIT_RETENTION = timedelta(days=1)


class BackupError(Exception):
    pass


# Writes a checked copy of the database to folder, then removes all but the newest `keep` backups
# Older backups are only removed once the new one is safely there. Backups hold password hashes, only their owner reads them
def make_backup(database_path, folder, keep=DEFAULT_KEEP):
    if keep < 1:
        raise BackupError('keep at least one backup')
    os.makedirs(folder, mode=0o700, exist_ok=True)
    name = 'fishtank-{}.db.gz'.format(utcnow().strftime('%Y%m%d-%H%M%S'))
    with tempfile.TemporaryDirectory(dir=folder, prefix='.partial-') as partial:
        copy_path = os.path.join(partial, 'copy.db')
        copy_database(database_path, copy_path)
        check_database(copy_path)
        packed_path = os.path.join(partial, name)
        with open(copy_path, 'rb') as copy, gzip.open(packed_path, 'wb') as packed:
            shutil.copyfileobj(copy, packed)
        os.chmod(packed_path, 0o600)
        path = os.path.join(folder, name)
        os.replace(packed_path, path)
    return path, prune_backups(folder, keep)


# sqlite's backup api gives one consistent copy while the app keeps running, copying the file would not
def copy_database(database_path, copy_path):
    source = sqlite3.connect('file:{}?mode=ro'.format(database_path), uri=True)
    target = sqlite3.connect(copy_path)
    try:
        source.backup(target)
    except sqlite3.Error as e:
        raise BackupError('could not copy {}: {}'.format(database_path, e))
    finally:
        target.close()
        source.close()


def check_database(path):
    connection = sqlite3.connect(path)
    try:
        answer = connection.execute('PRAGMA integrity_check').fetchone()[0]
    finally:
        connection.close()
    if answer != 'ok':
        raise BackupError('the copy of the database is damaged: {}'.format(answer))


# only ever touches files named like a backup, the names sort by time. Returns the names it removed
def prune_backups(folder, keep):
    backups = sorted(name for name in os.listdir(folder) if BACKUP_NAME.match(name))
    removed = backups[:-keep]
    for name in removed:
        os.remove(os.path.join(folder, name))
    return removed
