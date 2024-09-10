from __future__ import annotations

from http import HTTPStatus


class ClientError(Exception):
    """Base exception for Client-related errors."""


class RequestError(ClientError):
    """
    Raised when there is an issue during the request process.

    This exception is triggered when the request could not be completed, such as connection issues,
    timeouts, or invalid request configuration.
    It indicates that the error occurred before a response was received.
    """


class ResponseError(ClientError):
    """
    Raised when a response contains an error HTTP status code (4xx or 5xx).

    This exception is triggered when a response is received but the status code indicates a client
    (4xx) or server (5xx) error.
    It signals that the server responded, but with an error status that requires handling.
    """

    def __init__(
        self,
        url: str,
        method: str,
        status: int,
        message: str | None = None,
    ):
        self.url = url
        self.method = method
        self.status = status

        super().__init__(
            f"{method} request to {url} failed with status {status} ({HTTPStatus(status).phrase})"
            + (f": {message}" if message else "")
        )
