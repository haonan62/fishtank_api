from models.fish import fish
from models.fishtank import fishtank
a_fish=fish('a','a','a','a','a','a','a','a','a','a','a','a','a','a','a','a',)

tank=fishtank({},'Healthy')
tank.add_fish(a_fish)
tank.add_fish(a_fish)
print(tank)