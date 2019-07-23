from models.fish import Fish
from models.fishtank import fishtank
a_fish=Fish.get(Fish.scientific_name == 'Abramites eques')
b_fish=Fish.get(Fish.scientific_name == 'Neolamprologus caudopunctatus')
tank=fishtank(size=(100,100,30),status='bad')
tank.add_fish(a_fish)
tank.add_fish(a_fish)
tank.add_fish(b_fish)
print(tank)