import asyncio
import json

from aiohttp import ClientSession

from pyaltherma.proto import Request
import logging

logger = logging.getLogger(__name__)


class DaikinWSConnection:
    def __init__(self, session: ClientSession, host, timeout=30):
        self._host = host
        self._session: ClientSession = session
        self._client = None
        self._timeout = timeout
        self._address = f"ws://{self._host}/mca"
        self._lock = asyncio.Lock()

    @property
    def host(self):
        return self._host

    @property
    def ws_address(self):
        return self._address

    async def connect(self):
        self._client = await self._session.ws_connect(self.ws_address)
        logger.debug(f'Connected to {self.ws_address}')

    async def close(self):
        async with self._lock:
            if self._client is not None:
                await self._client.close()

    async def request(self, dest, payload=None, wait_for_response=True, assert_response_fn=None):
        async with self._lock:
            result = await self._request(dest, payload, wait_for_response, assert_response_fn)
        return result

    async def _request(self, dest, payload=None, wait_for_response=True, assert_response_fn=None):

        if self._client is None:
            await self.connect()

        if self._client.closed:
            await self.connect()

        pkg: Request = Request(dest, payload)
        data = pkg.serialize()
        logger.debug(f"[OUT]: {dest} {data}")
        try:
            async with asyncio.timeout(self._timeout):
                _ = await self._client.send_str(data)
                if not wait_for_response:
                    return None
                response = await self._receive(pkg.rqi)
        except BaseException:
            # Socket state is unknown (e.g. reply still in flight): drop it, next request reconnects
            await self._client.close()
            raise

        if callable(assert_response_fn):
            assert_response_fn(response)
        return response

    async def _receive(self, rqi):
        while True:
            response_str = await self._client.receive_str()
            logger.debug(f"[IN]: {response_str}")
            response = json.loads(response_str)
            if response.get('m2m:rsp', {}).get('rqi') == rqi:
                return response
            logger.debug(f'Skipping response not matching request {rqi}')
