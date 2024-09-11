import asyncio
import json

import pytest

from shmdash import HTTPSessionAiohttp, HTTPSessionOptions, RequestError


async def test_http_connection_failure():
    async with HTTPSessionAiohttp(options=HTTPSessionOptions()) as session:
        with pytest.raises(RequestError):
            await session.get("https://example.invalid")


async def test_http_timeout():
    async with HTTPSessionAiohttp(options=HTTPSessionOptions(timeout=1)) as session:
        with pytest.raises(asyncio.TimeoutError):
            await session.get("https://postman-echo.com/delay/2")


async def test_http_headers():
    async with HTTPSessionAiohttp(options=HTTPSessionOptions(headers={"custom": "123"})) as session:
        response = await session.get("https://postman-echo.com/headers")
        body = response.json()
        assert body["headers"]["custom"] == "123"


async def test_http_status():
    async with HTTPSessionAiohttp(options=HTTPSessionOptions()) as session:
        response = await session.get("https://postman-echo.com/status/404")
        assert response.status == 404


async def test_http_get():
    async with HTTPSessionAiohttp(options=HTTPSessionOptions()) as session:
        response = await session.get("https://postman-echo.com/get", params={"param": "test"})

        assert response.url == "https://postman-echo.com/get?param=test"
        assert response.method == "GET"
        assert response.status == 200
        assert response.content

        body = response.json()
        assert body["args"]["param"] == "test"


async def test_http_post():
    async with HTTPSessionAiohttp(options=HTTPSessionOptions()) as session:
        response = await session.post("https://postman-echo.com/post", data={"key": "value"})

        assert response.url == "https://postman-echo.com/post"
        assert response.method == "POST"
        assert response.status == 200
        assert response.content

        body = response.json()
        assert body["form"]["key"] == "value"


async def test_http_post_json():
    async with HTTPSessionAiohttp(
        options=HTTPSessionOptions(headers={"Content-Type": "application/json"})
    ) as session:
        response = await session.post(
            "https://postman-echo.com/post", data=json.dumps({"key": "value"})
        )

        body = response.json()
        assert body["json"]["key"] == "value"


async def test_http_delete():
    async with HTTPSessionAiohttp(options=HTTPSessionOptions()) as session:
        response = await session.delete("https://postman-echo.com/delete")

        assert response.url == "https://postman-echo.com/delete"
        assert response.method == "DELETE"
        assert response.status == 200
        assert response.content
