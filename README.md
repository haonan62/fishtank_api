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
Python version 3.6.8
Python packages: flask, peewee
```

### Installing

```
Activate virtual environment, run pip install peewee flask
```

```
To run the app, enter "python app.py"
```

```
To run the tests, enter "python -m unittest test_fishtank test_database test_api test_import -v"
```

```
data/fish.db carries its schema version, to upgrade an older copy enter
"python migrate_db.py <old database> <new database>", the old database is left unchanged
```

```
data/fish.db already includes the fish and pictures of FishBase release 25.04, to import a release again:
download species, stocks, synonyms, families and picturesmain (.parquet) from
https://huggingface.co/datasets/cboettig/fishbase/tree/main/data/fb/v25.04/parquet into one folder,
run pip install pyarrow (only needed for the import), then enter
"python import_fishbase.py <folder> <old database> <new database>", the old database is left unchanged
```

## Important APIs and their functionalities

```
GET
ip:5000/fishtank_api/get_fish_by_group
Sorting fish based on their families
Every fish carries its id, its data_source (aqua-fish.net or FishBase 25.04), a fishbase_url to its FishBase page
when known, and its pictures: hosted urls with author, licence, credit and source page, the pictures are not stored here
Fish from FishBase have an "unknown" temperament and no size, origin, reproduce method or fishtank position yet,
until their temperament is known they can only be kept alone, one fish in a fishtank
```

```
GET
ip:5000/fishtank_api/initialize_new_fishtank
Create new fishtank with a special identifier(hash of the current timestamp)
```

```
POST
ip:5000/fishtank_api/remove_fish_tank
Remove a fishtank with its special identifier on the server
form data: urlencoded
key: fishtank_key value:identifier of the fishtank
```

```
GET
ip:5000/fishtank_api/get_all_fishtank_keys
Retrieve all unique identifiers of the key(This is only for developement purposes)
```

```
POST
ip:5000/fishtank_api/fishtank_operation
This method carries the main logic. It can either add or remove a group of fish from the fishtank with conditional checking.
Fish are identified by their id, which get_fish_by_group returns with every fish. The fish in a fishtank are reported as {id: number of fish}
1(add fish):
url parameters: ip:5000/fishtank_api/fishtank_operation?action=add
form data is in json
format: {"fishtank_no": unique identifier, "fish":list of fish ids}
example: {"fishtank_no":"accabf084fcbe29002ec6965aeed035a7df90b3559ee60802e9c09f83398dbce","fish":[11,22]}

sample output:
{
    "message": [
        "Cross species competition exists between Acestrorhynchus altus and Alestopetersius caudalis, Acestrorhynchus altus with size 24 may attack Alestopetersius caudalis with size 5"
    ],
    "status": "error"
}

2(remove fish):
url parameters: ip:5000/fishtank_api/fishtank_operation?action=remove
form data is in json
format: {"fishtank_no": unique identifier, "fish":list of fish ids}
example: {"fishtank_no":"accabf084fcbe29002ec6965aeed035a7df90b3559ee60802e9c09f83398dbce","fish":[11,22]}
```

## Functions to add
Given a fish or a group of fish, determine the maximum fish species that the fishtank can hold(requires background in optimization), target method: maximize_diversity_given_fish in [fishtank.py](./models/fishtank.py)    
Session support(creation and expiry)  
user module?(complicated)  
fuzzy search(difficult, might make more sense to put into frontend)


## Deployment

Please use gunicorn and nginx to serve the production app. If you want configuration files for both, please approach the authors. But googling will be fine, there are plenty of online tutorials.
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