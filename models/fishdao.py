from models.fish import Fish

all_fish_list = Fish.select()
class Fishdao:
    def __init__(self,all_fish=None):
        to_set={}
        for fish in all_fish_list:
            scientific_name=fish.scientific_name
            common_name=fish.common_name
            if common_name is not None:
                to_set[common_name]=fish
            elif common_name is None:
                to_set[scientific_name]=fish
        self.all_fish=to_set
    
    def get_all_fish_names(self):
        return list(self.all_fish.keys())
    
    def get_all_scientific_names(self):
        scientific_name_list=Fish.select(Fish.scientific_name)
        to_return=[]
        for name in scientific_name_list:
            to_return.append(name.scientific_name)
        return to_return

    def get_all_fish_group_by_family(self):
        to_return={}
       

