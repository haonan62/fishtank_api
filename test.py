from models.fish import Fish
from models.fishtank import Fishtank
from models.fishdao import Fishdao
import hashlib
import time
import itertools

a_fish = Fish.get(Fish.scientific_name == 'Corydoras acrensis')

b_fish = Fish.get(Fish.scientific_name == 'Corydoras adolfoi')
c_fish= Fish.get(Fish.scientific_name == 'Acanthicus adonis')
aggressive_fish = Fish.get(Fish.scientific_name == 'Cynotilapia afra')

first_20_fish_in_db=Fish.select().limit(20)
all_fish=Fish.select()

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

# print("Setting a new map")
# tank.set_fish_map({"ga":1})
# tank.set_tank_status("unhealthy")
# tank.set_size([1,2,3])
# print(tank)

# print(sample_fish_dao.get_all_fish_group_by_fishtank_position_for_api())


# Below method tests when there are two fish in the fishtank, what would be the maximum fish species a tank can hold
# maximum_fish_given_fish_in_tank=tank.maximize_diversity_given_fish()
# print(maximum_fish_given_fish_in_tank)
# print(len(maximum_fish_given_fish_in_tank))

# print(list(itertools.combinations(first_20_fish_in_db,7)))
# 1 nums have been processed, number of this limiter is 743
# 2 nums have been processed, number of this limiter is 142691
# 3 nums have been processed, number of this limiter is 21246300
sol=[]
cur_com_num=1
for i in range(1,len(first_20_fish_in_db)):
    comb_iterator=itertools.combinations(first_20_fish_in_db,i)
    count=0
    temp_sol=[]
    for cur_comb in comb_iterator:
        tank = Fishtank(size=(100, 100, 30))
        try:
            tank.add_fish_list_in_sequence(cur_comb)
            temp_sol.append(cur_comb)
            count=count+1
        except:
            pass
    if count==0:
        break
    else:
        sol=temp_sol
    print(str(i)+" nums have been processed"+", number of this limiter is "+ str(count))

print("------------------------")
for ele in sol:
    print(ele)
print(len(sol))
print(len(sol[0]))




