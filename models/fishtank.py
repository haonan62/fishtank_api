from models.fish import fish

class fishtank:
    def __init__(self, fish_map,status):
        self.fish_map = fish_map
        self.status=status
    
    def __str__(self):
        return str(self.fish_map)
    
    def add_fish(self,another_fish):
        if isinstance(another_fish,fish):

            if another_fish.scientific_name in self.fish_map:
                cur_number=self.fish_map[another_fish.scientific_name]+1
                self.fish_map[another_fish.scientific_name]=cur_number
            elif another_fish.scientific_name not in self.fish_map:

                self.fish_map[another_fish.scientific_name]=1
        else:
            raise Exception('The object is not fish')
