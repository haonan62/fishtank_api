from models.fish import Fish
from models.fishtank import Fishtank
from models.fishdao import Fishdao

a_fish=Fish.get(Fish.scientific_name == 'Abramites eques')
b_fish=Fish.get(Fish.scientific_name == 'Neolamprologus caudopunctatus')

sample_fish_dao=Fishdao()

all_fish=sample_fish_dao.all_fish


tank=Fishtank(size=(100,100,30))

for key,value in all_fish.items():
    tank.add_fish(value)


print(tank)