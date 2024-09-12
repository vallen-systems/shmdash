import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, Mock, create_autospec

import pytest

from shmdash import Client, HTTPResponse, HTTPSession, ResponseError


@dataclass
class MockObjects:
    url: str
    api_key: str
    http_session: HTTPSession
    client: Client


@pytest.fixture
def mock() -> MockObjects:
    url = "https://shmdash.de"
    api_key = "00000000-0000-0000-0000-000000000000"
    http_session_instance = create_autospec(spec=HTTPSession, instance=True)
    http_session = Mock()
    http_session.return_value = http_session_instance
    return MockObjects(
        url=url,
        api_key=api_key,
        http_session=http_session_instance,
        client=Client(url=url, api_key=api_key, http_session=http_session),
    )


SETUP_DICT = {
    "attributes": {
        "AbsDateTime": {
            "descr": "Absolutetime in ISO8601, UTC Zone (max. µs)",
            "type": "dateTime",
            "format": "YYYY-MM-DDThh:mm:ss[.ssssss]Z",
        },
        "REFNO": {
            "descr": "Increasing reference number",
            "softLimits": [0, None],
            "diagramScale": "lin",
            "type": "int64",
            "format": "%d",
        },
        "VOLTAGE": {
            "unit": "mV",
            "descr": "Control Voltage",
            "softLimits": [0, 100],
            "diagramScale": "lin",
            "type": "float32",
            "format": "%.2f",
        },
        "TEMP1": {
            "unit": "°C",
            "descr": "Outside temperature",
            "softLimits": [-60, 100],
            "diagramScale": "lin",
            "type": "float32",
            "format": "%.1f",
        },
    },
    "virtual_channels": {
        "0": {
            "name": "Temperature sensor 1",
            "attributes": ["AbsDateTime", "REFNO", "min(TEMP1)", "max(TEMP1)"],
        },
        "1": {
            "name": "Control Signal",
            "descr": "Control signal voltage",
            "attributes": ["AbsDateTime", "REFNO", "VOLTAGE"],
        },
    },
}


def json_response(obj: Any, status: int = 200) -> HTTPResponse:
    encoding = "utf-8"
    return HTTPResponse(
        url="",
        method="",
        status=status,
        headers={},
        content=json.dumps(obj).encode(encoding),
        encoding=encoding,
    )


async def test_get_setup(mock):
    mock.http_session.get = AsyncMock(return_value=json_response(SETUP_DICT, status=200))
    setup = await mock.client.get_setup()
    mock.http_session.get.assert_awaited_once_with(f"{mock.url}/upload/vjson/v1/setup")

    assert len(setup.attributes) == 4
    assert setup.attributes[0].identifier == "AbsDateTime"
    assert setup.attributes[1].identifier == "REFNO"
    assert setup.attributes[2].identifier == "VOLTAGE"
    assert setup.attributes[3].identifier == "TEMP1"

    assert len(setup.virtual_channels) == 2
    assert setup.virtual_channels[0].identifier == "0"
    assert setup.virtual_channels[1].identifier == "1"


async def test_get_setup_empty(mock):
    mock.http_session.get = AsyncMock(return_value=json_response({}, status=200))
    setup = await mock.client.get_setup()
    assert setup.is_empty()


async def test_get_setup_error(mock):
    mock.http_session.get = AsyncMock(return_value=json_response({}, status=400))
    with pytest.raises(ResponseError):
        await mock.client.get_setup()
