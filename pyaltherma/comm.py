import json

from aiohttp import ClientSession

from pyaltherma.proto import Request
import logging

logger = logging.getLogger(__name__)


class DaikinWSConnection:
    def __init__(self, session: ClientSession, host, timeout=None):
        self._host = host
        self._session: ClientSession = session
        self._client = None
        self._timeout = timeout

    async def connect(self):
        address = f"ws://{self._host}/mca"
        self._client = await self._session.ws_connect(address)

    async def close(self):
        self._client.close()

    async def request(self, dest, payload=None, wait_for_response=True, assert_response_fn=None):

        if self._client is None:
            await self.connect()

        pkg: Request = Request(dest, payload)
        data = pkg.serialize()
        logger.debug(f"[OUT]: {dest} {data}")
        _ = await self._client.send_str(data)
        if wait_for_response:
            response_str = await self._client.receive_str(timeout=self._timeout)
            logger.debug(f"[IN]: {response_str}")
            response = json.loads(response_str)
            if callable(assert_response_fn):
                assert_response_fn(response)

        else:
            response = None

        return response
