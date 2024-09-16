from __future__ import annotations

import json
import logging
from http import HTTPStatus
from typing import Any, Iterable, Literal, Sequence
from urllib.parse import urljoin

from shmdash._datatypes import (
    Annotation,
    Attribute,
    Data,
    Setup,
    VirtualChannel,
    _format_datetime,
)
from shmdash._exceptions import ResponseError
from shmdash._http import HTTPRequest, HTTPResponse, HTTPSession, HTTPSessionDefault

logger = logging.getLogger(__name__)


class Client:
    """SHM Dash client."""

    def __init__(
        self,
        url: str,
        api_key: str,
        *,
        http_session: HTTPSession | None = None,
    ):
        """
        Initialize SHM Dash client.

        Args:
            url: Base URL to dashboard server, e.g. https://shmdash.de
            api_key: API key
            http_session: HTTP session
        """
        logger.info("Initialize SHM Dash client: %s", url)
        self._url = url
        self._api_key = api_key
        self._session = http_session if http_session else HTTPSessionDefault()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        await self.close()

    def _upload_url(self, endpoint: str):
        base_upload_url = urljoin(self._url, "/upload/vjson/v1/")
        return urljoin(base_upload_url, endpoint)

    def _dev_url(self, endpoint: str):
        base_dev_url = urljoin(self._url, "/dev/")
        return urljoin(base_dev_url, endpoint)

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

    async def _request(
        self,
        method: Literal["GET", "POST", "DELETE"],
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> HTTPResponse:
        response = await self._session.request(
            HTTPRequest(
                method,
                url,
                content=json.dumps(json_body) if json_body else None,
                headers={
                    "Content-Type": "application/json",
                    "UPLOAD-API-KEY": self._api_key,
                },
            )
        )
        self._check_response(response)
        return response

    async def get_setup(self) -> Setup:
        response = await self._request("GET", self._upload_url("setup"))
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
            await self._request(
                "POST",
                self._upload_url("setup"),
                json_body=Setup(list(attributes), list(virtual_channels)).to_dict(),
            )
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

    async def _post_commands(self, commands: Iterable[dict[str, Any]]):
        await self._request(
            "POST",
            self._upload_url("commands"),
            json_body={"commands": tuple(commands)},
        )

    async def add_attribute(self, attribute: Attribute):
        """
        Add attribute / channel.

        Args:
            attribute: Attribute definition
        """
        logger.info("Add attribute %s", attribute.identifier)
        commands = [
            {
                "cmdName": "addAttribute",
                "attributeId": str(attribute.identifier),
                **attribute.to_dict(),
            },
        ]
        await self._post_commands(commands)

    async def add_virtual_channel(self, virtual_channel: VirtualChannel):
        """
        Add virtual channel / channel group.

        Args:
            virtual_channel: Virtual channel definition
        """
        logger.info("Add virtual channel %s", virtual_channel.identifier)
        commands = [
            {
                "cmdName": "addVirtualChannel",
                "virtualChannelId": str(virtual_channel.identifier),
                **virtual_channel.to_dict(),
            },
        ]
        await self._post_commands(commands)

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
        commands = [
            {
                "cmdName": "addVirtualChannelAttributes",
                "virtualChannelId": str(virtual_channel_id),
                "attributes": attribute_ids,
            },
        ]
        await self._post_commands(commands)

    async def upload_data(self, virtual_channel_id: str, data: Sequence[Data]):
        """
        Upload data to virtual channel.

        Args:
            virtual_channel_id: Identifier of virtual channel
            data: List of data to upload
        """
        logger.debug("Upload %d data sets to virtual channel %s", len(data), virtual_channel_id)
        try:
            response = await self._request(
                "POST",
                self._upload_url("data"),
                json_body={
                    "conflict": "IGNORE",
                    "data": [
                        (
                            virtual_channel_id,
                            _format_datetime(record.timestamp),
                            *record.values,  # noqa: PD011
                        )
                        for record in data
                    ],
                },
            )
            # expected reponse content:
            # {
            #     "0": { "success": 2 },
            #     "1": { "error": "Key (abs_date_time)=(2018-09-27 15:51:14) already exists." }
            # }
            for identifier, results in response.json().items():
                unsuccessful = len(data) - results.get("success", len(data))
                if unsuccessful > 0:
                    logger.warning(
                        "Ignored %d uploads to virtual channel %s", unsuccessful, identifier
                    )
                if "error" in results:
                    logger.warning(
                        "Error uploading to virtual channel %s: %s", identifier, results["error"]
                    )
        except ResponseError as e:
            if e.status == HTTPStatus.REQUEST_ENTITY_TOO_LARGE and len(data) > 1:
                mid = len(data) // 2
                logger.debug("Retry upload with smaller batch size: %d", mid)
                await self.upload_data(virtual_channel_id, data[:mid])
                await self.upload_data(virtual_channel_id, data[mid:])
            else:
                raise

    async def upload_annotation(self, annotation: Annotation):
        """
        Upload an annotation.

        Args:
            annotation: Annotation
        """
        await self._request("POST", self._upload_url("annotation"), json_body=annotation.to_dict())

    async def delete_data(self):
        """
        Delete all time-series data.

        Data of other upload sources (different API keys) won't be affected.
        """
        logger.warning("Delete all data")
        await self._request("DELETE", self._dev_url("timeseriesdata"))

    async def recreate(self):
        """
        Delete all time-series data and setup information.

        Data and setups of other upload sources (different API keys) won't be affected.
        """
        logger.warning("Delete all data and setup information")
        await self._request("GET", self._dev_url("recreate"))

    async def close(self):
        """Close session."""
        logger.debug("Close SHM Dash HTTP client session")
        await self._session.close()
