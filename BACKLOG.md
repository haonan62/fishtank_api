# Backlog

Things to come back to after going live, newest thinking first. Nothing here blocks the launch.

## Accounts

- **Move authentication to Keycloak.** This is also the plan for forgotten passwords: accounts have no email address
  and there is no reset, not even by an admin, so until then a lost password means a lost account. The terms say so.
  Sessions, roles and the login dialog are the parts that change (`fishtank/api/auth.py`, `fishtank/api/common.py`,
  `frontend/src/components/AuthDialog.tsx`).

## Catalogue

- **Get catalogue updates to the live site.** Changes to `data/fish.db` only reach a database created after them,
  so fixes and new pictures need a way to reach a database that already exists.
- **Check for broken pictures.** Every picture is linked from another site, a scheduled check would find the dead ones.
- **Fish without a picture.** 120 fish have none and still show by default. Sort them last, or hide them until an admin
  adds a photo (the admin fish list has a "Without a photo" filter).

## Running it

- **Load test the catalogue.** One process answers 8 clients asking for the catalogue at once in about 1.6 s each,
  because its 650 KB of json is compressed again on every request. Keeping the compressed answer should help.
- **Copy backups off the server.** Weekly backups stay on the same disk as the database, so they protect from mistakes
  and damage to the file, not from losing the server.

## Sharing

- **Link previews.** Every page has the same title and description, so shared tank links look the same in chat apps.
