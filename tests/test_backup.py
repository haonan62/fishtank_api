import gzip
import os
import shutil
import sqlite3
import stat
import tempfile
import unittest
from datetime import timedelta
from unittest import mock

from fishtank import backup
from fishtank.db import SEED_DATABASE, database, utcnow
from fishtank.models.rate_limit import RateLimitHit
from tests.api_test_case import ApiTestCase


class BackupTest(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder)
        self.source = database.database

    def backups(self):
        return sorted(name for name in os.listdir(self.folder))

    def restore(self, name):
        path = os.path.join(self.folder, 'restored.db')
        with gzip.open(os.path.join(self.folder, name)) as packed, open(path, 'wb') as restored:
            shutil.copyfileobj(packed, restored)
        return sqlite3.connect(path)

    def test_a_backup_can_be_restored_with_changes_not_yet_checkpointed(self):
        self.register('alice')
        path, _ = backup.make_backup(self.source, self.folder)
        connection = self.restore(os.path.basename(path))
        self.addCleanup(connection.close)
        self.assertEqual(connection.execute('SELECT username FROM user').fetchall(), [('alice',)])
        self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_only_its_owner_reads_a_backup(self):
        path, _ = backup.make_backup(self.source, self.folder)
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)

    def test_only_the_newest_backups_stay_and_other_files_are_left_alone(self):
        names = ['fishtank-2026010{}-030000.db.gz'.format(day) for day in range(1, 6)]
        for name in names + ['notes.txt']:
            open(os.path.join(self.folder, name), 'w').close()
        path, removed = backup.make_backup(self.source, self.folder, keep=2)
        self.assertEqual(removed, names[:4])
        self.assertEqual(self.backups(), sorted([names[4], os.path.basename(path), 'notes.txt']))

    def test_a_failed_backup_removes_nothing(self):
        old = 'fishtank-20260101-030000.db.gz'
        open(os.path.join(self.folder, old), 'w').close()
        with mock.patch.object(backup, 'check_database', side_effect=backup.BackupError('damaged')):
            with self.assertRaises(backup.BackupError):
                backup.make_backup(self.source, self.folder, keep=1)
        self.assertEqual(self.backups(), [old])

    def test_at_least_one_backup_is_kept(self):
        with self.assertRaises(backup.BackupError):
            backup.make_backup(self.source, self.folder, keep=0)

    def test_the_command_writes_a_backup_and_forgets_old_ip_addresses(self):
        RateLimitHit.create(bucket='register_ip', key='old', created_at=utcnow() - timedelta(days=2))
        RateLimitHit.create(bucket='register_ip', key='recent', created_at=utcnow())
        result = self.app.test_cli_runner().invoke(args=['backup', self.folder, '--keep', '1'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual([hit.key for hit in RateLimitHit.select()], ['recent'])


class WriteAheadLogTest(ApiTestCase):

    def test_the_app_database_uses_it_and_the_committed_one_does_not(self):
        self.assertEqual(database.execute_sql('PRAGMA journal_mode').fetchone()[0], 'wal')
        with open(SEED_DATABASE, 'rb') as seed:
            # bytes 18 and 19 of a sqlite file are 1 for a rollback journal and 2 for the write-ahead log
            self.assertEqual(seed.read(20)[18:20], b'\x01\x01')


if __name__ == '__main__':
    unittest.main()
