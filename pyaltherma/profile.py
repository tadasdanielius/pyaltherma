class ConsumptionContent:
    def __init__(self, period, profile):
        self._profile = profile
        self._period = period
        self._contentCount = profile['contentCount']
        self._resolution = profile['resolution']

    @property
    def period(self):
        return self._period

    @property
    def contentCount(self):
        return self._contentCount

    @property
    def resolution(self):
        return self._resolution


class ConsumptionAction:
    def __init__(self, action, profile):
        self._profile = profile
        self._action = action
        self._content = {}
        self.parse()

    def parse(self):
        for period, content in self._profile.items():
            self._content[period] = ConsumptionContent(period, content)

    @property
    def consumption_contents(self):
        return self._content

    @property
    def action(self):
        return self._action


class ConsumptionType:
    def __init__(self, source, profile):
        self._profile = profile
        self._consumption_type = None
        self._unit = None
        self._source = source
        self._actions = {}

        self.parse()

    def parse(self):
        for action, details in self._profile.items():
            if isinstance(details, dict):
                consumption_action = ConsumptionAction(action, details)
                self._actions[action] = consumption_action

    @property
    def actions(self):
        return self._actions

    @property
    def consumption_source(self):
        return self._source

    @property
    def units(self):
        return self._unit

    @property
    def consumption_type(self):
        return self._consumption_type


class AlthermaUnit:
    def __init__(self, unit_id, profile, unit_function="function/Unknown"):
        self._profile = profile
        self._unit_id = unit_id
        self._sync_status = None
        self._sensors = []
        self._unit_status = []
        self._operations = {}
        self._initialized = False
        self._consumptions = {}
        self._unit_function = unit_function

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

        if 'Consumption' in profile:
            try:
                for consumption_type, consumption_profile in profile['Consumption'].items():
                    self._consumptions[consumption_type] = ConsumptionType(consumption_type, consumption_profile)
            except:
                self._consumptions = {}

    @property
    def unit_function(self):
        return self._unit_function

    @property
    def consumptions(self):
        return self._consumptions

    @property
    def consumption_types(self):
        return list(self._consumptions.keys())

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

    @property
    def consumptions_available(self):
        return len(self._consumptions.keys()) > 0