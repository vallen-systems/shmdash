# ruff: noqa: F401

from __future__ import annotations

import asyncio
import functools
import json
import logging
from datetime import timezone
from http import HTTPStatus
from typing import Sequence
from urllib.parse import urljoin

import aiohttp

from shmdash._datatypes import (
    Attribute,
    AttributeType,
    DiagramScale,
    Setup,
    UploadData,
    VirtualChannel,
)
from shmdash._exceptions import ClientError, RequestError, ResponseError
from shmdash._utils import to_identifier

logger = logging.getLogger(__name__)


def _request_exception_handling(func):
    assert asyncio.iscoroutinefunction(func)  # noqa: S101

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except aiohttp.ClientError as e:
            raise RequestError(str(e)) from e

    return async_wrapper


async def _check_response(response: aiohttp.ClientResponse):
    """Check HTTP client response and handle errors."""
    status = HTTPStatus(response.status)

    if status.is_success:
        return

    response_text = await response.text()
    try:
        response_dict = json.loads(response_text)
        response_dict.get()
    except ValueError:
        response_dict = {}

    message = response_dict.get("message", response_text)  # JSON dict with message expected
    raise ResponseError(
        url=str(response.url),
        method=response.method,
        status=status,
        message=message if message else None,
    )


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

    @_request_exception_handling
    async def get_setup(self) -> Setup:
        async with self._session.get(self._url_setup) as response:
            await _check_response(response)
            setup_dict = await response.json()
            return Setup.from_dict(setup_dict)

    @_request_exception_handling
    async def has_setup(self) -> bool:
        """Check if an setup already exists."""
        setup = await self.get_setup()
        return setup.attributes and setup.virtual_channels

    @_request_exception_handling
    async def setup(
        self,
        attributes: Sequence[Attribute],
        virtual_channels: Sequence[VirtualChannel],
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
            query_dict = Setup(list(attributes), list(virtual_channels)).to_dict()
            query_json = json.dumps(query_dict)
            async with self._session.post(self._url_setup, data=query_json) as response:
                await _check_response(response)

    @_request_exception_handling
    async def get_attributes(self) -> list[Attribute]:
        """Get list of existing attributes."""
        setup = await self.get_setup()
        return setup.attributes

    @_request_exception_handling
    async def get_attribute(self, attribute_id: str) -> Attribute | None:
        """Get attribute by identifier."""
        return next(
            filter(
                lambda a: a.identifier == attribute_id,  # type: ignore[arg-type, union-attr]
                await self.get_attributes(),
            ),
            None,
        )

    @_request_exception_handling
    async def get_virtual_channels(self) -> list[VirtualChannel]:
        """Get list of existing virtual channels."""
        setup = await self.get_setup()
        return setup.virtual_channels

    @_request_exception_handling
    async def get_virtual_channel(self, virtual_channel_id: str) -> VirtualChannel | None:
        """Get virtual channel by identifier."""
        return next(
            filter(
                lambda a: a.identifier == virtual_channel_id,  # type: ignore[arg-type, union-attr]
                await self.get_virtual_channels(),
            ),
            None,
        )

    @_request_exception_handling
    async def add_attribute(self, attribute: Attribute):
        """
        Add attribute / channel.

        Args:
            attribute: Attribute definition
        """
        existing = {attr.identifier: attr for attr in await self.get_attributes()}
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
                },
            ],
        }
        query_json = json.dumps(query_dict)
        async with self._session.post(self._url_commands, data=query_json) as response:
            await _check_response(response)

    @_request_exception_handling
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
                },
            ],
        }
        query_json = json.dumps(query_dict)
        async with self._session.post(self._url_commands, data=query_json) as response:
            await _check_response(response)

    @_request_exception_handling
    async def add_virtual_channel_attributes(
        self,
        virtual_channel_id: str,
        attribute_ids: Sequence[str],
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
                },
            ],
        }
        query_json = json.dumps(query_dict)
        async with self._session.post(self._url_commands, data=query_json) as response:
            await _check_response(response)

    @_request_exception_handling
    async def _upload_data_chunk(self, virtual_channel_id: str, data: Sequence[UploadData]):
        def convert_datetime(timestamp):
            return timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

        query_dict = {
            "conflict": "IGNORE",
            "data": [[virtual_channel_id, convert_datetime(d.timestamp), *d.data] for d in data],
        }
        query_json = json.dumps(query_dict)

        async with self._session.post(self._url_data, data=query_json) as response:
            await _check_response(response)

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
                    logger.warning("%s, ignore data: %s", error_prefix, error_message)

    @_request_exception_handling
    async def upload_data(
        self,
        virtual_channel_id: str,
        data: Sequence[UploadData],
        chunksize: int = 128,
    ):
        """
        Upload data to virtual channel.

        Args:
            virtual_channel_id: Identifier of virtual channel
            data: List of data to upload
            chunksize: Default chunk size (chunk size will be reduced on errors)
        """

        def chunks(lst, n):
            """Yield successive n-sized chunks from lst."""
            for i in range(0, len(lst), n):
                yield lst[i : i + n]

        logger.debug("Upload %d data sets to virtual channel %s", len(data), virtual_channel_id)
        for data_chunk in chunks(data, chunksize):
            try:
                await self._upload_data_chunk(virtual_channel_id, data_chunk)
            except ResponseError as e:  # noqa:PERF203
                if e.status == HTTPStatus.REQUEST_ENTITY_TOO_LARGE:
                    new_chunksize = int(chunksize / 2)
                    logger.warning("%s. Retry with smaller chunksize %d", e, new_chunksize)
                    if new_chunksize <= 1:
                        raise
                    await self.upload_data(virtual_channel_id, data_chunk, chunksize=new_chunksize)
                else:
                    raise

    @_request_exception_handling
    async def delete_data(self):
        """
        Delete all time-series data.

        Data of other upload sources (different API keys) won't be affected.
        """
        logger.warning("Delete all data")
        url = urljoin(self._url_api, "/dev/timeseriesdata")
        async with self._session.delete(url) as response:
            await _check_response(response)

    @_request_exception_handling
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
