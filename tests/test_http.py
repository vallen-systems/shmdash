import json
from urllib.parse import urlencode

import pytest

from shmdash import HTTPRequest, HTTPSessionAiohttp, RequestError


async def test_http_connection_failure():
    async with HTTPSessionAiohttp() as session:
        with pytest.raises(RequestError):
            await session.request(HTTPRequest("GET", "https://example.invalid"))


async def test_http_timeout():
    async with HTTPSessionAiohttp() as session:
        with pytest.raises(RequestError):
            await session.request(HTTPRequest("GET", "https://postman-echo.com/delay/2", timeout=1))


async def test_http_headers():
    async with HTTPSessionAiohttp() as session:
        response = await session.request(
            HTTPRequest(
                "GET",
                "https://postman-echo.com/headers",
                headers={"custom": "123"},
            )
        )
        body = response.json()
        assert body["headers"]["custom"] == "123"


async def test_http_status():
    async with HTTPSessionAiohttp() as session:
        response = await session.request(HTTPRequest("GET", "https://postman-echo.com/status/404"))
        assert response.status == 404


async def test_http_get():
    async with HTTPSessionAiohttp() as session:
        response = await session.request(
            HTTPRequest("GET", "https://postman-echo.com/get", params={"param": "test"})
        )

        assert response.url == "https://postman-echo.com/get?param=test"
        assert response.method == "GET"
        assert response.status == 200
        assert response.content

        body = response.json()
        assert body["args"]["param"] == "test"


async def test_http_post_form():
    async with HTTPSessionAiohttp() as session:
        response = await session.request(
            HTTPRequest(
                "POST",
                "https://postman-echo.com/post",
                body=urlencode({"key": "value"}),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        )

        assert response.url == "https://postman-echo.com/post"
        assert response.method == "POST"
        assert response.status == 200
        assert response.content

        body = response.json()
        assert body["form"]["key"] == "value"


async def test_http_post_json():
    async with HTTPSessionAiohttp() as session:
        response = await session.request(
            HTTPRequest(
                "POST",
                "https://postman-echo.com/post",
                body=json.dumps({"key": "value"}),
                headers={"Content-Type": "application/json"},
            )
        )

        body = response.json()
        assert body["json"]["key"] == "value"


async def test_http_delete():
    async with HTTPSessionAiohttp() as session:
        response = await session.request(HTTPRequest("DELETE", "https://postman-echo.com/delete"))

        assert response.url == "https://postman-echo.com/delete"
        assert response.method == "DELETE"
        assert response.status == 200
        assert response.content
