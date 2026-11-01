import json

from peewee import *

from fishtank.db import BaseModel, to_iso, utcnow
from fishtank.models.fish import Fish
from fishtank.models.user import User

STATUS_PENDING = 'pending'
STATUS_APPROVED = 'approved'
STATUS_REJECTED = 'rejected'


# A user's suggestion for a fish whose temperament is not known yet, an admin approves or rejects it
# Approving copies the values onto the fish, the suggestion keeps what was proposed
class TemperamentSuggestion(BaseModel):
    id = AutoField()
    fish = ForeignKeyField(Fish, backref='suggestions', column_name='fish_id', on_delete='CASCADE')
    user = ForeignKeyField(User, null=True, backref='suggestions', column_name='user_id', on_delete='SET NULL')
    in_species_temperament = CharField()
    cross_species_temperament = CharField()
    size_min = IntegerField(null=True)
    size_max = IntegerField(null=True)
    minimum_group_size = IntegerField(null=True)
    note = TextField(null=True)
    status = CharField(default=STATUS_PENDING)
    created_at = DateTimeField(default=utcnow)
    reviewed_by = ForeignKeyField(User, null=True, column_name='reviewed_by', on_delete='SET NULL', backref='reviews')
    reviewed_at = DateTimeField(null=True)

    class Meta:
        table_name = 'temperament_suggestion'

    # the values to copy onto the fish, named as the fish api names them
    def fish_values(self):
        return {
            'in_species_temperament': self.in_species_temperament,
            'cross_species_temperament': self.cross_species_temperament,
            'minimum_size': self.size_min,
            'maximum_size': self.size_max,
            'minimum_group_size': self.minimum_group_size,
        }

    def to_dic(self):
        return {
            'id': self.id,
            'fish_id': self.fish_id,
            'username': self.user.username if self.user_id is not None else None,
            **self.fish_values(),
            'note': self.note,
            'status': self.status,
            'created_at': to_iso(self.created_at),
            'reviewed_by': self.reviewed_by.username if self.reviewed_by_id is not None else None,
            'reviewed_at': to_iso(self.reviewed_at),
        }


# One change made by an admin, the username is kept as well, so the log still reads well after a user is removed
class AuditEvent(BaseModel):
    id = AutoField()
    user = ForeignKeyField(User, null=True, column_name='user_id', on_delete='SET NULL', backref='audit_events')
    username = CharField(null=True)
    action = CharField()
    fish_id = IntegerField(null=True)
    target_user_id = IntegerField(null=True)
    details = TextField(null=True)
    created_at = DateTimeField(default=utcnow)

    class Meta:
        table_name = 'audit_event'

    @classmethod
    def record(cls, user, action, fish_id=None, target_user_id=None, details=None):
        return cls.create(user=user, username=user.username if user is not None else None, action=action,
                          fish_id=fish_id, target_user_id=target_user_id,
                          details=json.dumps(details, sort_keys=True, default=str) if details is not None else None)

    def to_dic(self):
        return {
            'id': self.id,
            'username': self.username,
            'action': self.action,
            'fish_id': self.fish_id,
            'target_user_id': self.target_user_id,
            'details': json.loads(self.details) if self.details else None,
            'created_at': to_iso(self.created_at),
        }
