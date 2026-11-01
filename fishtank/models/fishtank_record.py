from datetime import timedelta
import secrets

from peewee import *

from fishtank.db import BaseModel, to_iso, utcnow
from fishtank.models.fish import Fish
from fishtank.simulation.fishtank import Fishtank
from fishtank.simulation.stocking import assess_stocking, tank_warnings
from fishtank.models.user import User

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
    # set while the fishtank is shared read only, the key itself is never shown to the people it is shared with
    share_token = CharField(null=True, unique=True)

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

    # a shared fishtank, for anyone with the link, as long as its owner shares it and it has not expired
    @classmethod
    def find_shared(cls, token):
        if not isinstance(token, str):
            return None
        record = cls.get_or_none(cls.share_token == token)
        if record is None or (record.owner_id is None and record.expires_at <= utcnow()):
            return None
        return record

    def is_saved(self):
        return self.owner_id is not None

    def share(self):
        if self.share_token is None:
            self.share_token = secrets.token_urlsafe(24)

    def stop_sharing(self):
        self.share_token = None

    # A new fishtank for owner (a visitor when None) with the same name, size and fish
    # Retired fish cannot be added anymore, they are left out and returned, so the copy can say so
    def copy_for(self, owner, name=None):
        copy = FishtankRecord.create_for(owner, name=name if name is not None else self.name, size=self.size())
        skipped = []
        rows = []
        for entry in self.entries():
            if entry.fish.is_retired():
                skipped.append(entry.fish)
            else:
                rows.append({'fishtank': copy.id, 'fish': entry.fish.id, 'count': entry.count})
        if rows:
            FishtankFish.insert_many(rows).execute()
        return copy, skipped

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
        return {'key': self.key, **self.contents_dic(), 'saved': self.is_saved(), 'share_token': self.share_token,
                'created_at': to_iso(self.created_at), 'expires_at': to_iso(self.expires_at)}

    # what a shared fishtank shows: no key, no owner, nothing that changes it
    def shared_dic(self):
        return {'share_token': self.share_token, **self.contents_dic(),
                'owner': self.owner.username if self.owner_id is not None else None}

    def contents_dic(self):
        entries = list(self.entries())
        residents = [(entry.fish, entry.count) for entry in entries]
        stocking = assess_stocking(self.size(), residents)
        return {
            'name': self.name,
            'size': {'length': self.length, 'width': self.width, 'height': self.height},
            'fish': [{'id': entry.fish.id, 'scientific_name': entry.fish.scientific_name,
                      'common_name': entry.fish.common_name, 'count': entry.count} for entry in entries],
            # advice only, a fishtank can be crowded or keep a lonely schooling fish
            'stocking': stocking,
            'warnings': tank_warnings(self.size(), residents, stocking),
            'updated_at': to_iso(self.updated_at),
        }


class FishtankFish(BaseModel):
    fishtank = ForeignKeyField(FishtankRecord, backref='fish_entries', column_name='fishtank_id', on_delete='CASCADE')
    fish = ForeignKeyField(Fish, backref='fishtank_entries', column_name='fish_id')
    count = IntegerField()

    class Meta:
        table_name = 'fishtank_fish'
        primary_key = CompositeKey('fishtank', 'fish')
