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