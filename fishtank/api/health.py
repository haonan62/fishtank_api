from flask import Blueprint, make_response
from peewee import PeeweeException

from fishtank.api.common import error_response, success
from fishtank.db import database
from fishtank.models.fish import Fish

blueprint = Blueprint('health', __name__)


# For monitoring tools, they say nothing about the data and need no login
# Is the process up? Does not touch the database, so a restart only helps when this one fails
@blueprint.route('/healthz')
def healthz():
    return no_store(success())


# Can the app serve requests? Reads the database, a failure is a 503 so monitoring tools see it from the status alone
@blueprint.route('/readyz')
def readyz():
    try:
        database.connect(reuse_if_open=True)
        Fish.select(Fish.id).limit(1).execute()
    except PeeweeException:
        return no_store(error_response('the database cannot be read', 503))
    return no_store(success())


# a cache between the monitoring tool and the app must not answer for the app
def no_store(answer):
    response = make_response(answer)
    response.headers['Cache-Control'] = 'no-store'
    return response
