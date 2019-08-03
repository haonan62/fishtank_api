from models.fish import Fish
from models.fishtank import Fishtank
from models.fishdao import Fishdao
import hashlib
import time

a_fish=Fish.get(Fish.scientific_name == 'Aequidens rondoni')
b_fish=Fish.get(Fish.scientific_name == 'Cynotilapia afra')

sample_fish_dao=Fishdao()

all_fish=sample_fish_dao.all_fish


tank=Fishtank(size=(100,100,30))
# try:
#     tank.add_fish(a_fish)
#     tank.add_fish(b_fish)
# except Exception as e:
#     print(e)
# for key,value in all_fish.items():
#     try:
    
#         tank.add_fish(value)
#     except Exception as e:
#         print(e)
# print(tank)

# print(sample_fish_dao.get_all_fish_group_by_family_for_api())
hash = hashlib.sha256()
hash.update(str(time.time()).encode('utf-8'))
print (hash.hexdigest())
print (hash.hexdigest()[:10])