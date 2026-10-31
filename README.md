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

Run git clone <https://github.com/haonan62/fishtank_api.git>

### Prerequisites

```
Python version 3.11 or newer
Python packages: see pyproject.toml (flask, peewee, gunicorn)
```

### Installing

```
Activate virtual environment, run pip install -e .
```

```
To run the app, enter "flask --app fishtank run --debug"
The web ui is served at http://127.0.0.1:5000 once it is built: in frontend/, run npm ci, then npm run build (Node 20.19 or newer)
While working on the ui, run npm run dev in frontend/ as well and open http://localhost:5173, it reloads on every change
```

```
To run the tests, enter "python -m unittest -v", and for the web ui "npm test" in frontend/
```

```
The app never writes to data/fish.db, it works on its own database: FISHTANK_DATABASE when set, instance/fishtank.db otherwise
The first time the app starts it copies data/fish.db there, every start after brings it to the latest schema
Users, fishtanks and fish changed by admins live only in the app's database, which is not committed
Fish added to data/fish.db later only reach an app database that is created after
```

```
To make the first admin, enter "flask --app fishtank create-admin <username>" and type a password
Admins can then promote other users through the api, or enter "flask --app fishtank set-role <username> admin"
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

The layout of the code, and how to work on it together, is described in [CONTRIBUTING.md](./CONTRIBUTING.md)

## Important APIs and their functionalities

Every answer is json with a "status" of "success" or "error", an error comes with a "message" and an http status:
400 for a bad request, 401 when a login is needed or the token is wrong, 403 for something only admins may do,
404 when the fish or fishtank does not exist (or belongs to someone else), 409 for a conflict,
422 when the fish cannot live together (the alarm), the fishtank is then unchanged
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

```
POST ip:5000/fishtank_api/auth/register   {"username": ..., "password": ...}
     username: 3 to 32 letters, digits, dots, dashes or underscores, unique ignoring case; password: 8 to 128 characters
     everyone registers as a user, the answer carries "user", "token" and "expires_at"
POST ip:5000/fishtank_api/auth/login      {"username": ..., "password": ...}, answers like register
POST ip:5000/fishtank_api/auth/logout     ends the login of this token only
GET  ip:5000/fishtank_api/auth/me         the logged in user
```

### Fish

```
GET ip:5000/fishtank_api/fish                   every fish, by id
GET ip:5000/fishtank_api/fish?group_by=family   every fish, sorted into their families ("fish_by_family")
GET ip:5000/fishtank_api/fish/<id>              one fish, also a retired one (fishtanks may keep it)
The catalogue leaves out retired fish, admins see them with ?include_retired=true and every fish carries its fishtank_count for them
Every fish carries its id, its data_source (aqua-fish.net, FishBase 25.04, or manual entry for fish added by an admin),
a fishbase_url to its FishBase page when known, and its pictures: hosted urls with author, licence, credit and source page,
the pictures are not stored here
Fish from FishBase have an "unknown" temperament and no size, origin, reproduce method or fishtank position yet,
until their temperament is known they can only be kept alone, one fish in a fishtank
```

Admins only:

```
POST   ip:5000/fishtank_api/fish        adds a fish, with the fields of a fish as GET returns them (not id, fishbase_url or pictures)
       required: scientific_name, family_name, minimum/maximum_ph, minimum/maximum_water_hardness,
       minimum/maximum_temperature, in_species_temperament, cross_species_temperament
       optional: common_name, minimum/maximum_size, reproduce_method, origin, fishtank_position, fishbase_spec_code,
       data_source (manual entry when left out)
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
```

A fishtank is answered as:

```
{"key": ..., "name": ..., "size": {"length": 100, "width": 100, "height": 30}, "saved": true,
 "fish": [{"id": 11, "scientific_name": ..., "common_name": ..., "count": 2}],
 "created_at": ..., "updated_at": ..., "expires_at": null for a saved fishtank}
```

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

## Functions to add
Given a fish or a group of fish, determine the maximum fish species that the fishtank can hold(requires background in optimization), target method: maximize_diversity_given_fish in [fishtank.py](./fishtank/simulation/fishtank.py)    
fuzzy search(difficult, might make more sense to put into frontend)


## Deployment

Please use gunicorn and nginx to serve the production app, e.g. gunicorn -b 0.0.0.0:5000 "fishtank:create_app()".
The app keeps its data in one sqlite file, so run a single instance and keep the file (FISHTANK_DATABASE) on a persistent volume. If you want configuration files for both, please approach the authors. But googling will be fine, there are plenty of online tutorials.
There is also a separate branch for docker deployment, please refer to the branches or approach authors for deployment details.

## Built With

* [flask](https://flask.palletsprojects.com/en/1.0.x/) - The web framework used
* [pip](https://pypi.org/project/pip/) - Dependency Management

## Authors

* **Xu Haonan** - *Initial work* - [Xu Haonan](https://github.com/haonan62), SIS,SMU  
* **Ma Chao** - *Initial work* - [George Ma](https://github.com/G1335721N), Stern, NYU  

## License

The code of this project is licensed under the MIT License

The data in data/fish.db is not covered by the MIT License:
* Fish with data_source "FishBase 25.04", the FishBase species codes and all pictures come from FishBase and are licensed
  under [Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/),
  they may only be used for non-commercial purposes, clearly identified as coming from FishBase, with a link to the source page
* Pictures are only linked, each keeps its own copyright, only pictures marked for free use, non-commercial use or public domain
  are linked, and each must be shown with its credit ("author, from FishBase")
* Fish with data_source "aqua-fish.net" come from <https://en.aqua-fish.net/>, © Aqua-Fish.Net, all rights reserved

## Acknowledgments

* The authors thank <https://en.aqua-fish.net/> for providing high quality data regarding different traits of fish
* Additional species, FishBase species codes and pictures are taken from FishBase:
  Froese, R. and D. Pauly. Editors. 2025. FishBase. World Wide Web electronic publication. www.fishbase.org, version (04/2025).
  Data taken from FishBase should also be credited by the Main Ref. and/or Data Ref. of the respective record,
  see <https://www.fishbase.se/summary/citation.php>
* Pictures are credited to their photographers on every picture, as recorded by FishBase
* The FishBase release was read from the parquet tables that Carl Boettiger publishes for
  [rfishbase](https://github.com/ropensci/rfishbase) at <https://huggingface.co/datasets/cboettig/fishbase>