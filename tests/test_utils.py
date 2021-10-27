from unittest import TestCase

import pytest

from pyaltherma.const import VALID_RESPONSE_CODES
from pyaltherma.utils import query_object, assert_response
from pyaltherma.errors import PathException, AlthermaResponseException


class Test_query_object(TestCase):
    def test_json_path(self):
        d = {'lvl1_value': 1,
         'lvl1': {
             'lvl2_value': 2,
             'lvl2': {
                 'lvl3_value': 3
             }
         }}
        value = query_object(d, 'lvl1_value')
        assert value == 1

        value = query_object(d, 'lvl1/lvl2_value')
        assert value == 2

        value = query_object(d, 'lvl1/lvl2/lvl3_value')
        assert value == 3

    def test_json_path_exception(self):
        d = {'lvl1_value': 1}
        with pytest.raises(PathException):
            d = query_object(d, 'lvl1/lvl2_value', raise_exception=True)

    def test_json_none_values(self):
        d = {
            'lvl1_value': 1,
            'lvl2': {

            }
        }
        value = query_object(d, 'lvl1/lvl2/lvl3', convert_to_none=True)
        assert value is None

        value = query_object(d, 'lvl1/lvl2/lvl3', convert_to_none=False)
        assert isinstance(value, dict)


class Test_Response_Error(TestCase):
    def test_if_throws_error_on_invalid_rsc_code(self):
        resp = {
            'm2m:rsp': {'rsc': 4000, 'rqi': 1234}
        }
        req = {
            'm2m:rqp': {'rqi': 1234}
        }
        with pytest.raises(AlthermaResponseException):
            assert_response(req, resp)

    def test_if_no_error_is_thrown(self):
        resp = {
            'm2m:rsp': {'rsc': 2000, 'rqi': 1234}
        }
        req = {
            'm2m:rqp': {'rqi': 1234}
        }
        assert_response(req, resp)
        for resp_code in VALID_RESPONSE_CODES:
            resp = {
                'm2m:rsp': {'rsc': resp_code}
            }
            assert_response(req, resp)