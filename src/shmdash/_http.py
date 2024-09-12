from __future__ import annotations

import json
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import aiohttp

from shmdash._exceptions import RequestError


@dataclass
class HTTPResponse:
    """HTTP response."""

    url: str  #: URL of the request
    method: str  #: Method of the request
    status: int  #: HTTP status code of response
    headers: dict[str, str]  #: HTTP headers of the response
    content: bytes  #: Body of the response
    encoding: str | None  #: Content encoding of the response

    def text(self) -> str:
        """Decode content as text."""
        return self.content.decode(encoding=self.encoding or "utf-8")

    def json(self) -> Any:
        """Decode content as JSON."""
        return json.loads(self.text())


@dataclass
class HTTPSessionOptions:
    headers: dict[str, str] | None = None  #: HTTP headers to include when sending requests
    timeout: int | None = None  #: Timeout for sending requests
    verify: bool = True  #: Perform SSL certificate validation for HTTPS requests


class HTTPSession(ABC):
    @abstractmethod
    def __init__(self, *, options: HTTPSessionOptions):
        """
        Initialize HTTP session.

        Params:
            options: Session options
        """

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        await self.close()

    @abstractmethod
    async def close(self):
        """Close HTTP session."""

    @abstractmethod
    async def get(self, url: str, *, params: dict[str, Any] | None = None) -> HTTPResponse:
        """Send a GET request."""

    @abstractmethod
    async def post(self, url: str, *, data: Any = None) -> HTTPResponse:
        """Send a POST request."""

    @abstractmethod
    async def delete(self, url: str) -> HTTPResponse:
        """Send a DELETE request."""


# ------------------------------------ aiohttp implementation ------------------------------------ #


class HTTPSessionAiohttp(HTTPSession):
    def __init__(self, *, options: HTTPSessionOptions):
        self._session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(verify_ssl=options.verify),
            headers=options.headers,
            timeout=aiohttp.ClientTimeout(total=options.timeout),
        )

    async def close(self):
        await self._session.close()

    @staticmethod
    @contextmanager
    def _convert_exceptions():
        try:
            yield
        except aiohttp.ClientError as e:
            raise RequestError(str(e)) from e

    @staticmethod
    async def _convert_response(response: aiohttp.ClientResponse) -> HTTPResponse:
        return HTTPResponse(
            url=str(response.url),
            method=response.method,
            status=response.status,
            headers=dict(response.headers.items()),
            content=await response.read(),
            encoding=response.get_encoding(),
        )

    async def get(self, url: str, *, params: dict[str, Any] | None = None) -> HTTPResponse:
        with self._convert_exceptions():
            async with self._session.get(url, params=params) as response:
                return await self._convert_response(response)

    async def post(self, url: str, *, data: Any = None) -> HTTPResponse:
        with self._convert_exceptions():
            async with self._session.post(url, data=data) as response:
                return await self._convert_response(response)

    async def delete(self, url: str) -> HTTPResponse:
        with self._convert_exceptions():
            async with self._session.delete(url) as response:
                return await self._convert_response(response)
