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
    

