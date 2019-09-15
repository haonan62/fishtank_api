from peewee import *
import os.path
from models.fish_error import *

current_file = os.path.abspath(os.path.dirname(__file__))
data_location = os.path.join(current_file, '../data/fish.db')

DATABASE = data_location
database = SqliteDatabase(DATABASE)

# db = SqliteDatabase('fish.db')


class BaseModel(Model):
    class Meta:
        database = database



class Fish(BaseModel):
    scientific_name = CharField(unique=True, primary_key=True)
    common_name = CharField()
    family_name = CharField()
    size_min = IntegerField()
    size_max = IntegerField()
    ph_min = DoubleField()
    ph_max = DoubleField()
    water_hardness_min = IntegerField()
    water_hardness_max = IntegerField()
    temperature_min = IntegerField()
    temperature_max = IntegerField()
    reproduce_method = CharField()
    origin = CharField()
    in_species_temperament = CharField()
    cross_species_temperament = CharField()
    fishtank_position = CharField()

    def __str__(self):
        return self.scientific_name

    def to_dic(self):
        return{
            'scientific_name': self.scientific_name,
            'common_name': self.common_name,
            'family_name': self.family_name,
            'minimum_size': self.size_min,
            'maximum_size': self.size_max,
            'minimum_ph': self.ph_min,
            'maximum_ph': self.ph_max,
            'minimum_water_hardness': self.water_hardness_min,
            'maximum_water_hardness': self.water_hardness_max,
            'minimum_temperature': self.temperature_min,
            'maximum_temperature': self.temperature_max,
            'reproduce_method': self.reproduce_method,
            'origin': self.origin,
            'in_species_temperament': self.in_species_temperament,
            'cross_species_temperament': self.cross_species_temperament,
            'fishtank_position': self.fishtank_position
        }
    # important!!!! This is the function indicating whether a fish could coexist with another fish
    # if can, it will return a true
    # if cannot, it will raise a custom exception with reason(e.g: Ph ranges are not common)

    def coexist_together(self, another_fish):
        if isinstance(another_fish, Fish):
            try:
                temperature_flag = self.share_common_temperature_zone(
                    another_fish)
                ph_flag = self.share_common_ph_zone(another_fish)
                water_hardness_flag = self.share_common_water_hardness_zone(
                    another_fish)
                peace_flag = self.live_peacefully_with(another_fish)
                return True
            except Exception as e:
                raise e
        else:
            raise Exception("The object is not fish")
    
    #This function examines whether the two fish share temperature zones in common
    #There are six possible ways of relative positions between two fish's temperature zones
    #A general gist is that if one fish's maximum temperature is smaller than another fish's minimum
    #or one fish's minimum temperature is larger than another fish's maximum, then the two fish have
    #no common temperature zones, in the above two cases, a custom error will be thrown
    #When two fish can indeed share a common temperature zone, the method returns true

    def share_common_temperature_zone(self, another_fish):
        if isinstance(another_fish, Fish):
            if self.temperature_min > another_fish.temperature_max or self.temperature_max < another_fish.temperature_min:
                raise temperature_not_common_error('Temperature ranges are not common between {} and {}'.format(
                    self.scientific_name, another_fish.scientific_name))
            else:
                return True
        else:
            raise Exception("The object is not fish")
    
    #This function examines whether the two fish share ph zones in common

    def share_common_ph_zone(self, another_fish):
        if isinstance(another_fish, Fish):
            if self.ph_min > another_fish.ph_max or self.ph_max < another_fish.ph_min:
                raise ph_not_common_error('Ph ranges are not common between {} and {}'.format(
                    self.scientific_name, another_fish.scientific_name))
            else:
                return True
        else:
            raise Exception("The object is not fish")
    
    #This function examines whether the two fish share water hardness zones in common

    def share_common_water_hardness_zone(self, another_fish):
        if isinstance(another_fish, Fish):
            if self.water_hardness_min > another_fish.water_hardness_max or self.water_hardness_max < another_fish.water_hardness_min:
                raise water_hardness_not_common_error('Water hardness ranges are not common between {} and {}'.format(
                    self.scientific_name, another_fish.scientific_name))
            else:
                return True
        else:
            raise Exception("The object is not fish")

    #This function examines whether the one fish shows aggression to another, or vice versa
    #If the method detects the two fish are of the same species, then it will check the in_species_temperament
    #If the two fish are different, then it will check the cross_species_temperament
    #Size also matters, as some fish will only attack smaller, and some have a wirdo gut to attck larger
    
    def live_peacefully_with(self, another_fish):
        if isinstance(another_fish, Fish):
            if self.scientific_name == another_fish.scientific_name:
                if self.in_species_temperament == 'peaceful':
                    return True
                else:
                    raise in_species_competition_error(
                        'In species competition exists between two {}s'.format(self.scientific_name))
            elif self.scientific_name != another_fish.scientific_name:
                if self.cross_species_temperament == 'peaceful' and another_fish.cross_species_temperament == 'peaceful':
                    return True
                elif self.cross_species_temperament == 'aggressive/territorial' or another_fish.cross_species_temperament == 'aggressive/territorial':
                    raise cross_species_competition_error('Cross species competition exists between {} and {}'.format(
                        self.scientific_name, another_fish.scientific_name))
                elif self.cross_species_temperament == 'aggressive to smaller':
                    if self.size_max > another_fish.size_min:
                        raise cross_species_competition_error('Cross species competition exists between {} and {}, {} with size {} may attack {} with size {}'.format(
                            self.scientific_name, another_fish.scientific_name, self.scientific_name, self.size_max, another_fish.scientific_name, another_fish.size_min))
                    else:
                        return True
                elif another_fish.cross_species_temperament == 'aggressive to smaller':
                    if another_fish.size_max > self.size_min:
                        raise cross_species_competition_error('Cross species competition exists between {} and {}, {} with size {} may attack {} with size {}'.format(
                            self.scientific_name, another_fish.scientific_name, another_fish.scientific_name, another_fish.size_max, self.scientific_name, self.size_min))
                    else:
                        return True

        else:
            raise Exception("The object is not fish")
