from datetime import datetime, timezone
import os

from peewee import Model, SqliteDatabase

from fishtank import migrations

current_file = os.path.abspath(os.path.dirname(__file__))

# data/fish.db is the committed fish database, the app never writes to it
# the app works on its own copy, so users, fishtanks and fish edited by admins stay out of the repository
SEED_DATABASE = os.path.join(current_file, '../data/fish.db')
DEFAULT_APP_DATABASE = os.path.join(current_file, '../instance/fishtank.db')

# sqlite only enforces foreign keys when asked to, on every connection
PRAGMAS = {'foreign_keys': 1}

# models read the committed database until use_database points them elsewhere
database = SqliteDatabase(SEED_DATABASE, pragmas=PRAGMAS)


class BaseModel(Model):
    class Meta:
        database = database


# The app works on its own database, made from the committed data/fish.db the first time it starts
# and brought to the latest schema every time after
def prepare_database(path):
    if os.path.exists(path):
        migrations.upgrade(path)
    else:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        migrations.migrate(SEED_DATABASE, path)


def use_database(path):
    if not database.is_closed():
        database.close()
    database.init(path, pragmas=PRAGMAS)


# times are stored in UTC without a timezone, sqlite has no timezone type
def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_iso(moment):
    if moment is None:
        return None
    return moment.replace(microsecond=0).isoformat() + 'Z'
