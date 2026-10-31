from peewee import *
from fishtank.db import BaseModel, SEED_DATABASE
from fishtank.simulation.errors import *

# the committed fish database
DATABASE = SEED_DATABASE


FISHBASE_SUMMARY_URL = 'https://www.fishbase.se/summary/{}'

# A temperament that is not known yet, such a fish is kept apart from every other species
UNKNOWN_TEMPERAMENT = 'unknown'

# The temperaments live_peacefully_with understands
IN_SPECIES_TEMPERAMENTS = ('peaceful', 'peaceful to males', 'peaceful to females', 'aggressive/territorial',
                           UNKNOWN_TEMPERAMENT)
CROSS_SPECIES_TEMPERAMENTS = ('peaceful', 'aggressive/territorial', 'aggressive to smaller', UNKNOWN_TEMPERAMENT)


# Every fish is identified by its id, the scientific name is unique but may change when a species is renamed
# Fish imported from FishBase do not have a size, reproduce method, origin or fishtank position, these are None
class Fish(BaseModel):
    id = AutoField()
    scientific_name = CharField(unique=True)
    common_name = CharField(null=True)
    family_name = CharField()
    size_min = IntegerField(null=True)
    size_max = IntegerField(null=True)
    ph_min = DoubleField()
    ph_max = DoubleField()
    water_hardness_min = IntegerField()
    water_hardness_max = IntegerField()
    temperature_min = IntegerField()
    temperature_max = IntegerField()
    reproduce_method = CharField(null=True)
    origin = CharField(null=True)
    in_species_temperament = CharField()
    cross_species_temperament = CharField()
    fishtank_position = CharField(null=True)
    fishbase_spec_code = IntegerField(null=True, unique=True)
    data_source = CharField()

    def __str__(self):
        return self.scientific_name

    # FishBase asks for a link back to the source page of the data
    def fishbase_url(self):
        if self.fishbase_spec_code is None:
            return None
        return FISHBASE_SUMMARY_URL.format(self.fishbase_spec_code)

    def to_dic(self):
        return{
            'id': self.id,
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
            'fishtank_position': self.fishtank_position,
            'data_source': self.data_source,
            'fishbase_url': self.fishbase_url(),
            'pictures': [picture.to_dic() for picture in self.pictures]
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
    #A fish whose temperament is not known yet is never assumed to be peaceful, this is checked before anything else

    def live_peacefully_with(self, another_fish):
        if isinstance(another_fish, Fish):
            if self.scientific_name == another_fish.scientific_name:
                if self.in_species_temperament == 'peaceful':
                    return True
                else:
                    raise in_species_competition_error(
                        'In species competition exists between two {}s'.format(self.scientific_name))
            elif self.scientific_name != another_fish.scientific_name:
                if self.cross_species_temperament == UNKNOWN_TEMPERAMENT or another_fish.cross_species_temperament == UNKNOWN_TEMPERAMENT:
                    raise cross_species_competition_error('Temperament is not known yet between {} and {}'.format(
                        self.scientific_name, another_fish.scientific_name))
                elif self.cross_species_temperament == 'peaceful' and another_fish.cross_species_temperament == 'peaceful':
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


# A picture is not stored, only the url where it is hosted, the credit follows FishBase's terms:
# full attribution to the person or organization and the indication 'from FishBase'
class FishPicture(BaseModel):
    id = AutoField()
    fish = ForeignKeyField(Fish, backref='pictures', column_name='fish_id')
    url = TextField(unique=True)
    author = TextField(null=True)
    licence = TextField()
    source_url = TextField()

    class Meta:
        table_name = 'fish_picture'

    def credit(self):
        if self.author is None:
            return 'from FishBase'
        return '{}, from FishBase'.format(self.author)

    def to_dic(self):
        return {
            'url': self.url,
            'author': self.author,
            'licence': self.licence,
            'credit': self.credit(),
            'source_url': self.source_url
        }
