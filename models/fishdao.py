from models.fish import Fish
import copy
all_fish_list = Fish.select()
# The scientific name is the key for the all_fish map due to their uniqueness


class Fishdao:
    def __init__(self, all_fish=None):
        to_set = {}
        for fish in all_fish_list:
            scientific_name = fish.scientific_name
            to_set[scientific_name] = fish
        self.all_fish = to_set

    # If the fish has no common name, we'll have scientific name instead

    def get_all_common_names(self):
        to_return = []
        for key, value in self.all_fish.items():
            cur_common_name = None
            if value.common_name is None:
                cur_common_name = value.scientific_name
            elif value.common_name is not None:
                cur_common_name = value.common_name
            to_return.append(cur_common_name)
        return to_return

    def get_all_scientific_names(self):
        return list(self.all_fish.keys())

    def get_all_fish_group_by_family_for_api(self):
        to_return = {}
        for key, value in self.all_fish.items():
            cur_family_name = value.family_name
            if cur_family_name not in to_return:
                to_return[cur_family_name] = [value.to_dic()]
            elif cur_family_name in to_return:
                fish_in_list = to_return[cur_family_name]
                fish_in_list.append(value.to_dic())
                to_return[cur_family_name] = fish_in_list
        return to_return

    def retrieve_remaining_fish(self, to_exclude):
        to_return_copy = self.all_fish.copy()
        if len(to_exclude) != 0:
            for sample in to_exclude:
                del to_return_copy[sample]
            return to_return_copy
        else:
            return to_return_copy

    # this method returns fish that are peaceful to both its own species and other species

    def retrieve_enitirely_peaceful_fish(self):
        return Fish.select().where((Fish.cross_species_temperament == 'peaceful') & (Fish.in_species_temperament == 'peaceful'))
    # return fish that are peaceful among its own species

    def retrieve_in_species_peaceful_fish(self):
        return Fish.select().where(Fish.in_species_temperament == 'peaceful')
    # return fish that are peaceful with other fish species

    def retrieve_cross_species_peaceful_fish(self):
        return Fish.select().where(Fish.cross_species_temperament == 'peaceful')

    def generate_dummy_peaceful_buffer_fish(self, target_fish_list):
        to_return = None
        ph_buffer_max = 1000
        ph_buffer_min = -1000
        water_hardness_buffer_max = 1000
        water_hardness_buffer_min = -1000
        temperature_buffer_max = 1000
        temperature_buffer_min = -1000

        if isinstance(target_fish_list, list):
            for individual_target in target_fish_list:
                if individual_target.ph_min > ph_buffer_min:
                    ph_buffer_min = individual_target.ph_min
                if individual_target.ph_max < ph_buffer_max:
                    ph_buffer_max = individual_target.ph_max
                if individual_target.water_hardness_min > water_hardness_buffer_min:
                    water_hardness_buffer_min = individual_target.water_hardness_min
                if individual_target.water_hardness_max < water_hardness_buffer_max:
                    water_hardness_buffer_max = individual_target.water_hardness_max
                if individual_target.temperature_min > temperature_buffer_min:
                    temperature_buffer_min = individual_target.temperature_min
                if individual_target.temperature_max < temperature_buffer_max:
                    temperature_buffer_max = individual_target.temperature_max
        to_return = Fish(scientific_name='Dummy', common_name='Dummy', family_name='Dummy', size_min=1000, size_max=1001, ph_min=ph_buffer_min, ph_max=ph_buffer_max, water_hardness_min=water_hardness_buffer_min, water_hardness_max=water_hardness_buffer_max,
                         temperature_min=temperature_buffer_min, temperature_max=temperature_buffer_max, reproduce_method='Dummy', origin='Dummy', in_species_temperament='peaceful', cross_species_temperament='peaceful', fishtank_position='Dummy')
        return to_return

    def find_all_compatible_fish(self, target_fish_list):
        all_fish = copy.deepcopy(self.all_fish)
        to_return = []

        for key, value in all_fish.items():
            compatible_flag = True
            for sample in target_fish_list:
                if sample.scientific_name != key:
                    try:
                        sample.coexist_together(value)
                    except:
                        compatible_flag = False
                        break
                else:
                    compatible_flag = False
                    break
            if compatible_flag == True:
                to_return.append(value)
        return to_return
