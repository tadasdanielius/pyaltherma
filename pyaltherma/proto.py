import uuid
import json


class Request:
    def __init__(self, dest, payload=None, user_agent='pyaltherma'):
        request = {'fr': user_agent, 'rqi': uuid.uuid4().hex[0:5], 'op': 2, 'to': dest}
        if payload:
            request['op'] = 1
            request['ty'] = 4
            request['pc'] = {
                'm2m:cin': payload
            }
        self._request = {
            'm2m:rqp': request
        }

    def serialize(self) -> str:
        o = json.dumps(self._request)
        return o
