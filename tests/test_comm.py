import asyncio
import json

import pytest

from pyaltherma.comm import DaikinWSConnection


class FakeClient:
    def __init__(self, replies=(), hang=False):
        self.sent = []
        self.replies = list(replies)
        self.hang = hang
        self.closed = False

    async def send_str(self, data):
        self.sent.append(json.loads(data))

    async def receive_str(self):
        if self.hang:
            await asyncio.sleep(3600)
        reply = self.replies.pop(0)
        # None means: echo the rqi of the last request
        if reply is None:
            reply = {'m2m:rsp': {'rsc': 2000, 'rqi': self.sent[-1]['m2m:rqp']['rqi'], 'pc': 'fresh'}}
        return json.dumps(reply)

    async def close(self):
        self.closed = True


def connection(client, timeout=30):
    conn = DaikinWSConnection(session=None, host='test', timeout=timeout)
    conn._client = client
    return conn


def test_stale_response_is_skipped():
    stale = {'m2m:rsp': {'rsc': 2000, 'rqi': 'old00', 'pc': 'stale'}}
    client = FakeClient(replies=[stale, None])
    response = asyncio.run(connection(client).request('/[0]/MNAE/1/Operation/Power/la'))
    assert response['m2m:rsp']['pc'] == 'fresh'
    assert not client.closed


def test_timeout_closes_socket_and_raises():
    client = FakeClient(hang=True)
    with pytest.raises(TimeoutError):
        asyncio.run(connection(client, timeout=0.05).request('/[0]/MNAE/1/Operation/Power/la'))
    assert client.closed


def test_close_without_connection():
    asyncio.run(DaikinWSConnection(session=None, host='test').close())
