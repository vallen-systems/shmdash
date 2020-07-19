import asyncio
import functools
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Sequence, Tuple
from urllib.parse import urljoin

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class Attribute:
    """Attribute / channel defintion."""

    identifier: str  #: Unique identifier (alphanumeric and "_", max. 32 char)
    desc: str  #: Channel description
    unit: Optional[str]  #: Measurement unit
    format_: str  #: Format string, e.g. %s for strings, %d for integers, %.2f for floats
    type_: str  #: Type: dateTime, int16, unit16, int32, uint32, int64, float32, float64 or string
    soft_limits: Tuple[Optional[float], Optional[float]] = (None, None)  #: Min/max values
    diagram_scale: str = "lin"  #: Diagram scale: lin or log


@dataclass
class VirtualChannel:
    """Virtual channel / channel group definition."""

    identifier: str  #: Unique identifier (alphanumeric and "_", max. 32 char) VAE requires int
    name: str  #: Channel group name
    desc: str  #: Channel group description
    #: List of assigned attribute / channel identifiers.
    #: Following channels have specific meaning: AbsDateTime, DSET, X, Y
    #: Following statistics can be applied:
    #: min(id), max(id), avg(id), sum(id), stdDev(id), nbVals(id), var(id), deltaT()
    attributes: List[Attribute]
    #: Properties used for interpretation of the data:
    #: - hardcoded on the server side: STREAM, LOC (require X, Y), STAT (statistics)
    #: - used in VAE: HIT, PAR, ...
    #: Use for example: [STREAM, HIT]
    properties: Optional[List[str]] = None


@dataclass
class UploadData:
    """Upload data."""

    timestamp: datetime  #: Absolute datetime (unique!)
    data: Sequence[float]  #: List of values in order of the virtual channel attributes


class RedirectionError(Exception):
    """HTTP status codes 3xx."""


class ClientError(Exception):
    """HTTP status codes 4xx."""


class BadRequestError(ClientError):
    """HTTP status code 400."""


class UnauthorizedError(ClientError):
    """HTTP status code 401."""


class ServerError(Exception):
    """HTTP status codes 5xx."""


class PayloadTooLargeError(ServerError):
    """
    Special case of HTTP status code 500.

    {
        "statusCode":500,
        "timestamp":"2020-07-09T16:15:03.106Z",
        "path":"/upload/vjson/v1/data",
        "method":"POST",
        "message":"PayloadTooLargeError: request entity too large"
    }
    """


def connection_exception_handling(func):
    assert asyncio.iscoroutinefunction(func)

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except asyncio.TimeoutError:
            raise ConnectionError("Timeout error")
        except aiohttp.ServerConnectionError as e:
            raise ConnectionError(str(e) if str(e) else "Server connection error")
        except aiohttp.ClientConnectionError as e:
            raise ConnectionError(str(e) if str(e) else "Client connection error")

    return async_wrapper


class DaqMonInterface:
    """DaqMon interface."""

    def __init__(self, url: str, api_key: str):
        logger.info(f"Initialize DaqMon interface: {url}")

        self._url_api = urljoin(url, "/upload/vjson/v1/")
        self._url_setup = urljoin(self._url_api, "setup")
        self._url_data = urljoin(self._url_api, "data")
        self._url_commands = urljoin(self._url_api, "commands")

        logger.debug("Open DaqMon HTTP client session")
        self._session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(verify_ssl=False),  # SSL verification problems on cWave
            headers={"content-type": "application/json", "UPLOAD-API-KEY": api_key,},
            timeout=aiohttp.ClientTimeout(total=60),
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        await self.close()

    @staticmethod
    async def _check_and_handle_errors(response: aiohttp.ClientResponse):
        status = response.status  # e.g. 401
        status_class = status // 100 * 100  # e.g. 400

        if status_class == 200:
            return

        response_text = await response.text()
        try:
            response_dict = json.loads(response_text)
        except ValueError:
            response_dict = {}

        error_message = "HTTP {code} error for {method} request {url}: {message}".format(
            code=status,
            method=response.method,
            url=response.url,
            message=response_dict.get("message", response_text),  # JSON dict with message expected
        )

        if status_class == 300:
            raise RedirectionError(error_message)

        if status_class == 400:
            if status == 400:
                raise BadRequestError(error_message)
            if status == 401:
                raise UnauthorizedError(error_message)
            raise ClientError(error_message)

        if status_class == 500:
            if "PayloadTooLargeError" in response_dict.get("message", ""):
                raise PayloadTooLargeError(error_message)
            raise ServerError(error_message)

        raise RuntimeError(f"Uncaught error: {error_message}")

    @connection_exception_handling
    async def _get_setup(self):
        async with self._session.get(self._url_setup) as response:
            await self._check_and_handle_errors(response)
            return await response.json()

    @connection_exception_handling
    async def get_attributes(self) -> List[Attribute]:
        setup = await self._get_setup()
        return [
            Attribute(
                identifier=k,
                desc=v.get("descr"),
                unit=v.get("unit"),
                format_=v.get("format"),
                type_=v.get("type"),
                soft_limits=v.get("softLimits"),
                diagram_scale=v.get("diagramScale", "lin"),
            )
            for k, v in setup["attributes"].items()
        ]

    @connection_exception_handling
    async def get_virtual_channels(self) -> List[VirtualChannel]:
        setup = await self._get_setup()
        return [
            VirtualChannel(
                identifier=k,
                name=v.get("name"),
                desc=v.get("desc"),
                attributes=v.get("attributes"),
                properties=v.get("prop"),
            )
            for k, v in setup["virtual_channels"].items()
        ]

    @connection_exception_handling
    async def add_attribute(self, attribute: Attribute):
        existing = {a.identifier: a for a in await self.get_attributes()}
        if attribute.identifier in existing:
            logger.info(f"Attribute {attribute.identifier} already exists")
            return

        logger.info(f"Add attribute {attribute.identifier}")
        query_dict = dict(
            commands=[
                dict(
                    cmdName="addAttribute",
                    attributeId=attribute.identifier,
                    descr=attribute.desc,
                    unit=attribute.unit,
                    format=attribute.format_,
                    type=attribute.type_,
                    softLimits=attribute.soft_limits,
                    diagramScale=attribute.diagram_scale,
                )
            ]
        )
        query_json = json.dumps(query_dict)
        async with self._session.post(self._url_commands, data=query_json) as response:
            await self._check_and_handle_errors(response)

    @connection_exception_handling
    async def add_virtual_channel(self, virtual_channel: VirtualChannel):
        existing = {vc.identifier: vc for vc in await self.get_virtual_channels()}
        if virtual_channel.identifier in existing:
            logger.info(f"Virtual channel {virtual_channel.identifier} already exists")
            return

        logger.info(f"Add virtual channel {virtual_channel.identifier}")
        query_dict = dict(
            commands=[
                dict(
                    cmdName="addVirtualChannel",
                    virtualChannelId=virtual_channel.identifier,
                    name=virtual_channel.name,
                    descr=virtual_channel.desc,
                    attributes=virtual_channel.attributes,
                    prop=virtual_channel.properties,
                )
            ]
        )
        query_json = json.dumps(query_dict)
        async with self._session.post(self._url_commands, data=query_json) as response:
            await self._check_and_handle_errors(response)

    @connection_exception_handling
    async def _upload_data_chunk(self, virtual_channel_id: str, data: Sequence[UploadData]):
        def convert_datetime(timestamp):
            return timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

        query_dict = dict(
            conflict="IGNORE",
            data=[[virtual_channel_id, convert_datetime(d.timestamp), *d.data] for d in data],
        )
        query_json = json.dumps(query_dict)

        async with self._session.post(self._url_data, data=query_json) as response:
            await self._check_and_handle_errors(response)

            # expected reponse:
            # {
            #     "0": {
            #         "success": 2
            #     },
            #     "1": {
            #         "error": "Key (abs_date_time)=(2018-09-27 15:51:14) already exists."
            #     }
            # }

            response_dict = await response.json()

            for identifier, results in response_dict.items():
                if "error" not in results:
                    continue

                error_message = results["error"]
                error_prefix = f"Error uploading to virtual channel {identifier}"

                if "ChannelGroup not found" in error_message:
                    raise ValueError(f"{error_prefix}: {identifier} does not exist")
                if error_message == "INSERT has more expressions than target columns":
                    raise ValueError(f"{error_prefix}: {error_message}")

                logger.warning(f"{error_prefix}, ignore data: {error_message}")

    @connection_exception_handling
    async def upload_data(
        self, virtual_channel_id: str, data: Sequence[UploadData], chunksize: int = 2000
    ):
        def chunks(lst, n):
            """Yield successive n-sized chunks from lst."""
            for i in range(0, len(lst), n):
                yield lst[i : i + n]

        logger.debug(f"Upload {len(data)} data sets to virtual channel {virtual_channel_id}")
        for data_chunk in chunks(data, chunksize):
            try:
                await self._upload_data_chunk(virtual_channel_id, data_chunk)
            except PayloadTooLargeError as e:
                new_chunksize = int(chunksize / 2)
                logger.warning(f"{e}. Retry with smaller chunksize {new_chunksize}")
                if new_chunksize <= 1:
                    raise
                await self.upload_data(virtual_channel_id, data_chunk, chunksize=new_chunksize)

    @connection_exception_handling
    async def recreate(self):
        """
        Delete all time-series data and setup information.

        Data and setups of other upload sources (different API keys) will not be affected.
        """
        logger.warning("Delete all data and setup information")
        url = urljoin(self._url_api, "/dev/recreate")
        async with self._session.get(url) as response:
            await self._check_and_handle_errors(response)

    async def close(self):
        logger.debug("Close DaqMon HTTP client session")
        await self._session.close()
