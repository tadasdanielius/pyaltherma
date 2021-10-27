from enum import Enum

VALID_RESPONSE_CODES = (2000, 2001)


class ClimateControlMode(Enum):
    Auto = "auto"
    Cooling = "cooling"
    Heating = "heating"


class ControlConfiguration(Enum):
    WeatherDependent = 1
    Fixed = 2
