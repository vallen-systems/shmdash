import asyncio
import functools
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from http import HTTPStatus
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple, Union
from urllib.parse import urljoin

import aiohttp

logger = logging.getLogger(__name__)


def to_identifier(identifier: Any) -> str:
    """Convert to identifier (alphanumeric and "_", max. 32 chars)."""
    result = str(identifier)
    result = re.sub(r"[^a-zA-Z0-9_]", "", result)  # remove non-allowed chars
    return result[:32]  # crop to max. 32 chars


class AttributeType(str, Enum):
    DATETIME = "dateTime"
    INT16 = "int16"
    UINT16 = "uint16"
    INT32 = "int32"
    UINT32 = "uint32"
    INT64 = "int64"
    FLOAT32 = "float32"
    FLOAT64 = "float64"
    STRING = "string"

    def __str__(self) -> str:
        return self.value


class DiagramScale(str, Enum):
    LIN = "lin"
    LOG = "log"

    def __str__(self) -> str:
        return self.value


@dataclass
class Attribute:
    """
    Attribute / channel defintion.

    Data structure for the JSON/dict representation:
    {
        "AbsDateTime": {
            "descr": "Absolutetime in ISO8601, UTC Zone (max. μs)",
            "unit": None,
            "type": "dateTime",
            "format": "YYYY-MM-DDThh:mm:ss[.ssssss]Z",
            "softLimits": [0, None],
            "diagramScale": "lin",
        }
    }
    """

    identifier: str  #: Unique identifier (alphanumeric and "_", max. 32 chars)
    desc: str  #: Channel description
    unit: Optional[str]  #: Measurement unit
    type: AttributeType  #: Type
    format: Optional[str] = None  #: Format string, e.g. %s for str, %d for int, %.2f for float
    soft_limits: Tuple[Optional[float], Optional[float]] = (None, None)  #: Min/max values
    diagram_scale: DiagramScale = DiagramScale.LIN

    @classmethod
    def from_dict(cls, attributes_dict: Dict[str, Dict[str, Any]]) -> Iterator["Attribute"]:
        """Create `Attribute` from parsed JSON dict."""
        for identifier, dct in attributes_dict.items():
            yield cls(
                identifier=identifier,
                desc=dct["descr"],
                unit=dct.get("unit"),
                type=AttributeType(dct["type"]),
                format=dct["format"],
                soft_limits=dct.get("softLimits", (None, None)),
                diagram_scale=DiagramScale(dct.get("diagramScale", "lin")),
            )

    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        """Convert into dict for JSON representation."""
        return {
            self.identifier: {
                "descr": self.desc,
                "unit": self.unit,
                "type": str(self.type),
                "format": self.format,
                "softLimits": self.soft_limits,
                "diagramScale": str(self.diagram_scale),
            }
        }


@dataclass
class VirtualChannel:
    """
    Virtual channel / channel group definition.

    Data structure for the JSON/dict representation:
    "1": {
        "name": "Control Signal",
        "descr": "Control signal voltage",
        "attributes": ["AbsDateTime", "DSET", "VOLTAGE"],
        "prop": ["STREAM", "PAR"]
    }
    """

    identifier: str  #: Unique identifier (alphanumeric and "_", max. 32 chars), VAE requires int
    name: str  #: Channel group name
    desc: Optional[str]  #: Channel group description
    #: List of assigned attribute / channel identifiers.
    #: Following channels have specific meaning: AbsDateTime, DSET, X, Y
    #: Following statistics can be applied:
    #: min(id), max(id), avg(id), sum(id), stdDev(id), nbVals(id), var(id), deltaT()
    attributes: List[str]
    #: Properties used for interpretation of the data:
    #: - hardcoded on the server side: STREAM, LOC (require X, Y), STAT (statistics)
    #: - used in VAE: HIT, PAR, ...
    #: Use for example: [STREAM, HIT]
    properties: Optional[List[str]] = None

    @classmethod
    def from_dict(cls, attributes_dict: Dict[str, Dict[str, Any]]) -> Iterator["VirtualChannel"]:
        """Create `VirtualChannel` from parsed JSON dict."""
        for identifier, dct in attributes_dict.items():
            yield cls(
                identifier=str(identifier),
                name=dct["name"],
                desc=dct.get("descr"),
                attributes=dct["attributes"],
                properties=dct.get("prop"),
            )

    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        """Convert into dict for JSON representation."""
        return {
            self.identifier: {
                "name": self.name,
                "descr": self.desc,
                "attributes": self.attributes,
                "prop": self.properties,
            }
        }


@dataclass
class UploadData:
    """Upload data."""

    timestamp: datetime  #: Absolute datetime (unique!)
    #: List of values in order of the virtual channel attributes
    data: Sequence[Union[int, float, str]]


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


def _connection_exception_handling(func):
    assert asyncio.iscoroutinefunction(func)

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except aiohttp.ServerConnectionError as e:
            raise ConnectionError(str(e) if str(e) else "Server connection error") from None
        except aiohttp.ClientConnectionError as e:
            raise ConnectionError(str(e) if str(e) else "Client connection error") from None

    return async_wrapper


async def _check_response(response: aiohttp.ClientResponse, request_body: Optional[str] = None):
    """Check HTTP client response and handle errors."""
    status = response.status  # e.g. 401
    status_class = status // 100 * 100  # e.g. 400

    if status_class == HTTPStatus.OK:
        return

    logger.error(
        "HTTP %s error for %s request %s: %s",
        status,
        response.method,
        response.url,
        request_body or "empty",
    )

    response_text = await response.text()
    try:
        response_dict = json.loads(response_text)
    except ValueError:
        response_dict = {}

    # pylint: disable=consider-using-f-string
    error_message = "HTTP {code} error for {method} request {url}: {message}".format(
        code=status,
        method=response.method,
        url=response.url,
        message=response_dict.get("message", response_text),  # JSON dict with message expected
    )

    if status_class == HTTPStatus.MULTIPLE_CHOICES:
        raise RedirectionError(error_message)

    if status_class == HTTPStatus.BAD_REQUEST:
        if status == HTTPStatus.BAD_REQUEST:
            raise BadRequestError(error_message)
        if status == HTTPStatus.UNAUTHORIZED:
            raise UnauthorizedError(error_message)
        raise ClientError(error_message)

    if status_class == HTTPStatus.INTERNAL_SERVER_ERROR:
        if "PayloadTooLargeError" in response_dict.get("message", ""):
            raise PayloadTooLargeError(error_message)
        raise ServerError(error_message)

    raise RuntimeError(f"Uncaught error: {error_message}")


def _merge_dicts(*dcts):
    result = {}
    for dct in dcts:
        result.update(dct)
    return result


class Client:
    """SHM Dash client."""

    def __init__(self, url: str, api_key: str, *, verify_ssl=False):
        """
        Initialize SHM Dash client.

        Args:
            url: Base URL to dashboard server, e.g. https://shmdash.de
            api_key: API key
            verify_ssl: Check SSL certifications
        """
        logger.info("Initialize SHM Dash client: %s", url)

        self._url_api = urljoin(url, "/upload/vjson/v1/")
        self._url_setup = urljoin(self._url_api, "setup")
        self._url_data = urljoin(self._url_api, "data")
        self._url_commands = urljoin(self._url_api, "commands")

        logger.debug("Open SHM Dash HTTP client session")
        self._session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(verify_ssl=verify_ssl),
            headers={
                "content-type": "application/json",
                "UPLOAD-API-KEY": api_key,
            },
            timeout=aiohttp.ClientTimeout(total=60),
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        await self.close()

    @_connection_exception_handling
    async def get_setup(self) -> Dict:
        async with self._session.get(self._url_setup) as response:
            await _check_response(response)
            return await response.json()

    @_connection_exception_handling
    async def has_setup(self) -> bool:
        """Check if an setup already exists."""
        setup = await self.get_setup()
        return bool(setup["attributes"]) and bool(setup["virtual_channels"])

    @_connection_exception_handling
    async def setup(
        self, attributes: Sequence[Attribute], virtual_channels: Sequence[VirtualChannel]
    ):
        """
        Upload setup.

        If a setup already exists, attributes and virtual channels are added to the existing setup.
        """
        if await self.has_setup():
            for attribute in attributes:
                await self.add_attribute(attribute)
            for virtual_channel in virtual_channels:
                await self.add_virtual_channel(virtual_channel)
        else:
            logger.info("Upload setup")
            query_dict = {
                "attributes": _merge_dicts(*(attribute.to_dict() for attribute in attributes)),
                "virtual_channels": _merge_dicts(
                    *(virtual_channel.to_dict() for virtual_channel in virtual_channels)
                ),
            }
            query_json = json.dumps(query_dict)
            async with self._session.post(self._url_setup, data=query_json) as response:
                await _check_response(response, request_body=query_json)

    @_connection_exception_handling
    async def get_attributes(self) -> List[Attribute]:
        """Get list of existing attributes."""
        setup = await self.get_setup()
        return list(Attribute.from_dict(setup["attributes"]))

    @_connection_exception_handling
    async def get_attribute(self, attribute_id: str) -> Optional[Attribute]:
        """Get attribute by identifier."""
        return next(
            filter(
                lambda a: a.identifier == attribute_id,  # type: ignore
                await self.get_attributes(),
            ),
            None,
        )

    @_connection_exception_handling
    async def get_virtual_channels(self) -> List[VirtualChannel]:
        """Get list of existing virtual channels."""
        setup = await self.get_setup()
        return list(VirtualChannel.from_dict(setup["virtual_channels"]))

    @_connection_exception_handling
    async def get_virtual_channel(self, virtual_channel_id: str) -> Optional[VirtualChannel]:
        """Get virtual channel by identifier."""
        return next(
            filter(
                lambda a: a.identifier == virtual_channel_id,  # type: ignore
                await self.get_virtual_channels(),
            ),
            None,
        )

    @_connection_exception_handling
    async def add_attribute(self, attribute: Attribute):
        """
        Add attribute / channel.

        Args:
            attribute: Attribute definition
        """
        existing = {a.identifier: a for a in await self.get_attributes()}
        if attribute.identifier in existing:
            logger.info("Attribute %s already exists", attribute.identifier)
            return

        logger.info("Add attribute %s", attribute.identifier)
        query_dict = {
            "commands": [
                {
                    "cmdName": "addAttribute",
                    "attributeId": str(attribute.identifier),
                    **attribute.to_dict()[attribute.identifier],
                }
            ]
        }
        query_json = json.dumps(query_dict)
        async with self._session.post(self._url_commands, data=query_json) as response:
            await _check_response(response, request_body=query_json)

    @_connection_exception_handling
    async def add_virtual_channel(self, virtual_channel: VirtualChannel):
        """
        Add virtual channel / channel group.

        Args:
            virtual_channel: Virtual channel definition
        """
        existing = {vc.identifier: vc for vc in await self.get_virtual_channels()}
        if str(virtual_channel.identifier) in existing:
            logger.info("Virtual channel %s already exists", virtual_channel.identifier)
            return

        logger.info("Add virtual channel %s", virtual_channel.identifier)
        query_dict = {
            "commands": [
                {
                    "cmdName": "addVirtualChannel",
                    "virtualChannelId": str(virtual_channel.identifier),
                    **virtual_channel.to_dict()[virtual_channel.identifier],
                }
            ]
        }
        query_json = json.dumps(query_dict)
        async with self._session.post(self._url_commands, data=query_json) as response:
            await _check_response(response, request_body=query_json)

    @_connection_exception_handling
    async def add_virtual_channel_attributes(
        self, virtual_channel_id: str, attribute_ids: Sequence[str]
    ):
        """
        Add attributes to existing virtual channel.

        Args:
            virtual_channel_id: Virtual channel identifier
            attribute_ids: Attribute identifiers
        """
        logger.info("Add attributes %s to virtual channel %s", attribute_ids, virtual_channel_id)
        query_dict = {
            "commands": [
                {
                    "cmdName": "addVirtualChannelAttributes",
                    "virtualChannelId": str(virtual_channel_id),
                    "attributes": attribute_ids,
                }
            ]
        }
        query_json = json.dumps(query_dict)
        async with self._session.post(self._url_commands, data=query_json) as response:
            await _check_response(response, request_body=query_json)

    @_connection_exception_handling
    async def _upload_data_chunk(self, virtual_channel_id: str, data: Sequence[UploadData]):
        def convert_datetime(timestamp):
            return timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

        query_dict = {
            "conflict": "IGNORE",
            "data": [[virtual_channel_id, convert_datetime(d.timestamp), *d.data] for d in data],
        }
        query_json = json.dumps(query_dict)

        async with self._session.post(self._url_data, data=query_json) as response:
            await _check_response(response, request_body=query_json)

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
                unsuccessful_uploads = len(data) - results.get("success", len(data))
                if unsuccessful_uploads > 0:
                    logger.warning(
                        "Ignored %d/%d uploads to virtual channel %s: Timestamps already exist",
                        unsuccessful_uploads,
                        len(data),
                        identifier,
                    )

                if "error" in results:
                    error_message = results["error"]
                    error_prefix = f"Error uploading to virtual channel {identifier}"

                    if "ChannelGroup not found" in error_message:
                        raise ValueError(f"{error_prefix}: {identifier} does not exist")
                    if "INSERT has more expressions than target columns" in error_message:
                        raise ValueError(f"{error_prefix}: {error_message}")

                    logger.warning("%s, ignore data: %s", error_prefix, error_message)

    @_connection_exception_handling
    async def upload_data(
        self, virtual_channel_id: str, data: Sequence[UploadData], chunksize: int = 128
    ):
        """
        Upload data to virtual channel.

        Args:
            virtual_channel_id: Identifier of virtual channel
            data: List of data to upload
            chunksize: Default chunksize (chunksize will be reduced on errors)
        """

        def chunks(lst, n):
            """Yield successive n-sized chunks from lst."""
            for i in range(0, len(lst), n):
                yield lst[i : i + n]

        logger.debug("Upload %d data sets to virtual channel %s", len(data), virtual_channel_id)
        for data_chunk in chunks(data, chunksize):
            try:
                await self._upload_data_chunk(virtual_channel_id, data_chunk)
            except PayloadTooLargeError as e:  # noqa:PERF203
                new_chunksize = int(chunksize / 2)
                logger.warning("%s. Retry with smaller chunksize %d", e, new_chunksize)
                if new_chunksize <= 1:
                    raise
                await self.upload_data(virtual_channel_id, data_chunk, chunksize=new_chunksize)

    @_connection_exception_handling
    async def delete_data(self):
        """
        Delete all time-series data.

        Data of other upload sources (different API keys) won't be affected.
        """
        logger.warning("Delete all data")
        url = urljoin(self._url_api, "/dev/timeseriesdata")
        async with self._session.delete(url) as response:
            await _check_response(response)

    @_connection_exception_handling
    async def recreate(self):
        """
        Delete all time-series data and setup information.

        Data and setups of other upload sources (different API keys) won't be affected.
        """
        logger.warning("Delete all data and setup information")
        url = urljoin(self._url_api, "/dev/recreate")
        async with self._session.get(url) as response:
            await _check_response(response)

    async def close(self):
        """Close session."""
        logger.debug("Close SHM Dash HTTP client session")
        await self._session.close()
