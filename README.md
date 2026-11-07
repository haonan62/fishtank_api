# Fishtank API

This is a webservice for achieving fish Harmony

Problem: Keeping different tropical fish inside a fish tank can be difficult, fish adapt to different temperatures, we might mistakenly mix predators and prays, each species have optimal population density. A wrong fish could ruin the entire ecosystem of a fish tank

Idea: A Web-based application: FishTank allows users to create a fish tank. While user drag and drop virtual fish from sidebar into the simulated fish tank, it will raise alarm when there are potential predators, or two species having too different optimal temperatures or the tank reaches optimal population. After the alarm, the fish being dragged in will be placed back.

Fish tank API offers an intelligent and elegant backend solution for fish lovers to create a fish tank in harmony.

## Research Statement

A spectre is haunting the fishtank – the spectre of complexity. All the powers of the academia have
entered into a holy alliance to exorcise this spectre: UNSW and NYU, HKU and SMU, faculty of Computer Science and Mathematics.   

Please refer to [Functions to add](#Functions-to-add) to get the detailed problem description.  



## Getting Started

### Prerequisites

- Python 3.11 or newer
- Node 20.19 or newer, for the web ui

### Quick start

From a fresh clone, install the api into a virtual environment:

```bash
git clone https://github.com/haonan62/fishtank_api.git
```

```bash
cd fishtank_api
```

```bash
python3 -m venv .venv && source .venv/bin/activate
```

```bash
pip install -e .
```

Build the web ui once, Flask serves the built files itself:

```bash
npm --prefix frontend ci && npm --prefix frontend run build
```

Make yourself an admin, it asks for a password (skip this to only browse and simulate as a visitor):

```bash
flask --app fishtank create-admin <username>
```

Start the app, then open http://127.0.0.1:5000:

```bash
flask --app fishtank run --debug
```

On macOS port 5000 is often taken by the AirPlay Receiver ("Address already in use", or a 403 from AirTunes).
Turn it off in System Settings → General → AirDrop & Handoff, or run on another port and open that one instead:

```bash
flask --app fishtank run --debug --port 5050
```

Admins can promote other users in the web ui, or with `flask --app fishtank set-role <username> admin`.

### Working on the web ui

Keep Flask running, and start Vite in a second terminal, then open http://localhost:5173, it reloads on every change
and sends api calls on to Flask. When Flask runs on another port, tell Vite which, e.g. `FISHTANK_API=http://127.0.0.1:5050`:

```bash
npm --prefix frontend run dev
```

### Running the tests

```bash
python -m unittest -v
```

```bash
npm --prefix frontend test
```

### Notes

```
The login cookie of the web ui is only sent over https. Chrome and Firefox make an exception for localhost,
in another browser over plain http set FISHTANK_SECURE_COOKIES=0 for local use, never in production
```

```
The app never writes to data/fish.db, it works on its own database: FISHTANK_DATABASE when set, instance/fishtank.db otherwise
The first time the app starts it copies data/fish.db there, every start after brings it to the latest schema
Users, fishtanks and fish changed by admins live only in the app's database, which is not committed
Fish added to data/fish.db later only reach an app database that is created after
```

```
data/fish.db carries its schema version, to upgrade an older copy enter
"python -m fishtank.migrations <old database> <new database>", the old database is left unchanged
```

```
data/fish.db already includes the fish and pictures of FishBase release 25.04, to import a release again:
download species, stocks, synonyms, families and picturesmain (.parquet) from
https://huggingface.co/datasets/cboettig/fishbase/tree/main/data/fb/v25.04/parquet into one folder,
run pip install -e ".[fishbase]" (pyarrow is only needed for the import), then enter
"python -m fishtank.fishbase_import <folder> <old database> <new database>", the old database is left unchanged
```

```
Fish FishBase has no reusable picture of got one from Wikimedia Commons, iNaturalist or GBIF, to look again for fish
without a picture (after an import, say), enter
"python -m fishtank.picture_import fetch data/fish.db pictures.json" to look them up (this takes a while, the apis are
asked politely), check pictures.json, then
"python -m fishtank.picture_import apply pictures.json <old database> <new database>", the old database is left unchanged
```

The layout of the code, and how to work on it together, is described in [CONTRIBUTING.md](./CONTRIBUTING.md).
What comes after the launch is in [BACKLOG.md](./BACKLOG.md).

## Important APIs and their functionalities

Every answer is json with a "status" of "success" or "error", an error comes with a "message" and an http status:
400 for a bad request, 401 when a login is needed or the token is wrong, 403 for something only admins may do,
a wrong password or a missing csrf token, 404 when the fish or fishtank does not exist (or belongs to someone else),
409 for a conflict, 422 when the fish cannot live together (the alarm), the fishtank is then unchanged,
429 when there were too many attempts, with a "Retry-After" header in seconds
When a request field is wrong, the error also names it in "field", so a form can show the message next to it
Large json answers are gzipped when the client accepts it

### Users and roles

```
visitor  no account needed, can look at fish and create and simulate fishtanks, which are removed after a day without changes
user     registered, everything a visitor can do, and their fishtanks are saved until they remove them
admin    everything a user can do, and adds, changes and removes fish, and changes the role of users
```

A user logs in once and sends the token with every request, in the header `Authorization: Bearer <token>`
A token lasts 30 days, a request with a wrong or expired token is refused, it is not treated as a visitor's

Logging in or registering also sets two cookies, which the web ui uses instead of the token:
`fishtank_session` carries the token, scripts cannot read it (HttpOnly, Secure, SameSite=Lax);
`fishtank_csrf` can be read, and every request that changes something (not GET) with the session cookie must send
its value back in the header `X-CSRF-Token`, otherwise it is refused (403). Other sites cannot read the cookie,
so they cannot make a logged in browser change anything. Requests with `Authorization: Bearer` need no csrf token
An expired session cookie is refused (401) and removed with the answer

```
POST ip:5000/fishtank_api/auth/register   {"username": ..., "password": ...}
     username: 3 to 32 letters, digits, dots, dashes or underscores, unique ignoring case; password: 8 to 128 characters
     everyone registers as a user, the answer carries "user", "token" and "expires_at"
POST ip:5000/fishtank_api/auth/login      {"username": ..., "password": ...}, answers like register
POST ip:5000/fishtank_api/auth/logout     ends the login of this token only, and removes the cookies
GET  ip:5000/fishtank_api/auth/me         the logged in user
POST ip:5000/fishtank_api/auth/password   {"current_password": ..., "new_password": ...}, every other login of the user ends
DELETE ip:5000/fishtank_api/auth/me       {"password": ...}, removes the account with its logins and saved fishtanks,
                                          the last admin cannot remove themselves (409)
```

Too many attempts are answered with 429 and a Retry-After header, counted in the database, so every worker sees them:

```
failed logins               5 per username and 20 per ip address in 15 minutes, a wrong password given to change
                            the password or remove the account counts as well, a login succeeding resets the username's count
new accounts                10 per ip address in an hour
fishtanks made by visitors  30 per ip address in an hour, logged in users are not limited
```

### Fish

```
GET ip:5000/fishtank_api/fish                   every fish, by id
GET ip:5000/fishtank_api/fish?group_by=family   every fish, sorted into their families ("fish_by_family")
GET ip:5000/fishtank_api/fish/<id>              one fish, also a retired one (fishtanks may keep it)
The catalogue leaves out retired fish, admins see them with ?include_retired=true and every fish carries its fishtank_count for them
Every fish carries its id, its data_source (aqua-fish.net, FishBase 25.04, or manual entry for fish added by an admin),
a fishbase_url to its FishBase page when known, and its pictures: hosted urls with author, licence, credit, source page
and source (FishBase, Wikimedia Commons, iNaturalist or GBIF), the pictures are not stored here
Fish from FishBase have an "unknown" temperament and no size, origin, reproduce method or fishtank position yet,
until their temperament is known they can only be kept alone, one fish in a fishtank
```

Admins only:

```
POST   ip:5000/fishtank_api/fish        adds a fish, with the fields of a fish as GET returns them (not id, fishbase_url or pictures)
       required: scientific_name, family_name, minimum/maximum_ph, minimum/maximum_water_hardness,
       minimum/maximum_temperature, in_species_temperament, cross_species_temperament
       optional: common_name, minimum/maximum_size, reproduce_method, origin, fishtank_position, fishbase_spec_code,
       data_source (manual entry when left out), minimum_group_size (2 to 50, the smallest group a schooling fish feels
       safe in, only for a fish peaceful with its own kind and with a known temperament)
       group_size_source is read only: Fishtank list for the starting values, manual entry once an admin sets it
       a minimum always comes with its maximum and is not larger, ph lies between 0 and 14, temperature between 0 and 45
       a fish whose cross_species_temperament is known needs a size
       in_species_temperament: peaceful, peaceful to males, peaceful to females, aggressive/territorial, unknown
       cross_species_temperament: peaceful, aggressive/territorial, aggressive to smaller, unknown
PATCH  ip:5000/fishtank_api/fish/<id>   changes only the fields that are sent, the rules above hold for the whole fish after it
       fishtanks keep the fish, even when it no longer fits in with the others
DELETE ip:5000/fishtank_api/fish/<id>   removes the fish and its pictures, refused (409) while the fish lives in a fishtank
POST   ip:5000/fishtank_api/fish/<id>/retire    takes the fish out of the catalogue, it cannot be added to fishtanks anymore,
                                                fishtanks that keep it are not changed
POST   ip:5000/fishtank_api/fish/<id>/restore   brings a retired fish back into the catalogue
POST   ip:5000/fishtank_api/fish/<id>/pictures  links a picture an admin found: {"url": the image, "source_url": its page,
                                                "licence", "source": the site it is from, "author" (optional)}, https only,
                                                credited "author, licence, via source"; only link pictures whose licence
                                                allows showing them with a credit
DELETE ip:5000/fishtank_api/fish/<id>/pictures/<picture id>   unlinks a picture
The first picture of a fish, the oldest, is the one the catalogue shows
```

### Fishtanks

A fishtank is identified by its key, a random text that cannot be guessed
A visitor's fishtank can be used by whoever knows its key, a user's fishtank only by that user

```
POST   ip:5000/fishtank_api/fishtanks                creates a fishtank, optional body {"name": ..., "size": {"length", "width", "height"}}
                                                     size defaults to 100 x 100 x 30, saved when a user is logged in
GET    ip:5000/fishtank_api/fishtanks                the saved fishtanks of the logged in user, latest change first
GET    ip:5000/fishtank_api/fishtanks/<key>          one fishtank
PATCH  ip:5000/fishtank_api/fishtanks/<key>          {"name": ..., "size": ...}, changes the name or size
DELETE ip:5000/fishtank_api/fishtanks/<key>          removes the fishtank
POST   ip:5000/fishtank_api/fishtanks/<key>/save     a logged in user saves a visitor's fishtank, e.g. one built before logging in
GET    ip:5000/fishtank_api/fishtanks/<key>/compatible   which fish could join now: {"compatible": [ids], "incompatible": [{"id", "reason"}]},
                                                     the same check as adding them, retired fish are left out
GET    ip:5000/fishtank_api/fishtanks/<key>/suggestions   companions that can all join together, best first:
                                                     {"suggestions": [ids], "group_size": ..., "complete": true}, ?limit= 1 to 50
POST   ip:5000/fishtank_api/fishtanks/<key>/share    a read only link: the fishtank answers with its share_token, sharing again keeps it
DELETE ip:5000/fishtank_api/fishtanks/<key>/share    stops sharing, the link stops working
GET    ip:5000/fishtank_api/shared/<token>           the shared fishtank for anyone with the link: name, owner, size, fish, stocking,
                                                     warnings, never its key
POST   ip:5000/fishtank_api/fishtanks/<key>/copy     a new fishtank with the same name, size and fish, saved for a logged in user
POST   ip:5000/fishtank_api/shared/<token>/copy      the same for a shared fishtank; retired fish are left out of a copy,
                                                     "skipped" lists them
```

Suggestions come from the maximum diversity search (`Fishtank.find_largest_group`), one fish per species, best first:
fish with a picture and a common name, then fish whose water ranges cover most of the water the tank's fish share
(for an empty tank, fish that take the widest ranges). `limit` is 1 to 50, 12 by default, `group_size` is the size of the
whole group. Any part of the group can be added in one request, in any order, until the fishtank changes. Retired fish
are left out. The search over the whole catalogue takes a second or two, it stops after 4 seconds and answers the
largest group found so far with `"complete": false`, that group still gets along, a larger one may exist.

A fishtank is answered as:

```
{"key": ..., "name": ..., "size": {"length": 100, "width": 100, "height": 30}, "saved": true,
 "fish": [{"id": 11, "scientific_name": ..., "common_name": ..., "count": 2}],
 "stocking": {"litres": 300.0, "net_litres": 255.0, "capacity_cm": 171.1, "fish_cm": 6, "share": 0.035,
              "level": "comfortable", "uncounted_fish": 0},
 "warnings": [{"kind": "group", "fish_id": 11, "count": 2, "minimum": 6, "message": ...}],
 "created_at": ..., "updated_at": ..., "expires_at": null for a saved fishtank}
```

Stocking and warnings are advice, they never stop a fish from being added:
- stocking counts the adult size of every fish (maximum_size x count) against what the water holds comfortably,
  one inch of fish per US gallon (0.67 cm per litre) of 85% of the tank's volume (gravel and decoration take the rest);
  level is empty, comfortable, nearly full (from 80%) or overstocked (above 100%), fish without a known size are uncounted_fish
- warnings, most pressing first: "overstocked"; "group" when a schooling fish has fewer than its minimum_group_size;
  "room" when the tank is shorter than 4 times a fish's adult length (minimum_length says how long it should be)

```
POST ip:5000/fishtank_api/fishtanks/<key>/add      {"fish": list of fish ids}
POST ip:5000/fishtank_api/fishtanks/<key>/remove   {"fish": list of fish ids}
This carries the main logic. It adds or removes a group of fish with conditional checking, the same id twice means two fish
The fishtank only changes when every fish in the list can be added or removed
example: {"fish": [11, 22]}

sample output (422):
{
    "message": "Cross species competition exists between Acestrorhynchus altus and Alestopetersius caudalis, Acestrorhynchus altus with size 24 may attack Alestopetersius caudalis with size 5",
    "status": "error"
}
```

### Users (admins only)

```
GET   ip:5000/fishtank_api/users        every user
PATCH ip:5000/fishtank_api/users/<id>   {"role": "user" or "admin"}, the last admin cannot become a user
```

### Reviewing the catalogue

Users help fill in the fish whose temperament is not known yet, admins review what they suggest:

```
POST ip:5000/fishtank_api/fish/<id>/suggestions   (logged in) {"in_species_temperament", "cross_species_temperament",
                                                  "minimum_size", "maximum_size", "minimum_group_size" (optional), "note" (optional)}
                                                  only for a fish whose temperament is unknown, checked like an admin's change,
                                                  a user's newer suggestion for the fish replaces their pending one
GET  ip:5000/fishtank_api/suggestions             (admins) ?status=pending (default), approved, rejected or all
POST ip:5000/fishtank_api/suggestions/<id>/approve   (admins) copies the values onto the fish, checked again
POST ip:5000/fishtank_api/suggestions/<id>/reject    (admins)
```

Admins change many fish at once as a spreadsheet:

```
GET  ip:5000/fishtank_api/fish/export.csv         id and every field admins can change, ?review=true for the fish to review
POST ip:5000/fishtank_api/fish/import             the csv as text/csv, only the columns in it change, an empty cell clears an
                                                  optional field; ?dry_run=true answers what would change, row by row,
                                                  without it every row is applied, or none when any row has an error
```

Every change admins make (fish, retiring, pictures, roles, suggestions, imports) is in the audit log:

```
GET ip:5000/fishtank_api/audit   (admins) newest first, ?fish_id= for one fish, ?before=<event id> for the next page, ?limit= up to 200
                                 each event has username, action, fish_id, target_user_id and details, e.g. the changed fields
                                 as {"field": {"from": ..., "to": ...}}
```

## Functions to add
Given a fish or a group of fish, determine the maximum fish species that the fishtank can hold(requires background in optimization), target method: maximize_diversity_given_fish in [fishtank.py](./fishtank/simulation/fishtank.py)    
fuzzy search(difficult, might make more sense to put into frontend)


## Deployment

The app runs in one container behind nginx, which adds https. It fits a very small server: one process with four threads
uses about 60 MB of memory serving the catalogue, and the container is limited to 128 MB (`docker-compose.yml`).

Start the app (it listens on 127.0.0.1:5000 only) and make the first admin:

```bash
docker compose up -d --build
```

```bash
docker compose exec web flask --app fishtank create-admin <username>
```

Copy [deploy/nginx.conf](./deploy/nginx.conf) to `/etc/nginx/conf.d/fishtank.conf` on the server, replace `example.org` with
your domain, and follow the steps at the top of the file. The login cookie is only sent over https.

`FISHTANK_PROXIES` is the number of proxies in front of the app (1 for nginx, already set in `docker-compose.yml`), so rate limits
count the visitor's ip address from X-Forwarded-For and https is recognised from X-Forwarded-Proto. Leave it unset when nothing sits
in front of the app, otherwise anyone could pick their ip address by sending X-Forwarded-For.

The app keeps its data in one sqlite file in write-ahead log mode, so run a single container and keep its volume on a local disk,
not on a network drive. `gunicorn.conf.py` has the server settings, `WEB_CONCURRENCY` sets more processes when there is memory for them.

Every answer carries a Content-Security-Policy, X-Content-Type-Options, Referrer-Policy and X-Frame-Options,
and Strict-Transport-Security over https. A ui that loads files from somewhere new needs CONTENT_SECURITY_POLICY
in fishtank/app.py changed with it.

### Health checks

Both need no login and answer `{"status": "success"}` with a 200, so any monitoring tool can scrape them by status alone:

| Endpoint | Means | Fails when |
| --- | --- | --- |
| `GET /healthz` | the process is up | the app is down or stuck, it does not touch the database |
| `GET /readyz` | the app can serve requests | also when the database cannot be read, with a 503 |

Docker checks `/readyz` every minute, `docker ps` shows the container as healthy or unhealthy.

### Backups

`flask --app fishtank backup <folder>` writes a checked, compressed copy of the database while the app keeps running, then removes all
but the newest backups (4 by default, change it with `--keep`). Older backups only go once the new one is safely written, and it only touches files named like a backup.
A backup is about 150 KB with a few users. It also forgets ip addresses from rate limits that have passed.

To run it every Sunday at 03:00, add this to the server's crontab with `crontab -e`, with the folder of this project:

```
0 3 * * 0 cd /path/to/fishtank_api && docker compose exec -T web flask --app fishtank backup /app/backups >> backups.log 2>&1
```

Backups live on the same disk as the database, so now and then copy the newest one somewhere else, it holds password hashes so keep it private:

```bash
docker compose cp web:/app/backups ./backups
```

To restore the newest backup, stop the app, replace its database, and start it again:

```bash
docker compose stop web
```

```bash
docker compose run --rm --no-deps -T web sh -c 'cd /app/instance && rm -f fishtank.db-wal fishtank.db-shm && gunzip -c "$(ls -1 /app/backups/fishtank-*.db.gz | tail -1)" > fishtank.db'
```

```bash
docker compose up -d web
```

## Built With

* [flask](https://flask.palletsprojects.com/en/1.0.x/) - The web framework used
* [pip](https://pypi.org/project/pip/) - Dependency Management

## Authors

* **Xu Haonan** - *Initial work* - [Xu Haonan](https://github.com/haonan62), SIS,SMU  
* **Ma Chao** - *Initial work* - [George Ma](https://github.com/G1335721N), Stern, NYU  

## License

The code of this project is licensed under the MIT License

The group sizes of schooling fish (group_size_source "Fishtank list") are this project's own starting values:
6 for fish of genera known to school or shoal, the minimum most fishkeeping guides give. No open dataset records
it per species, FishBase marks only 2 of our fish as schooling and ShoalBase (CC BY-NC-ND) cannot be adapted

This site runs as a non-commercial project, and has to stay one to use this data: 462 of the 1,145 pictures and all FishBase
data are licensed for non-commercial use only. Running it commercially means removing them first.

The data in data/fish.db is not covered by the MIT License:
* Fish with data_source "FishBase 25.04", the FishBase species codes and all pictures come from FishBase and are licensed
  under [Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/),
  they may only be used for non-commercial purposes, clearly identified as coming from FishBase, with a link to the source page
* Pictures are only linked, each keeps its own copyright and must be shown with its credit and a link to its page (source_url)
* Pictures with source "FishBase": only those marked for free use, non-commercial use or public domain, credited
  "author, from FishBase"
* Pictures with source "Wikimedia Commons", "iNaturalist" or "GBIF": only those under a licence that allows showing them with a
  credit (public domain, CC0, CC BY, CC BY-SA, GFDL, and on iNaturalist and GBIF also the non-commercial and no-derivatives
  Creative Commons licences), credited "author, licence, via source"
* Fish with data_source "aqua-fish.net" come from <https://en.aqua-fish.net/>, © Aqua-Fish.Net, all rights reserved

## Acknowledgments

* The authors thank <https://en.aqua-fish.net/> for providing high quality data regarding different traits of fish
* Additional species, FishBase species codes and pictures are taken from FishBase:
  Froese, R. and D. Pauly. Editors. 2025. FishBase. World Wide Web electronic publication. www.fishbase.org, version (04/2025).
  Data taken from FishBase should also be credited by the Main Ref. and/or Data Ref. of the respective record,
  see <https://www.fishbase.se/summary/citation.php>
* Pictures are credited to their photographers on every picture, as recorded by FishBase, Wikimedia Commons, iNaturalist
  or GBIF. They were found through Wikidata, the iNaturalist api and the GBIF api
* The FishBase release was read from the parquet tables that Carl Boettiger publishes for
  [rfishbase](https://github.com/ropensci/rfishbase) at <https://huggingface.co/datasets/cboettig/fishbase>