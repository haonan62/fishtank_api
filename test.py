from models.fish import Fish
from models.fishtank import Fishtank
from models.fishdao import Fishdao
import hashlib
import time

a_fish=Fish.get(Fish.scientific_name == 'Corydoras acrensis')

b_fish=Fish.get(Fish.scientific_name == 'Corydoras adolfoi')

sample_fish_dao=Fishdao()
#initialize a new fishtank
tank=Fishtank(size=(100,100,30))
try:
    #add two fishes that can live with each other for further testing
    tank.add_fish(a_fish)
    tank.add_fish(b_fish)
except Exception as e:
    print(e)
print(tank)

#Below method tests when there are two fish in the fishtank, what would be the maximum fish species a tank can hold
maximum_fish_given_fish_in_tank=tank.maximize_diversity_given_fish()
print(maximum_fish_given_fish_in_tank)

