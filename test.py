from models.fish import Fish
from models.fishtank import Fishtank
from models.fishdao import Fishdao
import hashlib
import time

a_fish = Fish.get(Fish.scientific_name == 'Corydoras acrensis')

b_fish = Fish.get(Fish.scientific_name == 'Corydoras adolfoi')
c_fish= Fish.get(Fish.scientific_name == 'Acanthicus adonis')
aggressive_fish = Fish.get(Fish.scientific_name == 'Cynotilapia afra')

first_20_fish_in_db=Fish.select().limit(20)


sample_fish_dao = Fishdao()
# initialize a new fishtank
tank = Fishtank(size=(100, 100, 30))
try:
    # add two fishes that can live with each other for further testing
    tank.add_fish(a_fish)
    tank.add_fish(b_fish)
    # tank.add_fish(aggressive_fish)
    tank.add_fish_list_in_sequence(first_20_fish_in_db)
except Exception as e:
    print(e)
print(tank)

print("Setting a new map")
tank.set_fish_map({"ga":1})
tank.set_tank_status("unhealthy")
tank.set_size([1,2,3])
print(tank)


# Below method tests when there are two fish in the fishtank, what would be the maximum fish species a tank can hold
# maximum_fish_given_fish_in_tank=tank.maximize_diversity_given_fish_v2()
# print(maximum_fish_given_fish_in_tank)
# print(len(maximum_fish_given_fish_in_tank))
