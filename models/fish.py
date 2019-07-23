class fish:
    def __init__(self, scientific_name,common_name,family_name,size_min,size_max,ph_min,ph_max,water_hardness_min,water_hardness_max,temperature_min,temperature_max,reproduce_method,origin,in_species_temperament,cross_species_temperament,fishtank_position):
        self.scientific_name = scientific_name
        self.common_name=common_name
        self.family_name=family_name
        self.size_min=size_min
        self.size_max=size_max
        self.ph_min=ph_min
        self.ph_max=ph_max
        self.water_hardness_min=water_hardness_min
        self.water_hardness_max=water_hardness_max
        self.temperature_min=temperature_min
        self.temperature_max=temperature_max
        self.reproduce_method=reproduce_method
        self.origin=origin
        self.in_species_temperament=in_species_temperament
        self.cross_species_temperament=cross_species_temperament
        self.fishtank_position=fishtank_position

    def __str__(self):
        return "The scientific name is "+ self.scientific_name