from enum import Enum

VALID_RESPONSE_CODES = (2000, 2001)


class ClimateControlMode(Enum):
    Auto = "auto"
    Cooling = "cooling"
    Heating = "heating"
    Heating_Day = "heating_day"
    Heating_Night = "heating_night"


class ControlConfiguration(Enum):
    WeatherDependent = 1
    Fixed = 2
