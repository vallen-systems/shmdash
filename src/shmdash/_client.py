from __future__ import annotations

import json
import logging
from datetime import timezone
from http import HTTPStatus
from typing import Sequence
from urllib.parse import urljoin

from shmdash._datatypes import Attribute, Setup, UploadData, VirtualChannel
from shmdash._exceptions import ResponseError
from shmdash._http import HTTPResponse, HTTPSession, HTTPSessionAiohttp, HTTPSessionOptions

logger = logging.getLogger(__name__)


class Client:
    """SHM Dash client."""

    def __init__(
        self,
        url: str,
        api_key: str,
        *,
        verify_ssl: bool = False,
        http_session: type[HTTPSession] = HTTPSessionAiohttp,
    ):
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
        self._session = http_session(
            options=HTTPSessionOptions(
                headers={
                    "Content-Type": "application/json",
                    "UPLOAD-API-KEY": api_key,
                },
                verify=verify_ssl,
            )
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        await self.close()

    @staticmethod
    def _check_response(response: HTTPResponse):
        """Check client response and handle errors."""

        def get_message() -> str | None:
            response_text = response.text()
            if response_text:
                try:
                    return json.loads(response_text).get("message", response_text)
                except ValueError:
                    return response_text
            return None

        if response.status >= 400:  # noqa: PLR2004
            raise ResponseError(
                url=str(response.url),
                method=response.method,
                status=response.status,
                message=get_message(),
            )

    async def get_setup(self) -> Setup:
        response = await self._session.get(self._url_setup)
        self._check_response(response)
        return Setup.from_dict(response.json())

    async def setup(
        self,
        attributes: Sequence[Attribute],
        virtual_channels: Sequence[VirtualChannel],
    ):
        """
        Upload setup.

        If a setup already exists, attributes and virtual channels are added to the existing setup.
        """
        setup = await self.get_setup()
        if setup.is_empty():
            logger.info("Upload setup")
            query = Setup(list(attributes), list(virtual_channels)).to_dict()
            response = await self._session.post(self._url_setup, data=json.dumps(query))
            self._check_response(response)
        else:
            existing_attribute_ids = {attr.identifier: attr for attr in setup.attributes}
            existing_virtual_channel_ids = {vc.identifier: vc for vc in setup.virtual_channels}
            for attribute in attributes:
                if attribute.identifier not in existing_attribute_ids:
                    await self.add_attribute(attribute)
                else:
                    logger.debug("Attribute %s already exists", attribute.identifier)
            for virtual_channel in virtual_channels:
                if virtual_channel.identifier not in existing_virtual_channel_ids:
                    await self.add_virtual_channel(virtual_channel)
                else:
                    logger.debug("Virtual channel %s already exists", virtual_channel.identifier)

    async def add_attribute(self, attribute: Attribute):
        """
        Add attribute / channel.

        Args:
            attribute: Attribute definition
        """
        logger.info("Add attribute %s", attribute.identifier)
        query = {
            "commands": [
                {
                    "cmdName": "addAttribute",
                    "attributeId": str(attribute.identifier),
                    **attribute.to_dict()[attribute.identifier],
                },
            ],
        }
        response = await self._session.post(self._url_commands, data=json.dumps(query))
        self._check_response(response)

    async def add_virtual_channel(self, virtual_channel: VirtualChannel):
        """
        Add virtual channel / channel group.

        Args:
            virtual_channel: Virtual channel definition
        """
        logger.info("Add virtual channel %s", virtual_channel.identifier)
        query = {
            "commands": [
                {
                    "cmdName": "addVirtualChannel",
                    "virtualChannelId": str(virtual_channel.identifier),
                    **virtual_channel.to_dict()[virtual_channel.identifier],
                },
            ],
        }
        response = await self._session.post(self._url_commands, data=json.dumps(query))
        self._check_response(response)

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
        query = {
            "commands": [
                {
                    "cmdName": "addVirtualChannelAttributes",
                    "virtualChannelId": str(virtual_channel_id),
                    "attributes": attribute_ids,
                },
            ],
        }
        response = await self._session.post(self._url_commands, data=json.dumps(query))
        self._check_response(response)

    async def _upload_data_chunk(self, virtual_channel_id: str, data: Sequence[UploadData]):
        def convert_datetime(timestamp):
            return timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

        query = {
            "conflict": "IGNORE",
            "data": [[virtual_channel_id, convert_datetime(d.timestamp), *d.data] for d in data],
        }
        response = await self._session.post(self._url_data, data=json.dumps(query))
        self._check_response(response)

        # expected reponse:
        # {
        #     "0": {
        #         "success": 2
        #     },
        #     "1": {
        #         "error": "Key (abs_date_time)=(2018-09-27 15:51:14) already exists."
        #     }
        # }

        response_json = response.json()
        for identifier, results in response_json.items():
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

    async def delete_data(self):
        """
        Delete all time-series data.

        Data of other upload sources (different API keys) won't be affected.
        """
        logger.warning("Delete all data")
        url = urljoin(self._url_api, "/dev/timeseriesdata")
        response = await self._session.delete(url)
        self._check_response(response)

    async def recreate(self):
        """
        Delete all time-series data and setup information.

        Data and setups of other upload sources (different API keys) won't be affected.
        """
        logger.warning("Delete all data and setup information")
        url = urljoin(self._url_api, "/dev/recreate")
        response = await self._session.get(url)
        self._check_response(response)

    async def close(self):
        """Close session."""
        logger.debug("Close SHM Dash HTTP client session")
        await self._session.close()
