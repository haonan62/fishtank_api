class FishError(Exception):
   """Base class for other exceptions"""
   pass
class ph_not_common_error(FishError):
   """Raised when there is no overlap between ph values"""
   pass
class temperature_not_common_error(FishError):
   """Raised when there is no overlap between temperature values"""
   pass
class water_hardness_not_common_error(FishError):
   """Raised when there is no overlap between water hardness values"""
   pass
class in_species_competition_error(FishError):
   """Raised when fish from the same species cannot live together"""
   pass
class cross_species_competition_error(FishError):
   """Raised when fish from the difference species cannot live together"""
   pass