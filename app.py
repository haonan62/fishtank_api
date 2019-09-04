from models.fish import Fish
from models.fishtank import Fishtank
from models.fishdao import Fishdao
from flask import Flask, url_for, jsonify, request
import hashlib
import time
import copy

app = Flask(__name__)

# a_fish=Fish.get(Fish.scientific_name == 'Abramites eques')
# b_fish=Fish.get(Fish.scientific_name == 'Neolamprologus caudopunctatus')

fish_dao_snapshot = Fishdao()
fishtank_map = {}

# all_fish=fish_dao_snapshot.all_fish


# tank=Fishtank(size=(100,100,30))

# for key,value in all_fish.items():
#     tank.casual_add_fish(value)


# print(fish_dao_snapshot.get_all_common_names())


@app.route('/fishtank_api')
def api_root():
    return 'Welcome to fishtank api'


@app.route('/fishtank_api/get_fish_by_group')
def api_fish_groups():

    fish_in_group = fish_dao_snapshot.get_all_fish_group_by_family_for_api()

    return jsonify(fish_in_group)


@app.route('/fishtank_api/initialize_new_fishtank')
def initialize_new_fish_tank():

    hash = hashlib.sha256()
    hash.update(str(time.time()).encode('utf-8'))
    # print (hash.hexdigest())
    unique_identifier = hash.hexdigest()
    fishtank_map[unique_identifier] = Fishtank(size=(100, 100, 30))

    return jsonify({'status': 'success', 'fishtank_number': unique_identifier, 'fishtank': fishtank_map[unique_identifier].get_total_status_for_api()})


@app.route('/fishtank_api/remove_fish_tank', methods=['POST'])
def remove_fish_tank():

    fishtank_key = None
    try:
        form_data = request.form
        fishtank_key = form_data.get('fishtank_key')
        if fishtank_key not in fishtank_map:
            return jsonify({'status': 'error', 'message': 'No such fishtank exists in the server'})
        else:
            fishtank_map.pop(fishtank_key)
            return jsonify({'status': 'success', 'message': 'fishtank removed', 'reference_no': fishtank_key})

    except:
        return jsonify({'status': 'error', 'message': 'No such fishtank exists in the server'})


@app.route('/fishtank_api/get_all_fishtank_keys')
def get_all_fish_tank_keys():

    return jsonify({'all fishtanks_keys': list(fishtank_map.keys())})


@app.route('/fishtank_api/fishtank_operation', methods=['POST'])
def add_fish():
    payload = None
    instruction = None
    target_fishtank_no = None
    fish_name_list = None
    fish_list = []
    cur_fishtank = None

    try:
        instruction = request.args.get('action')
    except:
        return jsonify({'status': 'error', 'message': 'please provide add or remove instruction to url'})

    try:
        payload = request.get_json()
    except:
        return jsonify({'status': 'error', 'message': 'please send json data'})

    try:
        target_fishtank_no = payload['fishtank_no']
        if target_fishtank_no not in fishtank_map:
            return jsonify({'status': 'error', 'message': 'no such fishtank'})
        cur_fishtank = fishtank_map[target_fishtank_no]
    except:
        return jsonify({'status': 'error', 'message': 'please provide fishtank number'})

    try:
        fish_name_list = payload['fish']
    except:
        return jsonify({'status': 'error', 'message': 'please provide a list of fishnames in array(scietific names)'})

    for cur_fish_name in fish_name_list:
        try:
            cur_fish = fish_dao_snapshot.all_fish[cur_fish_name]
            fish_list.append(cur_fish)
        except Exception as e:
            return jsonify({'status': 'error', 'message': cur_fish_name + " does not exist in database"})

    temp_fishtank = copy.deepcopy(cur_fishtank)

    if instruction == 'add':
        try:
            for cur_fish in fish_list:

                temp_fishtank.add_fish(cur_fish)
        except Exception as e:
            return jsonify({'status': 'error', 'message': e.args})
    elif instruction == 'remove':
        try:
            for cur_fish in fish_list:

                temp_fishtank.remove_fish(cur_fish)
        except Exception as e:
            return jsonify({'status': 'error', 'message': e.args})
    else:
        return jsonify({'status': 'error', 'message': "Specify a valid fishtank operation: add or remove"})

    cur_fishtank = temp_fishtank
    fishtank_map[target_fishtank_no] = cur_fishtank

    return jsonify({'status': 'success', 'current_fishtank': cur_fishtank.get_total_status_for_api()})


if __name__ == '__main__':
    app.run(debug=True)
