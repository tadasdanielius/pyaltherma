import json

from pyaltherma.const import VALID_RESPONSE_CODES
from pyaltherma.errors import PathException, AlthermaResponseException


def query_object(o, json_path, raise_exception=False, convert_to_none=True):
    location_steps = json_path.split('/')
    if isinstance(o, str):
        o = json.loads(o)
    for idx, step in enumerate(location_steps):
        if step not in o:
            if raise_exception:
                raise PathException(f'{json_path} step: {step} not found in object')

            if idx == len(location_steps) - 1 and convert_to_none:
                return None
        o = o.get(step, {})

    return o


def assert_response(request, response):
    resp_code = query_object(response, 'm2m:rsp/rsc')
    if resp_code not in VALID_RESPONSE_CODES:
        raise AlthermaResponseException(f'Response code {resp_code} is invalid.')
