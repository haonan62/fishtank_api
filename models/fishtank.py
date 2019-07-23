from models.fish import Fish

# The default size of the fishtank is length:10, width:10, heigth:10
# By default, there is no fish in the fishtank
# By default the status of the fishtank is healthy
# All above variables can be overrided in the constructor


class fishtank:
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

    def add_fish(self, another_fish):
        if isinstance(another_fish, Fish):

            if another_fish.scientific_name in self.fish_map:
                cur_number = self.fish_map[another_fish.scientific_name]+1
                self.fish_map[another_fish.scientific_name] = cur_number
            elif another_fish.scientific_name not in self.fish_map:

                self.fish_map[another_fish.scientific_name] = 1
        else:
            raise Exception('The object is not fish')
