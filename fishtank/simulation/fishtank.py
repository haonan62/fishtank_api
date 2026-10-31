from collections import namedtuple
from fishtank.models.fish import UNKNOWN_TEMPERAMENT, Fish
from fishtank.simulation.fishdao import Fishdao
from fishtank.simulation.errors import fish_not_in_fishtank_error
import itertools
import copy
import time

# The answer of Fishtank.find_largest_group: species, the sorted scientific names of the group, and complete,
# False when the search ran out of its budget, the group then still gets along but a larger one may exist
GroupSearch = namedtuple('GroupSearch', ['species', 'complete'])
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

    # setter for fishmap
    def set_fish_map(self,value):
        setattr(self,'fish_map',value)
    
    # setter for status
    def set_tank_status(self,value):
        setattr(self,'status',value)
    
    # setter for size of the tank
    def set_size(self,value):
        setattr(self,'size',value)

    # method for making a duplicate instead of a reference
    def copy(self):
        return copy.deepcopy(self)

    def __str__(self):
        return str({"Size": str(self.size), "Fish": str(self.fish_map), "Status": self.status})

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
        self.check_can_add(another_fish)
        self.fish_map[another_fish.scientific_name] = self.fish_map.get(another_fish.scientific_name, 0) + 1

    # Raises the reason when the fish cannot join the fishtank, every fish in the tank must accept it
    # all_fish (scientific name to fish) can be passed in when many fish are checked against the same tank
    def check_can_add(self, another_fish, all_fish=None):
        if not isinstance(another_fish, Fish):
            raise Exception('The object is not fish')
        if all_fish is None:
            all_fish = Fishdao().all_fish
        for key in self.fish_map:
            all_fish[key].coexist_together(another_fish)

    def add_fish_list_in_sequence(self, fish_list):
        for sample_fish in fish_list:
            try:
                self.add_fish(sample_fish)
            except Exception as e:
                raise e
                # print(str(e))

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
                raise fish_not_in_fishtank_error(another_fish.scientific_name +
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


    # Some problems that are similar to this:
    # constraint satisfaction problem
    # combinatorial optimization
    def maximize_diversity_given_fish_v2(self):
        current_fish_species_in_tank = [
            Fish.get(Fish.scientific_name == key) for key, value in self.fish_map.items()]
        general_compatible_list = Fishdao().find_all_compatible_fish(
            current_fish_species_in_tank)
        # TODO: perform internal combinations inside the to general_compatible_list
        # because although we ensure individual fish in the general_compatible_list can live with fish in the tank
        # we are not certain that the fish in the list can live with each other

        # however, this once again falls into the trap of the first version above
        # F**k, IS is useless

        return general_compatible_list

    # This function returns the largest group of new species that can live with every fish in the tank and with
    # each other, as a sorted list of scientific names, one fish per species. An empty tank searches the whole database
    # Two species only count as compatible when coexist_together passes in both directions, so the returned fish
    # can be added through add_fish in any order. Retired fish are left out, they can no longer be added
    # time_limit (seconds) and max_steps bound the search, see find_largest_group
    def maximize_diversity_given_fish_v3(self, time_limit=None, max_steps=None):
        return self.find_largest_group(time_limit=time_limit, max_steps=max_steps).species

    # The search behind maximize_diversity_given_fish_v3, answered as a GroupSearch
    # The problem is a maximum clique search: candidates are the nodes, compatible pairs are the edges
    # Branch and bound keeps it fast, a greedy colouring of the remaining candidates gives an upper bound on how many
    # more species can still join the current group (Tomita and Seki), so most branches are cut early
    # The search can still take very long on some inputs, so it can be given a budget: time_limit in seconds and
    # max_steps, the number of groups it may grow. Once the budget is spent it answers the largest group found so far,
    # with complete False. That group still all gets along, it is only not known to be the largest. When the time runs
    # out while the pairs are checked, only the candidates whose pairs were all checked are searched, at least one
    def find_largest_group(self, time_limit=None, max_steps=None, fish_dao=None):
        deadline = None if time_limit is None else time.monotonic() + time_limit
        if fish_dao is None:
            fish_dao = Fishdao()
        current_fish_in_tank = [fish_dao.all_fish[key] for key in self.fish_map]
        all_remaining_fish = fish_dao.retrieve_remaining_fish(list(self.fish_map.keys()))
        complete = True

        def out_of_time():
            return deadline is not None and time.monotonic() >= deadline

        def coexist_both_ways(first_fish, second_fish):
            try:
                first_fish.coexist_together(second_fish)
                second_fish.coexist_together(first_fish)
                return True
            except Exception:
                return False

        # sorted, so the same fish give the same answer whatever order the database returns them in
        candidates = sorted(scientific_name for scientific_name, fish in all_remaining_fish.items()
                            if not fish.is_retired()
                            and all(coexist_both_ways(resident, fish) for resident in current_fish_in_tank))

        # a fish of unknown temperament never gets along with another species, it is never checked against one
        compatible_with = {scientific_name: set() for scientific_name in candidates}
        known = [scientific_name for scientific_name in candidates
                 if all_remaining_fish[scientific_name].cross_species_temperament != UNKNOWN_TEMPERAMENT]
        for i, first_name in enumerate(known):
            # the first fish is always checked, so a fish that can join is always answered
            if i > 0 and out_of_time():
                complete = False
                candidates = sorted(set(known[:i]) | (set(candidates) - set(known)))
                break
            for second_name in known[i + 1:]:
                if coexist_both_ways(all_remaining_fish[first_name], all_remaining_fish[second_name]):
                    compatible_with[first_name].add(second_name)
                    compatible_with[second_name].add(first_name)

        # orders the candidates by colour, fish of the same colour are pairwise incompatible, so at most one of each
        # colour can join, the bound of a candidate is the number of colours up to and including its own
        def colour_candidates(remaining):
            colour_classes = []
            for scientific_name in sorted(remaining, key=lambda name: (-len(compatible_with[name] & remaining), name)):
                for colour_class in colour_classes:
                    if not (compatible_with[scientific_name] & colour_class):
                        colour_class.add(scientific_name)
                        break
                else:
                    colour_classes.append({scientific_name})
            ordered = []
            for colour_number, colour_class in enumerate(colour_classes, start=1):
                for scientific_name in sorted(colour_class):
                    ordered.append((scientific_name, colour_number))
            return ordered

        maximum_diversity_combination = []
        steps = 0

        def expand(current_group, remaining):
            nonlocal maximum_diversity_combination, steps, complete
            steps += 1
            # try the candidates with the highest bound first, stop once no bound can beat the best group found
            for scientific_name, bound in reversed(colour_candidates(remaining)):
                if len(current_group) + bound <= len(maximum_diversity_combination):
                    return
                # the first group is always grown to the end, so there is a group to answer
                if maximum_diversity_combination and (out_of_time() or (max_steps is not None and steps >= max_steps)):
                    complete = False
                    return
                new_group = current_group + [scientific_name]
                new_remaining = remaining & compatible_with[scientific_name]
                if new_remaining:
                    expand(new_group, new_remaining)
                elif len(new_group) > len(maximum_diversity_combination):
                    maximum_diversity_combination = new_group
                remaining = remaining - {scientific_name}

        expand([], set(candidates))
        return GroupSearch(species=sorted(maximum_diversity_combination), complete=complete)

    def maximize_diversity_on_empty_tank(self):
        return []
