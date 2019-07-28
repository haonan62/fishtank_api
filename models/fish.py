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

# the user model specifies its fields (or columns) declaratively, like django
class Fish(BaseModel):
    scientific_name = CharField(unique=True,primary_key=True)
    common_name = CharField()
    family_name = CharField()
    size_min=IntegerField()
    size_max=IntegerField()
    ph_min=DoubleField()
    ph_max=DoubleField()
    water_hardness_min=IntegerField()
    water_hardness_max=IntegerField()
    temperature_min=IntegerField()
    temperature_max=IntegerField()
    reproduce_method = CharField()
    origin = CharField()
    in_species_temperament=CharField()
    cross_species_temperament=CharField()
    fishtank_position=CharField()

    def __str__(self):
        return self.scientific_name
    
    def to_dic(self):
        return{
            'scientific name':self.scientific_name,
            'common name':self.common_name,
            'family name':self.family_name,
            'minimum size':self.size_min,
            'maximum size': self.size_max,
            'minimum ph': self.ph_min,
            'maximum ph': self.ph_max,
            'minimum water hardness': self.water_hardness_min,
            'maximum water hardness': self.water_hardness_max,
            'minimum temperature':self.temperature_min,
            'maximum temperature': self.temperature_max,
            'reproduce method': self.reproduce_method,
            'origin': self.origin,
            'in species temperament': self.in_species_temperament,
            'cross species temperament': self.cross_species_temperament,
            'fishtank position': self.fishtank_position
        }
    
    def share_common_temperature_zone(self,another_fish):
        if isinstance(another_fish, Fish):
            if self.temperature_min>another_fish.temperature_max or self.temperature_max<another_fish.temperature_min:
                raise temperature_not_common_error('Temperature ranges are not common between {} and {}'.format(self.scientific_name,another_fish.scientific_name))
            else:
                return True
        else:
            raise Exception("The object is not fish")
    
    def share_common_ph_zone(self,another_fish):
        if isinstance(another_fish, Fish):
            if self.ph_min>another_fish.ph_max or self.ph_max<another_fish.ph_min:
                raise ph_not_common_error('Ph ranges are not common between {} and {}'.format(self.scientific_name,another_fish.scientific_name))
            else:
                return True
        else:
            raise Exception("The object is not fish")

    def share_common_water_hardness_zone(self,another_fish):
        if isinstance(another_fish, Fish):
            if self.water_hardness_min>another_fish.water_hardness_max or self.water_hardness_max<another_fish.water_hardness_min:
                raise water_hardness_not_common_error('Water hardness ranges are not common between {} and {}'.format(self.scientific_name,another_fish.scientific_name))
            else:
                return True
        else:
            raise Exception("The object is not fish")

    def live_peacefully_with(self,another_fish):
        if isinstance(another_fish, Fish):
            if self.scientific_name==another_fish.scientific_name:
                if self.in_species_temperament=='peaceful':
                    return True
                else:
                    raise in_species_competition_error('In species competition exists between two {}s'.format(self.scientific_name))
            elif self.scientific_name!=another_fish.scientific_name:
                if self.cross_species_temperament=='peaceful' and another_fish.cross_species_temperament=='peaceful':
                    return True
                elif self.cross_species_temperament=='aggressive/territorial' or another_fish.cross_species_temperament=='aggressive/territorial':
                    raise cross_species_competition_error('Cross species competition exists between {} and {}'.format(self.scientific_name,another_fish.scientific_name))
                elif self.cross_species_temperament=='aggressive to smaller':
                    if self.size_max>another_fish.size_min:
                        raise cross_species_competition_error('Cross species competition exists between {} and {}, {} with size {} may attack {} with size {}'.format(self.scientific_name,another_fish.scientific_name,self.scientific_name,self.size_max,another_fish.scientific_name,another_fish.size_min))
                    else:
                        return True
                elif another_fish.cross_species_temperament=='aggressive to smaller':
                    if another_fish.size_max>self.size_min:
                        raise cross_species_competition_error('Cross species competition exists between {} and {}, {} with size {} may attack {} with size {}'.format(self.scientific_name,another_fish.scientific_name,another_fish.scientific_name,another_fish.size_max,self.scientific_name,self.size_min))
                    else:
                        return True
                
        else:
            raise Exception("The object is not fish")



