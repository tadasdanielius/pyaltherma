import json
import logging

from pyaltherma.comm import DaikinWSConnection
from pyaltherma.const import ClimateControlMode, ControlConfiguration
from pyaltherma.errors import AlthermaException
from pyaltherma.utils import query_object

logger = logging.getLogger(__name__)


class AlthermaUnit:
    def __init__(self, unit_id, profile):
        self._profile = profile
        self._unit_id = unit_id
        self._sync_status = None
        self._sensors = []
        self._unit_status = []
        self._operations = []
        self._initialized = False

    def init_unit(self):
        if not self._initialized:
            self._parse()

    def _parse(self):
        profile = self._profile
        if 'SyncStatus' in profile:
            self._sync_status = profile['SyncStatus']
        if 'Sensor' in profile:
            self._sensors = profile['Sensor']
        if 'UnitStatus' in profile:
            self._unit_status = profile['UnitStatus']
        if 'Operation' in profile:
            self._operations = profile['Operation']

    @property
    def unit_states(self):
        return self._unit_status

    @property
    def operation_list(self):
        return list(self._operations.keys())

    @property
    def operation_config(self):
        return self._operations

    @property
    def sensor_list(self):
        return self._sensors

    @property
    def unit_id(self):
        return self._unit_id


class AlthermaUnitController:
    def __init__(self, unit: AlthermaUnit, connection: DaikinWSConnection):
        self._connection = connection
        self._unit = unit
        self._unit.init_unit()

    async def read(self, query_type, prop):
        destination = f'{self._dest}/{query_type}/{prop}/la'
        result = await self._connection.request(destination)
        try:
            result_value = query_object(result, 'm2m:rsp/pc/m2m:cin/con')
        except:
            raise AlthermaException(f'Failed to read {query_type} {prop} data.')
        return result_value

    async def read_sensor(self, sensor):
        return await self.read(query_type='Sensor', prop=sensor)

    async def read_sensors(self):
        sensors = self._unit.sensor_list
        results = {}
        for sensor in sensors:
            results[sensor] = await self.read_sensor(sensor)
        return results

    async def read_operation(self, operation):
        # First letter must be uppercase however profile returns lower case
        if operation == 'powerful':
            operation = 'Powerful'
        return await self.read(query_type='Operation', prop=operation)

    async def read_state(self, status):
        resp = await self.read(query_type='UnitStatus', prop=status)
        return bool(resp)

    async def read_states(self):
        results = {}
        for state in self._unit.unit_states:
            results[state] = await self.read_state(state)
        return results

    async def read_operations(self):
        operations = list(self._unit._operations.keys())
        results = {}
        for operation in operations:
            results[operation] = await self.read_operation(operation)
        return results

    async def call_operation(self, operation, value=None):
        destination = f'{self._dest}/Operation/{operation}'
        if value is not None:
            key = operation if operation != 'Powerful' else 'powerful'
            conf = self._unit.operation_config[key]

            if 'heating' in conf and isinstance(conf['heating'], dict):
                conf = conf['heating']
                conf['settable'] = True

            if isinstance(conf, list):
                v = str(value) if key == 'powerful' else value
                valid = v in conf
            else:
                valid = conf['settable'] and conf['minValue'] <= value <= conf['maxValue']
            if not valid:
                raise AlthermaException(
                    f'Invalid argument {value} for operation {operation} or operation is not settable.')
            payload = {
                'con': value,
                'cnf': 'text/plain:0'
            }
        else:
            payload = None
        return await self._connection.request(destination, payload=payload)

    @property
    def _dest(self):
        return f'/[0]/MNAE/{self._unit.unit_id}'

    @property
    def sensors(self):
        return self._unit.sensor_list

    @property
    def operations(self):
        return self._unit.operation_list

    @property
    async def unit_name(self) -> str:
        return await self.read('UnitIdentifier', 'Name')

    @property
    async def indoor_settings(self):
        return await self.read(query_type='UnitInfo', prop='Version/IndoorSettings')

    @property
    async def indoor_software(self):
        return await self.read(query_type='UnitInfo', prop='Version/IndoorSoftware')

    @property
    async def outdoor_software(self):
        return await self.read(query_type='UnitInfo', prop='Version/OutdoorSoftware')

    @property
    async def remocon_software(self):
        return await self.read(query_type='UnitInfo', prop='Version/RemoconSoftware')

    @property
    async def remocon_settings(self):
        return await self.read(query_type='UnitInfo', prop='Version/RemoconSettings')


class AlthermaWaterTankController(AlthermaUnitController):

    @property
    async def tank_temperature(self):
        return await self.read_sensor('TankTemperature')

    @property
    async def target_temperature(self):
        return await self.read_operation('TargetTemperature')

    async def set_target_temperature(self, value: float):
        await self.call_operation('TargetTemperature', value)

    @property
    async def powerful(self) -> bool:
        current_value = str(await self.read_operation('Powerful'))
        return True if current_value == "1" else False

    async def set_powerful(self, value: bool):
        await self.call_operation('Powerful', int(value))

    @property
    async def domestic_hot_water_temperature_heating(self) -> float:
        return await self.read_operation('DomesticHotWaterTemperatureHeating')

    async def set_domestic_hot_water_temperature_heating(self, value: float):
        await self.call_operation('DomesticHotWaterTemperatureHeating', value)

    async def turn_on(self):
        await self.call_operation("Power", "on")

    async def turn_off(self):
        await self.call_operation("Power", "standby")

    @property
    async def is_turned_on(self) -> bool:
        return True if await self.read_operation("Power") == "on" else False

    @property
    async def states(self) -> dict:
        return await self.read_states()

    @property
    async def error_state(self) -> bool:
        return await self.read_state('ErrorState')

    @property
    async def installer_state(self) -> bool:
        return await self.read_state('InstallerState')

    @property
    async def weather_dependent_state(self) -> bool:
        return await self.read_state('WeatherDependentState')

    @property
    async def warning_state(self) -> bool:
        return await self.read_state('WarningState')

    @property
    async def emergency_state(self) -> bool:
        return await self.read_state('EmergencyState')


class AlthermaClimateControlController(AlthermaUnitController):
    @property
    def climate_control_heating_configuration(self) -> ControlConfiguration:
        conf = self._unit.operation_config
        if 'LeavingWaterTemperatureOffsetHeating' in conf and conf['LeavingWaterTemperatureOffsetHeating']['settable']:
            return ControlConfiguration.WeatherDependent
        else:
            return ControlConfiguration.Fixed

    @property
    def climate_control_cooling_configuration(self) -> ControlConfiguration:
        conf = self._unit.operation_config
        if 'LeavingWaterTemperatureOffsetCooling' in conf and conf['LeavingWaterTemperatureOffsetCooling']['settable']:
            return ControlConfiguration.WeatherDependent
        else:
            return ControlConfiguration.Fixed

    @property
    async def indoor_temperature(self) -> float:
        return await self.read_sensor("IndoorTemperature")

    @property
    async def outdoor_temperature(self) -> float:
        return await self.read_sensor("OutdoorTemperature")

    @property
    async def leaving_water_temperature_current(self):
        return await self.read_sensor("LeavingWaterTemperatureCurrent")

    async def turn_on(self):
        await self.call_operation("Power", "on")

    async def turn_off(self):
        await self.call_operation("Power", "standby")

    @property
    async def is_turned_on(self) -> bool:
        return await self.read_operation("Power") == "on"

    @property
    async def operation_mode(self) -> ClimateControlMode:
        return ClimateControlMode(await self.read_operation('OperationMode'))

    @operation_mode.setter
    async def operation_mode(self, mode: ClimateControlMode):
        await self.call_operation("OperationMode", mode.value)

    @property
    async def leaving_water_temperature_heating(self) -> int:
        return await self.read_operation('LeavingWaterTemperatureHeating')

    async def set_leaving_water_temperature_heating(self, value: int):
        await self.call_operation('LeavingWaterTemperatureHeating', value)

    @property
    async def leaving_water_temperature_cooling(self) -> int:
        return await self.read_operation("LeavingWaterTemperatureCooling")

    async def set_leaving_water_temperature_cooling(self, value: int):
        await self.call_operation("LeavingWaterTemperatureCooling", value)

    @property
    async def leaving_water_temperature_auto(self) -> int:
        return await self.read_operation("LeavingWaterTemperatureAuto")

    @property
    async def leaving_water_temperature_offset_heating(self) -> int:
        return await self.read_operation("LeavingWaterTemperatureOffsetHeating")

    async def set_leaving_water_temperature_offset_heating(self, value: int):
        await self.call_operation("LeavingWaterTemperatureOffsetHeating", value)

    @property
    async def leaving_water_temperature_offset_cooling(self) -> int:
        return await self.read_operation("LeavingWaterTemperatureOffsetCooling")

    async def set_leaving_water_temperature_offset_cooling(self, value: int):
        await self.call_operation("LeavingWaterTemperatureOffsetCooling", value)

    @property
    async def leaving_water_temperature_offset_auto(self) -> int:
        return await self.read_operation("LeavingWaterTemperatureOffsetAuto")

    async def set_leaving_water_temperature_offset_auto(self, value: int):
        await self.call_operation("LeavingWaterTemperatureOffsetAuto", value)

    @property
    async def states(self) -> dict:
        return await self.read_states()

    @property
    async def error_state(self) -> bool:
        return await self.read_state('ErrorState')

    @property
    async def installer_state(self) -> bool:
        return await self.read_state('InstallerState')

    @property
    async def target_temperature_overruled_state(self) -> bool:
        return await self.read_state('TargetTemperatureOverruledState')

    @property
    async def warning_state(self) -> bool:
        return await self.read_state('WarningState')

    @property
    async def emergency_state(self) -> bool:
        return await self.read_state('EmergencyState')

    @property
    async def control_mode_state(self) -> str:
        return await self.read(query_type='UnitStatus', prop='ControlModeState')


class AlthermaController:
    def __init__(self, connection: DaikinWSConnection):
        self._connection = connection
        self._altherma_units = {}
        self._hot_water_tank = None
        self._climate_control = None
        self._base_unit: AlthermaUnitController = None

    @property
    def hot_water_tank(self) -> AlthermaWaterTankController:
        return self._hot_water_tank

    @property
    def climate_control(self) -> AlthermaClimateControlController:
        return self._climate_control

    def _guess_unit_type(self, i, unit, con):
        sensors = con["Sensor"]
        if "TankTemperature" in sensors:
            unit_controller = AlthermaWaterTankController(unit, self._connection)
            self._hot_water_tank = unit_controller
            logger.info(f'Discovered unit: Water Tank Controller with id: {i}')
        elif "LeavingWaterTemperatureCurrent" in sensors:
            unit_controller = AlthermaClimateControlController(unit, self._connection)
            self._climate_control = unit_controller
            logger.info(f'Discovered unit: Climate Control with id: {i}')
        else:
            unit_controller = AlthermaUnitController(unit, self._connection)
            logger.warning(f'Discovered unrecognized unit with id: {i}')
        return unit_controller

    async def discover_units(self, guess_units=True):
        for i in range(0, 10):
            dest = f"[0]/MNAE/{i}/UnitProfile/la"
            try:
                resp_obj = await self._connection.request(dest)
                resp_code = query_object(resp_obj, 'm2m:rsp/rsc')
                if resp_code != 2000:
                    logger.debug('No more devices found')
                    break
                _con = json.loads(query_object(resp_obj, 'm2m:rsp/pc/m2m:cin/con'))
                unit = AlthermaUnit(i, _con)
                if guess_units and "Sensor" in _con:
                    unit_controller = self._guess_unit_type(i, unit, _con)
                else:
                    unit_controller = AlthermaUnitController(unit, self._connection)
                self._altherma_units[i] = unit_controller
                logger.debug(f'Discovered unit {i}')
            except AlthermaException:
                logger.debug('No more devices found')
                break
        # Likely to be general unit
        self._base_unit = self._altherma_units[0]

    @property
    async def error_state(self) -> bool:
        return await self._base_unit.read_state('ErrorState')
