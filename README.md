# pyaltherma
Python library to control Daikin Altherma heat pump
Tested only with BRP069A61

# Usage

```python3
async with aiohttp.ClientSession() as session:
    conn = DaikinWSConnection(session, 'IP_ADDRESS')
    device = AlthermaController(conn)
    await device.discover_units()
    tank = device.hot_water_tank
    climate = device.climate_control
    print(f'Tank / Target temperature: {await tank.tank_temperature} / {await tank.target_temperature}')
    print(f"Indoor/outdoor temperature: {await climate.indoor_temperature}/{await climate.outdoor_temperature}")
    await climate.turn_off()
    await climate.turn_on()
    await conn.close()
```
see example.py for more details.

# Status
Currently, the implementation is in early stage. At the moment it does not support schedules and energy consumption.
