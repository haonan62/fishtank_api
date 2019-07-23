from peewee import *
import os.path

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
        return "The scientific name is "+ self.scientific_name+ ", The family is "+ self.family_name



