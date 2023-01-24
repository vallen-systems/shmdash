import asyncio
import functools
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple, Union
from urllib.parse import urljoin

import aiohttp

logger = logging.getLogger(__name__)


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

    identifier: str  #: Unique identifier (alphanumeric and "_", max. 32 char)
    desc: str  #: Channel description
    unit: Optional[str]  #: Measurement unit
    type_: str  #: Type: dateTime, int16, unit16, int32, uint32, int64, float32, float64 or string
    format_: str  #: Format string, e.g. %s for strings, %d for integers, %.2f for floats
    soft_limits: Tuple[Optional[float], Optional[float]] = (None, None)  #: Min/max values
    diagram_scale: str = "lin"  #: Diagram scale: lin or log

    @classmethod
    def from_dict(cls, attributes_dict: Dict[str, Dict[str, Any]]) -> Iterator["Attribute"]:
        """Create `Attribute` from parsed JSON dict."""
        for identifier, dct in attributes_dict.items():
            yield cls(
                identifier=identifier,
                desc=dct["descr"],
                unit=dct.get("unit"),
                type_=dct["type"],
                format_=dct["format"],
                soft_limits=dct.get("softLimits", (None, None)),
                diagram_scale=dct.get("diagramScale", "lin"),
            )

    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        """Convert into dict for JSON representation."""
        return {
            self.identifier: dict(
                descr=self.desc,
                unit=self.unit,
                type=self.type_,
                format=self.format_,
                softLimits=self.soft_limits,
                diagramScale=self.diagram_scale,
            )
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

    identifier: str  #: Unique identifier (alphanumeric and "_", max. 32 char) VAE requires int
    name: str  #: Channel group name
    desc: Optional[str]  #: Channel group description
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
            # fmt: off
            self.identifier: dict(
                name=self.name,
                descr=self.desc,
                attributes=self.attributes,
                prop=self.properties,
            )
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


def connection_exception_handling(func):
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


async def check_response(response: aiohttp.ClientResponse):
    """Check HTTP client response and handle erros."""
    status = response.status  # e.g. 401
    status_class = status // 100 * 100  # e.g. 400

    if status_class == 200:
        return

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
        logger.info(f"Initialize SHM Dash client: {url}")

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

    @connection_exception_handling
    async def get_setup(self) -> Dict:
        async with self._session.get(self._url_setup) as response:
            await check_response(response)
            return await response.json()

    @connection_exception_handling
    async def has_setup(self) -> bool:
        """Check if an setup already exists."""
        setup = await self.get_setup()
        return bool(setup["attributes"]) and bool(setup["virtual_channels"])

    @connection_exception_handling
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
            query_dict = dict(
                # fmt: off
                attributes=_merge_dicts(
                    *(attribute.to_dict() for attribute in attributes)
                ),
                virtual_channels=_merge_dicts(
                    *(virtual_channel.to_dict() for virtual_channel in virtual_channels)
                ),
            )
            query_json = json.dumps(query_dict)
            async with self._session.post(self._url_setup, data=query_json) as response:
                await check_response(response)

    @connection_exception_handling
    async def get_attributes(self) -> List[Attribute]:
        """Get list of existing attributes."""
        setup = await self.get_setup()
        return list(Attribute.from_dict(setup["attributes"]))

    @connection_exception_handling
    async def get_attribute(self, attribute_id: str) -> Optional[Attribute]:
        """Get attribute by identifier."""
        return next(
            filter(
                lambda a: a.identifier == attribute_id,  # type: ignore
                await self.get_attributes(),
            ),
            None,
        )

    @connection_exception_handling
    async def get_virtual_channels(self) -> List[VirtualChannel]:
        """Get list of existing virtual channels."""
        setup = await self.get_setup()
        return list(VirtualChannel.from_dict(setup["virtual_channels"]))

    @connection_exception_handling
    async def get_virtual_channel(self, virtual_channel_id: str) -> Optional[VirtualChannel]:
        """Get virtual channel by identifier."""
        return next(
            filter(
                lambda a: a.identifier == virtual_channel_id,  # type: ignore
                await self.get_virtual_channels(),
            ),
            None,
        )

    @connection_exception_handling
    async def add_attribute(self, attribute: Attribute):
        """
        Add attribute / channel.

        Args:
            attribute: Attribute definition
        """
        existing = {a.identifier: a for a in await self.get_attributes()}
        if attribute.identifier in existing:
            logger.info(f"Attribute {attribute.identifier} already exists")
            return

        logger.info(f"Add attribute {attribute.identifier}")
        query_dict = dict(
            commands=[
                dict(
                    cmdName="addAttribute",
                    attributeId=str(attribute.identifier),
                    **attribute.to_dict()[attribute.identifier],
                )
            ]
        )
        query_json = json.dumps(query_dict)
        async with self._session.post(self._url_commands, data=query_json) as response:
            await check_response(response)

    @connection_exception_handling
    async def add_virtual_channel(self, virtual_channel: VirtualChannel):
        """
        Add virtual channel / channel group.

        Args:
            virtual_channel: Virtual channel definition
        """
        existing = {vc.identifier: vc for vc in await self.get_virtual_channels()}
        if str(virtual_channel.identifier) in existing:
            logger.info(f"Virtual channel {virtual_channel.identifier} already exists")
            return

        logger.info(f"Add virtual channel {virtual_channel.identifier}")
        query_dict = dict(
            commands=[
                dict(
                    cmdName="addVirtualChannel",
                    virtualChannelId=str(virtual_channel.identifier),
                    **virtual_channel.to_dict()[virtual_channel.identifier],
                )
            ]
        )
        query_json = json.dumps(query_dict)
        async with self._session.post(self._url_commands, data=query_json) as response:
            await check_response(response)

    @connection_exception_handling
    async def add_virtual_channel_attributes(
        self, virtual_channel_id: str, attribute_ids: Sequence[str]
    ):
        """
        Add attributes to existing virtual channel.

        Args:
            virtual_channel_id: Virtual channel identifier
            attribute_ids: Attribute identifiers
        """
        logger.info(f"Add attributes {attribute_ids} to virtual channel {virtual_channel_id}")
        query_dict = dict(
            commands=[
                dict(
                    cmdName="addVirtualChannelAttributes",
                    virtualChannelId=str(virtual_channel_id),
                    attributes=attribute_ids,
                )
            ]
        )
        query_json = json.dumps(query_dict)
        async with self._session.post(self._url_commands, data=query_json) as response:
            await check_response(response)

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
            await check_response(response)

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
                        f"Ignored {unsuccessful_uploads}/{len(data)} uploads to virtual channel "
                        f"{identifier}: Timestamps already exist"
                    )

                if "error" in results:
                    error_message = results["error"]
                    error_prefix = f"Error uploading to virtual channel {identifier}"

                    if "ChannelGroup not found" in error_message:
                        raise ValueError(f"{error_prefix}: {identifier} does not exist")
                    if "INSERT has more expressions than target columns" in error_message:
                        raise ValueError(f"{error_prefix}: {error_message}")

                    logger.warning(f"{error_prefix}, ignore data: {error_message}")

    @connection_exception_handling
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
            await check_response(response)

    async def close(self):
        """Close session."""
        logger.debug("Close SHM Dash HTTP client session")
        await self._session.close()
