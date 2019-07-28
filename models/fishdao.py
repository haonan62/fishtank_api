from models.fish import Fish

all_fish_list = Fish.select()
#The scientific name is the key for the all_fish map due to their uniqueness
class Fishdao:
    def __init__(self,all_fish=None):
        to_set={}
        for fish in all_fish_list:
            scientific_name=fish.scientific_name
            to_set[scientific_name]=fish
        self.all_fish=to_set
    
    def get_all_common_names(self):
        to_return=[]
        for key,value in self.all_fish.items():
            cur_common_name=None
            if value.common_name is None:
                cur_common_name=value.scientific_name
            elif value.common_name is not None:
                cur_common_name=value.common_name
            to_return.append(cur_common_name)
        return to_return
    
    def get_all_scientific_names(self):
        return list(self.all_fish.keys())

    def get_all_fish_group_by_family_for_api(self):
        to_return={}
        for key,value in self.all_fish.items():
            cur_family_name=value.family_name
            if cur_family_name not in to_return:
                to_return[cur_family_name]=[value.to_dic()]
            elif cur_family_name in to_return:
                fish_in_list=to_return[cur_family_name]
                fish_in_list.append(value.to_dic())
                to_return[cur_family_name]=fish_in_list
        return to_return
       

