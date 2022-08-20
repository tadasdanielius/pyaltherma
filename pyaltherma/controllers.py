import json
import logging
import typing

from pyaltherma.comm import DaikinWSConnection
from pyaltherma.const import ClimateControlMode, ControlConfiguration
from pyaltherma.errors import AlthermaException
from pyaltherma.profile import AlthermaUnit
from pyaltherma.utils import query_object

logger = logging.getLogger(__name__)


class AlthermaUnitController:
    def __init__(self, unit: AlthermaUnit, connection: DaikinWSConnection, function='generic'):
        self._connection = connection
        self._unit = unit
        self._unit.init_unit()
        self._function = function

        self._unit_name = None
        self._indoor_settings = None
        self._indoor_software = None
        self._outdoor_software = None
        self._remocon_settings = None
        self._remocon_software = None
        self._model_number = None

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

    async def read(self, query_type, prop=None):
        if prop is not None:
            destination = f'{self._dest}/{query_type}/{prop}/la'
        else:
            destination = f'{self._dest}/{query_type}/la'
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

    async def read_consumptions(self):
        if self.unit.consumptions_available:
            consumption_str = await self.read('Consumption')
            return json.loads(consumption_str)
        else:
            return {}

    async def read_operations(self):
        operations = list(self._unit.operations.keys()) \
            if isinstance(self._unit.operations, dict) else self._unit.operations
        results = {}
        for operation in operations:
            results[operation] = await self.read_operation(operation)
        return results

    async def call_operation(self, operation, value=None, validate=True):
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
                if validate:
                    if 'settable' not in conf:
                        conf['settable'] = True
                    valid = conf['settable'] and conf['minValue'] <= value <= conf['maxValue']
                else:
                    valid = True
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
        consumptions = await self.read_consumptions()
        return {
            'sensors': sensors,
            'operations': operations,
            'states': states,
            'consumption': consumptions
        }

    @property
    def unit(self):
        return self._unit

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
        if self._unit_name is None:
            self._unit_name = await self.read('UnitIdentifier', 'Name')
        return self._unit_name

    @property
    async def indoor_settings(self):
        if self._indoor_settings is None:
            self._indoor_settings = await self.read(query_type='UnitInfo', prop='Version/IndoorSettings')

    @property
    async def indoor_software(self):
        if self._indoor_software is None:
            self._indoor_software = await self.read(query_type='UnitInfo', prop='Version/IndoorSoftware')
        return self._indoor_software

    @property
    async def outdoor_software(self):
        if self._outdoor_software is None:
            self._outdoor_software = await self.read(query_type='UnitInfo', prop='Version/OutdoorSoftware')
        return self._outdoor_software

    @property
    async def remocon_software(self):
        if self._remocon_software is None:
            self._remocon_software = await self.read(query_type='UnitInfo', prop='Version/RemoconSoftware')
        return self._remocon_software

    @property
    async def remocon_settings(self):
        if self._remocon_settings is None:
            self._remocon_settings = await self.read(query_type='UnitInfo', prop='Version/RemoconSettings')
        return self._remocon_settings

    @property
    async def model_number(self):
        if self._model_number is None:
            self._model_number = await self.read(query_type='UnitInfo', prop='ModelNumber')
        return self._model_number

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
        self._profiles = []

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

    async def _guess_unit(self, i, unit, label):
        if label == 'function/SpaceHeating':
            logger.info(f'Discovered unit: Climate Control with id: {i} {label}')
            unit_controller = AlthermaClimateControlController(unit, self._connection, label)
            self._climate_control = unit_controller
        elif label == 'function/DomesticHotWaterTank' or 'function/DomesticHotWater':
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

                req = await self._connection.request(f'[0]/MNAE/{i}')
                label = query_object(req, 'm2m:rsp/pc/m2m:cnt/lbl')

                unit = AlthermaUnit(i, _con, label)
                if guess_units:
                    unit_controller = await self._guess_unit(i, unit, label)
                else:
                    unit_controller = AlthermaUnitController(unit, self._connection)
                unit_name = await unit_controller.unit_name
                unit_name = unit_name if unit_name is not None else 0

                self._profiles.append({
                    'idx': i, 'dest': dest, 'profile': _con, 'label': label, 'unit_name': unit_name
                })

                self._altherma_units[label] = unit_controller
            except AlthermaException:
                logger.debug('No more devices found')
                break
        # Likely to be general unit
        if 'function/Adapter' in self._altherma_units:
            self._base_unit = self._altherma_units['function/Adapter']
        elif 0 in self._altherma_units:
            self._base_unit = self._altherma_units[0]
        else:
            self._base_unit = None

    @property
    def altherma_units(self):
        return self._altherma_units

    @property
    def profiles(self):
        return self._profiles

    @property
    async def error_state(self) -> bool:
        return await self._base_unit.read_state('ErrorState')
