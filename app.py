from models.fish import Fish
from models.fishtank import Fishtank
from models.fishdao import Fishdao
from flask import Flask, url_for,jsonify
app = Flask(__name__)

# a_fish=Fish.get(Fish.scientific_name == 'Abramites eques')
# b_fish=Fish.get(Fish.scientific_name == 'Neolamprologus caudopunctatus')

fish_dao_snapshot=Fishdao()

# all_fish=fish_dao_snapshot.all_fish


# tank=Fishtank(size=(100,100,30))

# for key,value in all_fish.items():
#     tank.casual_add_fish(value)


# print(fish_dao_snapshot.get_all_common_names())


@app.route('/')
def api_root():
    return 'Welcome to fishtank api'

@app.route('/get_fish_by_group')
def api_fish_groups():

    fish_in_group=fish_dao_snapshot.get_all_fish_group_by_family_for_api()

    return jsonify(fish_in_group)



if __name__ == '__main__':
    app.run()