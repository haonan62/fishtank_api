from models.fish import Fish
from models.fishdao import Fishdao
import itertools
import copy
# The default size of the fishtank is length:10, width:10, heigth:10
# By default, there is no fish in the fishtank
# By default the status of the fishtank is healthy
# All above variables can be overrided in the constructor


class Fishtank:
    def __init__(self, size=None, fish_map=None, status="Healthy"):
        if fish_map is None:
            fish_map = {}
            self.fish_map = fish_map
        elif fish_map is not None:
            self.fish_map = fish_map

        self.status = status
        if size is None:
            size = (10, 10, 10)
            self.size = size
        elif size is not None:
            self.size = size

    def copy(self):
        return copy.deepcopy(self)

    def __str__(self):
        return str({"Size": str(self.size), "Fish": str(self.fish_map), "Status": self.status})

    def get_total_status_for_api(self):
        return {"Size": str(self.size), "Fish": str(self.fish_map), "Status": self.status}

    # DANGEROUS! This method adds fish to the fishtank without checking any conditions
    # Only for developement purposes.
    def casual_add_fish(self, another_fish):
        if isinstance(another_fish, Fish):

            if another_fish.scientific_name in self.fish_map:

                cur_number = self.fish_map[another_fish.scientific_name]+1
                self.fish_map[another_fish.scientific_name] = cur_number
            elif another_fish.scientific_name not in self.fish_map:

                self.fish_map[another_fish.scientific_name] = 1
        else:
            raise Exception('The object is not fish')

    # Standard method for adding fish into the fishtank
    # General logic is trying to invoke the coexist method with the fish any any other fish in current fishtank
    # If the for loop does not throw any error, then the method returns a true, otherwise, the method throws the
    # exception to the higher layer
    def add_fish(self, another_fish):
        temp_fish_dao = Fishdao()

        all_fish = temp_fish_dao.all_fish
        if isinstance(another_fish, Fish):

            if another_fish.scientific_name in self.fish_map:

                try:

                    for key, value in self.fish_map.items():
                        cur_fish = all_fish[key]
                        co_exist_flag = cur_fish.coexist_together(another_fish)

                    cur_number = self.fish_map[another_fish.scientific_name]+1
                    self.fish_map[another_fish.scientific_name] = cur_number
                except Exception as e:
                    raise e

            elif another_fish.scientific_name not in self.fish_map:

                try:

                    for key, value in self.fish_map.items():
                        cur_fish = all_fish[key]
                        co_exist_flag = cur_fish.coexist_together(another_fish)

                    self.fish_map[another_fish.scientific_name] = 1
                except Exception as e:
                    raise e

        else:
            raise Exception('The object is not fish')

    def add_fish_list_in_sequence(self, fish_list):
        for sample_fish in fish_list:
            try:
                self.add_fish(sample_fish)
            except Exception as e:
                print(str(e))

    def remove_fish(self, another_fish):
        temp_fish_dao = Fishdao()

        all_fish = temp_fish_dao.all_fish
        if isinstance(another_fish, Fish):

            if another_fish.scientific_name in self.fish_map:

                cur_fish_no = self.fish_map[another_fish.scientific_name]
                if cur_fish_no > 1:
                    cur_fish_no = cur_fish_no-1
                    self.fish_map[another_fish.scientific_name] = cur_fish_no
                elif cur_fish_no <= 1:
                    self.fish_map.pop(another_fish.scientific_name)

            elif another_fish.scientific_name not in self.fish_map:
                raise Exception(another_fish.scientific_name +
                                ': No such fish in the fishtank')
        else:
            raise Exception('The object is not fish')

    # This function returns the maximum number of species a fishtank can hold given the existing fish
    # user has chosen, lots of computational power needed, meaning lots of optimization can be achieved given enough expertise
    # note: theoretically, this fuction works, but in reality, it does not
    # as it consumes too much memory when it comes to combinations e.g: 742 C 720=9.153544691 E+41
    # any commercial computer do not have enough memory address for this stupid process
    # a smarter way to find best diversity is needed

    # if you want to improve the performance, please work on v2 or create your own v3 methods
    def maximize_diversity_given_fish(self):
        current_fish_species_in_tank = list(self.fish_map.keys())
        # if there is existing fish in the fishtank, then we use the existing fish as base to slowly add fish
        # the process is iterative, until the loop is all finished, we are not able to find the best combination
        maximum_diversity_combination = []

        if len(current_fish_species_in_tank) != 0:
            # retrieve all fish that is not in the fishtank
            all_remaining_fish = Fishdao().retrieve_remaining_fish(current_fish_species_in_tank)
            all_remaining_fish_scientific_names = all_remaining_fish.keys()
            current_combination_length = len(
                all_remaining_fish_scientific_names)
            # the for loop start from the largest possible length of combination to the shortest
            # e.g: if there are 700 fish left, then we loop from 700, 699........1
            for i in range(current_combination_length, 0, -1):

                combinations_given_order = list(itertools.combinations(
                    all_remaining_fish_scientific_names, r=i))
                print("Current size of the combination :" +
                      str(len(combinations_given_order)))
                for current_combination in combinations_given_order:
                    # create a temporary fishtank with only the user's pre-selected inside

                    temp_fishtank = self.copy()
                    maximum_diversity_flag = True
                    for current_fish_scientific_name in current_combination:
                        try:
                            temp_fishtank.add_fish(
                                all_remaining_fish[current_fish_scientific_name])
                        except Exception as e:
                            maximum_diversity_flag = False
                            print(str(e))
                            # stop the current for loop(which means the current combination) and move to the next combination
                            break
                    if maximum_diversity_flag == True:
                        maximum_diversity_combination = current_combination
                        return maximum_diversity_combination

            return []
        elif len(current_fish_species_in_tank) == 0:
            return "Still working on best combination for entire fish population"

    def maximize_diversity_given_fish_v2(self):
        current_fish_species_in_tank = [
            Fish.get(Fish.scientific_name == key) for key, value in self.fish_map.items()]
        general_compatible_list = Fishdao().find_all_compatible_fish(
            current_fish_species_in_tank)
        # TODO: perform internal combinations inside the to general_compatible_list
        # because although we ensure individual fish in the general_compatible_list can live with fish in the tank
        # we are not certain that the fish in the list can live with each other

        return general_compatible_list

    def maximize_diversity_on_empty_tank(self):
        return []
