import asyncio

import pytest

from pyaltherma.controllers import AlthermaController, AlthermaUnitController, AlthermaWaterTankController
from pyaltherma.errors import AlthermaException
from pyaltherma.profile import AlthermaUnit


class FakeConnection:
    def __init__(self, con=None):
        self.con = con
        self.requests = []

    async def request(self, dest, payload=None):
        self.requests.append((dest, payload))
        return {'m2m:rsp': {'rsc': 2000, 'pc': {'m2m:cin': {'con': self.con}}}}


def unit_controller(connection):
    profile = {'Operation': {'TargetTemperatureDay': {'minValue': 10.0, 'maxValue': 30.0, 'stepValue': 0.5}}}
    return AlthermaUnitController(AlthermaUnit(1, profile, 'function/SpaceHeating'), connection,
                                  'function/SpaceHeating')


@pytest.mark.parametrize('placeholder', ['$NULL', '--', -3276.5])
def test_read_placeholder_is_none(placeholder):
    controller = unit_controller(FakeConnection(con=placeholder))
    assert asyncio.run(controller.read_sensor('OutdoorTemperature')) is None


@pytest.mark.parametrize('value', [19.5, 0, 'on', 'heating_day'])
def test_read_real_value_is_kept(value):
    controller = unit_controller(FakeConnection(con=value))
    assert asyncio.run(controller.read_sensor('IndoorTemperature')) == value


def test_unsupported_operation_raises_without_sending():
    connection = FakeConnection()
    controller = unit_controller(connection)
    with pytest.raises(AlthermaException, match='LeavingWaterTemperatureOffsetHeating'):
        asyncio.run(controller.call_operation('LeavingWaterTemperatureOffsetHeating', 2))
    assert connection.requests == []


def test_supported_operation_is_sent():
    connection = FakeConnection()
    controller = unit_controller(connection)
    asyncio.run(controller.call_operation('TargetTemperatureDay', 20.5))
    dest, payload = connection.requests[0]
    assert dest == '/[0]/MNAE/1/Operation/TargetTemperatureDay'
    assert payload == {'con': 20.5, 'cnf': 'text/plain:0'}


def guess(label):
    controller = AlthermaController(connection=None)
    unit = AlthermaUnit(0, {'UnitStatus': ['ErrorState']}, label)
    unit_controller = asyncio.run(controller._guess_unit(0, unit, label))
    return controller, unit_controller


@pytest.mark.parametrize('label', ['function/Adapter', 'function/Unknown'])
def test_non_tank_unit_is_not_hot_water_tank(label):
    controller, unit_controller = guess(label)
    assert type(unit_controller) is AlthermaUnitController
    assert controller.hot_water_tank is None


@pytest.mark.parametrize('label', ['function/DomesticHotWaterTank', 'function/DomesticHotWater'])
def test_tank_unit_is_hot_water_tank(label):
    controller, unit_controller = guess(label)
    assert isinstance(unit_controller, AlthermaWaterTankController)
    assert controller.hot_water_tank is unit_controller


def test_refresh_logs_failed_unit_and_continues():
    class FailingConnection(FakeConnection):
        async def request(self, dest, payload=None):
            self.requests.append((dest, payload))
            return {'m2m:rsp': {'rsc': 4004}}

    connection = FailingConnection()
    controller = AlthermaController(connection)
    controller._altherma_units = {'a': unit_controller(connection), 'b': unit_controller(connection)}
    asyncio.run(controller.refresh())
    assert len(connection.requests) == 2
