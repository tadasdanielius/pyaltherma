import asyncio
import aiohttp

from pyaltherma.comm import DaikinWSConnection
from pyaltherma.controllers import AlthermaController, AlthermaClimateControlController, AlthermaUnitController, \
    AlthermaWaterTankController


async def print_header(cc: AlthermaUnitController):
    print(f"UNIT: {await cc.unit_name}")
    print(f"Indoor settings: {await cc.indoor_settings} / Indoor software: {await cc.indoor_software}")
    print(f"Outdoor settings: {await cc.outdoor_software}")
    print(f"Remocon settings: {await cc.remocon_settings} / Remocon software: {await cc.remocon_software}")


async def turn_off_on(cc):
    print('We are going to turn off the climate control and turn back on again after 5 minutes')
    await cc.turn_off()
    print(f'Is it on? {await cc.is_turned_on}')
    await asyncio.sleep(5)
    print('turning back on again')
    await cc.turn_on()
    print(f'Did we turned it on? {await cc.is_turned_on}')


async def climate_ctrl_test(cc: AlthermaClimateControlController):
    await print_header(cc)
    print(f"error state: {await cc.error_state}")
    print(f"Climate control cooling conf: {cc.climate_control_cooling_configuration}")
    print(f"Climate control heating conf: {cc.climate_control_heating_configuration}")

    print(f"Indoor/outdoor temperature: {await cc.indoor_temperature}/{await cc.outdoor_temperature}")
    print(f"leaving_water_temperature_current: {await cc.leaving_water_temperature_current}")

    await turn_off_on(cc)

    print(f'Operation mode: {await cc.operation_mode}')

    print(f'leaving_water_temperature_heating: {await cc.leaving_water_temperature_heating}')
    print(f'leaving_water_temperature_cooling: {await cc.leaving_water_temperature_cooling}')
    print(f'leaving_water_temperature_auto: {await cc.leaving_water_temperature_auto}')
    print(f'leaving_water_temperature_offset_heating: {await cc.leaving_water_temperature_offset_heating}')
    print(f'leaving_water_temperature_offset_cooling: {await cc.leaving_water_temperature_offset_cooling}')
    print(f'leaving_water_temperature_offset_auto: {await cc.leaving_water_temperature_offset_auto}')

    await cc.set_leaving_water_temperature_offset_heating(2)

    print('- States --')
    print(f'States {await cc.states}')
    print(f'error_state {await cc.error_state}')
    print(f'installer_state {await cc.installer_state}')
    print(f'target_temperature_overruled_state {await cc.target_temperature_overruled_state}')
    print(f'warning_state {await cc.warning_state}')
    print(f'emergency_state {await cc.emergency_state}')
    print(f'control_mode_state {await cc.control_mode_state}')
    print('======================================================')


async def test_powerful(cc):
    print(f'Turning on powerful. Is powerful now? {await cc.powerful}')
    await cc.set_powerful(True)
    await asyncio.sleep(5)
    print(f'Is powerful now? {await cc.powerful}')
    print(f'Target temperature: {await cc.target_temperature}')
    await asyncio.sleep(5)
    await cc.set_powerful(False)
    await asyncio.sleep(5)
    print(f'Powerful is off now. Is powerful now? {await cc.powerful}')
    await cc.set_target_temperature(45)
    print(f'Target temperature: {await cc.target_temperature}')


async def water_tank_test(cc: AlthermaWaterTankController):
    await print_header(cc)
    await turn_off_on(cc)
    print(f'Tank / Target temperature: {await cc.tank_temperature} / {await cc.target_temperature}')
    await test_powerful(cc)
    print(f'domestic_hot_water_temperature_heating: {await cc.domestic_hot_water_temperature_heating}')
    await cc.set_target_temperature(45)
    print(f'domestic_hot_water_temperature_heating: {await cc.domestic_hot_water_temperature_heating}')
    print("=========================================================")

async def main():
    daikin_ip = '192.168.1.10'
    async with aiohttp.ClientSession() as session:
        conn = DaikinWSConnection(session, daikin_ip)
        device = AlthermaController(conn)
        await device.discover_units()
        print(f'device error state: {await device.error_state}')
        cc = device.climate_control
        await climate_ctrl_test(cc)
        await water_tank_test(device.hot_water_tank)
        await conn._client.close()


if __name__ == '__main__':
    asyncio.run(main())
