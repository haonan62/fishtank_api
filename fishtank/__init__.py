# The app lives in fishtank/app.py, it is imported only when an app is made,
# so python -m fishtank.migrations and the other tools do not load flask and the api first
def create_app(database_path=None):
    from fishtank.app import create_app as create_flask_app
    return create_flask_app(database_path)
