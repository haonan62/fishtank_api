# Contributing

Thanks for helping the fish live in harmony. This page covers how the code is laid out and how to make a change.

## Setup

Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[fishbase]"
```

`-e` installs the `fishtank` package in place, so your edits apply without reinstalling and `data/fish.db` is found
next to the package. `[fishbase]` adds pyarrow, which only the FishBase import needs.

```bash
flask --app fishtank run --debug
```

```bash
python -m unittest -v
```

The web ui lives in `frontend/` (React, TypeScript, Vite, Tailwind), Node 20.19 or newer:

```bash
cd frontend
npm ci
npm run dev
```

`npm run dev` serves the ui on http://localhost:5173 and forwards api calls to the Flask app on port 5000, so run both.
`npm test` runs the ui's unit tests, `npm run build` type checks and writes `frontend/dist/`, which Flask then serves itself.

The app creates its own database at `instance/fishtank.db` (or `FISHTANK_DATABASE`) on first start.
Delete that file to start over from `data/fish.db`.
To try the admin endpoints locally, run `flask --app fishtank create-admin <username>`.

## Layout

```
fishtank/                 the app, one python package
  __init__.py             create_app(), loads the app only when one is made
  app.py                  the Flask app factory: blueprints, errors, the database, gzip and serving the built ui
  cli.py                  flask commands: create-admin, set-role
  db.py                   the peewee database, BaseModel, time helpers, setting up the app's database
  migrations.py           versioned schema upgrades (sqlite user_version), python -m fishtank.migrations
  fishbase_import.py      imports a FishBase release into a copy of the database
  api/                    http layer, one Flask blueprint per resource
    common.py             ApiError, json helpers, login_required / admin_required, the current user
    auth.py               /auth: register, login, logout, me
    fish.py               /fish: listing for everyone, create / change / remove for admins
    fishtanks.py          /fishtanks: create, simulate (add / remove fish), save
    users.py              /users: admins list users and change roles
  models/                 database tables (peewee models)
    fish.py               Fish and FishPicture, including the compatibility rules between two fish
    user.py               User and AuthToken
    fishtank_record.py    a stored fishtank and the fish in it
  simulation/             the fishtank logic, no http or storage concerns
    fishtank.py           Fishtank: adding / removing fish with checks, the maximum diversity search
    fishdao.py            Fishdao: all fish loaded from the database, by name and by id
    errors.py             the errors raised when fish cannot live together
tests/                    unittest tests, run with python -m unittest
  api_test_case.py        base class for http tests, each test gets its own copy of the database
scripts/                  one-off scripts that are not part of the app
frontend/                 the web ui
  src/api/                the api client and the shapes of its answers, the only place that calls fetch
  src/auth/               who is logged in, the login token
  src/lib/                logic without ui: fish wording, water ranges, the catalogue, visitor tanks
  src/components/         shared pieces: aquarium, fish detail, filters, dialogs, buttons
  src/pages/              one file per page, admin/ holds the admin portal
data/fish.db              the committed fish database, the app never writes to it
```

Only `api/`, `cli.py` and `__init__.py` know about Flask and http. Below them, `simulation/` works on `Fish` from
`models/fish.py`, and `models/fishtank_record.py` turns a stored fishtank into a `Fishtank` and back. Nothing
outside `api/` imports from `api/`. Keep requests, status codes and json in `api/`, so the simulation can be used
and tested without a web server.

## Making changes

- **A new page**: add it under `frontend/src/pages/` and a route in `frontend/src/App.tsx`. Use the colours in
  `frontend/src/index.css` by name (`bg-surface`, `text-muted`, `text-brand`...), so dark mode keeps working.
- **A new endpoint**: add a route to the blueprint of its resource in `fishtank/api/`, or a new module with its
  own `blueprint` that you register in `create_app`. Raise `ApiError(message, status_code)` for errors, return
  `success(...)` otherwise. Add tests under `tests/` built on `ApiTestCase`.
- **A schema change**: never edit an existing upgrade step. Add `upgrade_to_version_N` to `fishtank/migrations.py`,
  register it in `UPGRADE_STEPS`, bump `LATEST_VERSION`, update the matching peewee model, and test the step in
  `tests/test_migrations.py`. Then upgrade the committed database and replace it:

  ```bash
  python -m fishtank.migrations data/fish.db /tmp/fish.db && mv /tmp/fish.db data/fish.db
  ```

  App databases that already exist pick up the step the next time the app starts.
- **Fish data**: `data/fish.db` is binary, so two branches that both change it cannot be merged. Coordinate before
  changing it, and keep data changes in their own pull request. Data from FishBase and aqua-fish.net comes with
  licence terms, see the License section of the README.

## Style

- Follow the surrounding code: comments explain why, in plain sentences, above the code they describe.
- 4 spaces, lines up to 120 characters (see `.editorconfig`).
- Every change comes with tests, and `python -m unittest` passes before you open a pull request. CI runs the same
  command on every pull request.

## Pull requests

Branch from `master` (`feat/...`, `fix/...`, `refactor/...`), keep one topic per pull request, and describe what
changed, why, and anything a reviewer should look at.
