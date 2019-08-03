from models.fish import Fish
from models.fishdao import Fishdao
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

    def __str__(self):
        return str({"Size": str(self.size), "Fish": str(self.fish_map), "Status": self.status})

    def get_total_status_for_api(self):
        return {"Size": str(self.size), "Fish": str(self.fish_map), "Status": self.status}

    def casual_add_fish(self, another_fish):
        if isinstance(another_fish, Fish):

            if another_fish.scientific_name in self.fish_map:
                
                cur_number = self.fish_map[another_fish.scientific_name]+1
                self.fish_map[another_fish.scientific_name] = cur_number
            elif another_fish.scientific_name not in self.fish_map:

                self.fish_map[another_fish.scientific_name] = 1
        else:
            raise Exception('The object is not fish')

    def add_fish(self, another_fish):
        temp_fish_dao=Fishdao()

        all_fish=temp_fish_dao.all_fish
        if isinstance(another_fish, Fish):

            if another_fish.scientific_name in self.fish_map:

                try:
                    total_flag=False
                    for key,value in self.fish_map.items():
                        cur_fish=all_fish[key]
                        temperature_flag=cur_fish.share_common_temperature_zone(another_fish)
                        ph_flag=cur_fish.share_common_ph_zone(another_fish)
                        water_hardness_flag=cur_fish.share_common_water_hardness_zone(another_fish)
                        peace_flag=cur_fish.live_peacefully_with(another_fish)
                
                    cur_number = self.fish_map[another_fish.scientific_name]+1
                    self.fish_map[another_fish.scientific_name] = cur_number
                except Exception as e:
                    raise e
                    
            elif another_fish.scientific_name not in self.fish_map:
                
                try:
                    total_flag=False
                    for key,value in self.fish_map.items():
                        cur_fish=all_fish[key]
                        temperature_flag=cur_fish.share_common_temperature_zone(another_fish)
                        ph_flag=cur_fish.share_common_ph_zone(another_fish)
                        water_hardness_flag=cur_fish.share_common_water_hardness_zone(another_fish)
                        peace_flag=cur_fish.live_peacefully_with(another_fish)
                
                    self.fish_map[another_fish.scientific_name] = 1
                except Exception as e:
                    raise e
                    

        else:
            raise Exception('The object is not fish')




    def remove_fish(self, another_fish):
        temp_fish_dao=Fishdao()

        all_fish=temp_fish_dao.all_fish
        if isinstance(another_fish, Fish):

            if another_fish.scientific_name in self.fish_map:

                cur_fish_no=self.fish_map[another_fish.scientific_name]
                if cur_fish_no>1:
                    cur_fish_no=cur_fish_no-1
                    self.fish_map[another_fish.scientific_name]=cur_fish_no
                elif cur_fish_no<=1:
                    self.fish_map.pop(another_fish.scientific_name)
                    
            elif another_fish.scientific_name not in self.fish_map:
                raise Exception(another_fish.scientific_name+ ': No such fish in the fishtank')
        else:
            raise Exception('The object is not fish')