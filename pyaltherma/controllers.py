import json
import logging
import typing

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
        self._operations = {}
        self._initialized = False

    def init_unit(self):
        if not self._initialized:
            self.parse()

    def parse(self, profile=None):
        if profile is not None:
            self._profile = profile
        else:
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
    def operations(self):
        return self._operations

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
    def __init__(self, unit: AlthermaUnit, connection: DaikinWSConnection, function='generic'):
        self._connection = connection
        self._unit = unit
        self._unit.init_unit()
        self._function = function

    @property
    def unit(self):
        return self._unit

    async def refresh_profile(self):
        dest = f"[0]/MNAE/{self._unit.unit_id}/UnitProfile/la"
        resp_obj = await self._connection.request(dest)
        resp_code = query_object(resp_obj, 'm2m:rsp/rsc')
        if resp_code != 2000:
            raise AlthermaException('Failed to refresh device')
        _con = json.loads(query_object(resp_obj, 'm2m:rsp/pc/m2m:cin/con'))

        self._unit.parse(_con)
        logger.debug(f'Unit {self._unit.unit_id}/{self._function} profile refreshed.')

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
        operations = list(self._unit.operations.keys()) \
            if isinstance(self._unit.operations, dict) else self._unit.operations
        results = {}
        for operation in operations:
            results[operation] = await self.read_operation(operation)
        return results

    async def call_operation(self, operation, value=None):
        destination = f'{self._dest}/Operation/{operation}'
        if value is not None:
            key = operation if operation != 'Powerful' else 'powerful'
            conf = self._unit.operation_config[key]

            if 'heating' in conf and isinstance(conf, dict) and isinstance(conf['heating'], dict):
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

    async def get_current_state(self):
        sensors = await self.read_sensors()
        operations = await self.read_operations()
        states = await self.read_states()
        return {
            'sensors': sensors,
            'operations': operations,
            'states': states
        }

    @property
    def unit_function(self):
        return self._function

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

    @property
    async def model_number(self):
        return await self.read(query_type='UnitInfo', prop='ModelNumber')

    def __str__(self):
        return self._function


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

    async def set_operation_mode(self, mode: ClimateControlMode):
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
        self._base_unit: typing.Optional[AlthermaUnitController] = None

    @property
    def ws_connection(self):
        return self._connection

    async def get_current_state(self):
        status = {}
        for unit in self._altherma_units.values():
            unit_status = await unit.get_current_state()
            status[unit.unit_function] = unit_status
        return status

    @property
    def hot_water_tank(self) -> AlthermaWaterTankController:
        return self._hot_water_tank

    @property
    def climate_control(self) -> AlthermaClimateControlController:
        return self._climate_control

    async def device_info(self):
        """
        Information about adapter
        :return: details
        """
        info = {}
        o = await self._connection.request('/[0]/MNCSE-node/deviceInfo')
        info['serial_number'] = query_object(o, 'm2m:rsp/pc/m2m:dvi/dlb')
        info['manufacturer'] = query_object(o, 'm2m:rsp/pc/m2m:dvi/man')
        info['model_name'] = query_object(o, 'm2m:rsp/pc/m2m:dvi/mod')
        info['duty'] = query_object(o, 'm2m:rsp/pc/m2m:dvi/dty')
        info['miconID'] = query_object(o, 'm2m:rsp/pc/m2m:dvi/fwv')
        info['firmware'] = query_object(o, 'm2m:rsp/pc/m2m:dvi/swv')
        return info

    async def firmware(self):
        return await self._connection.request('/[0]/MNCSE-node/firmware')

    async def refresh(self):
        for u in self._altherma_units.values():
            try:
                await u.refresh_profile()
            except AlthermaUnitController:
                logger.error(f'Failed to refresh profile for unit {u}')

    async def _guess_unit(self, i, unit):
        req = await self._connection.request(f'[0]/MNAE/{i}')
        label = query_object(req, 'm2m:rsp/pc/m2m:cnt/lbl')
        if label == 'function/SpaceHeating':
            logger.info(f'Discovered unit: Climate Control with id: {i} {label}')
            unit_controller = AlthermaClimateControlController(unit, self._connection, label)
            self._climate_control = unit_controller
        elif label == 'function/DomesticHotWaterTank':
            logger.info(f'Discovered unit: Water Tank Controller with id: {i} {label}')
            unit_controller = AlthermaWaterTankController(unit, self._connection, label)
            self._hot_water_tank = unit_controller
        elif label == 'function/Adapter':
            logger.info(f'Discovered unit: function adapter: {i} {label}')
            unit_controller = AlthermaUnitController(unit, self._connection, label)
        else:
            unit_controller = AlthermaUnitController(unit, self._connection, label)
            logger.warning(f'Discovered unrecognized unit with id: {i} {label}')
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
                logger.debug(f'Discovered unit {i}')
                _con = json.loads(query_object(resp_obj, 'm2m:rsp/pc/m2m:cin/con'))
                unit = AlthermaUnit(i, _con)
                if guess_units:
                    unit_controller = await self._guess_unit(i, unit)
                else:
                    unit_controller = AlthermaUnitController(unit, self._connection)
                self._altherma_units[i] = unit_controller
            except AlthermaException:
                logger.debug('No more devices found')
                break
        # Likely to be general unit
        self._base_unit = self._altherma_units[0]

    @property
    async def error_state(self) -> bool:
        return await self._base_unit.read_state('ErrorState')
