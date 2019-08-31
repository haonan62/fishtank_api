# Fishtank API

This is a webservice for achieving fish Harmony

Problem: Keeping different tropical fish inside a fish tank can be difficult, fish adapt to different temperatures, we might mistakenly mix predators and prays, each species have optimal population density. A wrong fish could ruin the entire ecosystem of a fish tank

Idea: A Web-based application: FishTank allows users to create a fish tank. While user drag and drop virtual fish from sidebar into the simulated fish tank, it will raise alarm when there are potential predators, or two species having too different optimal temperatures or the tank reaches optimal population. After the alarm, the fish being dragged in will be placed back.

Fish tank API offers an intelligent and elegant backend solution for fish lovers to create a fish tank in harmony.

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

## Important APIs and their functionalities

```
GET
ip:5000/fishtank_api/get_fish_by_group
Sorting fish based on their families
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
1(add fish):
url parameters: ip:5000/fishtank_api/fishtank_operation?action=add
form data is in json
format: {"fishtank_no": unique identifier, "fish":list of fish's scientific names}
example: {"fishtank_no":"accabf084fcbe29002ec6965aeed035a7df90b3559ee60802e9c09f83398dbce","fish":["Acestrorhynchus altus","Alestopetersius caudalis"]}

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
format: {"fishtank_no": unique identifier, "fish":list of fish's scientific names}
example: {"fishtank_no":"accabf084fcbe29002ec6965aeed035a7df90b3559ee60802e9c09f83398dbce","fish":["Acestrorhynchus altus","Alestopetersius caudalis"]}
```

## Functions to add
Given a fish or a group of fish, determine the maximum fish species that the fishtank can hold(easy)  
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

* **Xu Haonan** - *Initial work* - [Xu Haonan](https://github.com/haonan62)
* **Ma Chao** - *Initial work* - [George Ma](https://github.com/G1335721N)

## License

This project is licensed under the MIT License

## Acknowledgments

* The authors thank <https://en.aqua-fish.net/> for providing high quality data regarding different traits of fish