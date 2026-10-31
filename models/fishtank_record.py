from datetime import timedelta
import secrets

from peewee import *

from models.database import BaseModel, to_iso, utcnow
from models.fish import Fish
from models.fishtank import Fishtank
from models.user import User

DEFAULT_SIZE = (100, 100, 30)
# a visitor's fishtank is removed after a day without changes, unless a user saves it
VISITOR_TANK_LIFETIME = timedelta(hours=24)


# A fishtank as it is stored, the simulation itself happens in a Fishtank built from it
# A fishtank with an owner is saved and kept until it is removed, only its owner can see or change it
# A fishtank without owner belongs to a visitor, whoever knows its key can use it, until it expires
class FishtankRecord(BaseModel):
    id = AutoField()
    # the key is the only thing protecting a visitor's fishtank, so it cannot be guessed
    key = CharField(unique=True, default=lambda: secrets.token_urlsafe(32))
    owner = ForeignKeyField(User, null=True, backref='fishtanks', column_name='owner_id', on_delete='CASCADE')
    name = CharField(null=True)
    length = IntegerField()
    width = IntegerField()
    height = IntegerField()
    created_at = DateTimeField(default=utcnow)
    updated_at = DateTimeField(default=utcnow)
    expires_at = DateTimeField(null=True)

    class Meta:
        table_name = 'fishtank'

    @classmethod
    def create_for(cls, owner, name=None, size=DEFAULT_SIZE):
        now = utcnow()
        expires_at = None if owner is not None else now + VISITOR_TANK_LIFETIME
        return cls.create(owner=owner, name=name, length=size[0], width=size[1], height=size[2],
                          created_at=now, updated_at=now, expires_at=expires_at)

    @classmethod
    def remove_expired(cls):
        return cls.delete().where(cls.owner.is_null() & (cls.expires_at <= utcnow())).execute()

    # returns the fishtank when the given user, or a visitor when user is None, may use it
    # other people's fishtanks look the same as fishtanks that do not exist
    @classmethod
    def find_for(cls, key, user):
        if not isinstance(key, str):
            return None
        record = cls.get_or_none(cls.key == key)
        if record is None:
            return None
        if record.owner_id is None:
            return record if record.expires_at > utcnow() else None
        if user is not None and record.owner_id == user.id:
            return record
        return None

    def is_saved(self):
        return self.owner_id is not None

    def size(self):
        return (self.length, self.width, self.height)

    def save_for(self, owner):
        self.owner = owner
        self.expires_at = None

    # every change keeps a visitor's fishtank alive for another lifetime
    def touch(self):
        self.updated_at = utcnow()
        if not self.is_saved():
            self.expires_at = self.updated_at + VISITOR_TANK_LIFETIME

    def entries(self):
        return (FishtankFish.select(FishtankFish, Fish).join(Fish)
                .where(FishtankFish.fishtank == self).order_by(Fish.id))

    # the Fishtank simulation knows fish by scientific name
    def to_fishtank(self):
        fish_map = {entry.fish.scientific_name: entry.count for entry in self.entries()}
        return Fishtank(size=self.size(), fish_map=fish_map)

    # stores the fish of a Fishtank by fish id, replacing the fish stored before
    def store_fish(self, fishtank):
        ids_by_name = {fish.scientific_name: fish.id for fish in
                       Fish.select(Fish.id, Fish.scientific_name).where(Fish.scientific_name.in_(list(fishtank.fish_map)))}
        FishtankFish.delete().where(FishtankFish.fishtank == self).execute()
        rows = [{'fishtank': self.id, 'fish': ids_by_name[name], 'count': count} for name, count in fishtank.fish_map.items()]
        if rows:
            FishtankFish.insert_many(rows).execute()

    def to_dic(self):
        return {
            'key': self.key,
            'name': self.name,
            'size': {'length': self.length, 'width': self.width, 'height': self.height},
            'saved': self.is_saved(),
            'fish': [{'id': entry.fish.id, 'scientific_name': entry.fish.scientific_name,
                      'common_name': entry.fish.common_name, 'count': entry.count} for entry in self.entries()],
            'created_at': to_iso(self.created_at),
            'updated_at': to_iso(self.updated_at),
            'expires_at': to_iso(self.expires_at)
        }


class FishtankFish(BaseModel):
    fishtank = ForeignKeyField(FishtankRecord, backref='fish_entries', column_name='fishtank_id', on_delete='CASCADE')
    fish = ForeignKeyField(Fish, backref='fishtank_entries', column_name='fish_id')
    count = IntegerField()

    class Meta:
        table_name = 'fishtank_fish'
        primary_key = CompositeKey('fishtank', 'fish')
