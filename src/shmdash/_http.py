from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal

import httpx

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
class HTTPRequest:
    """HTTP request."""

    method: Literal["GET", "OPTIONS", "HEAD", "POST", "PUT", "PATCH", "DELETE"]  #: HTTP method
    url: str  #: Request URL
    params: dict[str, Any] | None = None  #: Query parameters to include in the URL
    content: str | None = None  #: Binary content to include in the body of the request
    headers: dict[str, str] | None = None  #: HTTP headers to include in the request
    timeout: float | None = None  #: Timeout in seconds for sending requests


class HTTPSession(ABC):
    """HTTP session interface to wrap HTTP libraries."""

    @abstractmethod
    def __init__(self):
        """Initialize HTTP session."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        await self.close()

    @abstractmethod
    async def close(self):
        """Close HTTP session."""

    @abstractmethod
    async def request(self, request: HTTPRequest) -> HTTPResponse:
        """Send an HTTP request."""


# ------------------------------------ Default implementation ------------------------------------ #


class HTTPSessionDefault(HTTPSession):
    def __init__(self):
        self._session = httpx.AsyncClient()

    async def close(self):
        await self._session.aclose()

    async def request(self, request: HTTPRequest) -> HTTPResponse:
        try:
            response = await self._session.request(
                method=request.method,
                url=request.url,
                params=request.params,
                content=request.content,
                headers=request.headers,
                timeout=request.timeout,
            )
            return HTTPResponse(
                url=str(response.url),
                method=request.method,
                status=response.status_code,
                headers=dict(response.headers.items()),
                content=response.content,
                encoding=response.encoding,
            )
        except httpx.HTTPError as e:
            raise RequestError(str(e)) from e
