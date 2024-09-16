import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import ANY, AsyncMock, create_autospec

import pytest

import shmdash

API_KEY = "00000000-0000-0000-0000-000000000000"

URL = "https://shmdash.de"
URL_SETUP = f"{URL}/upload/vjson/v1/setup"
URL_DATA = f"{URL}/upload/vjson/v1/data"
URL_COMMANDS = f"{URL}/upload/vjson/v1/commands"
URL_ANNOTATION = f"{URL}/upload/vjson/v1/annotation"
URL_DEV_DATA = f"{URL}/dev/timeseriesdata"
URL_DEV_RECREATE = f"{URL}/dev/recreate"


@dataclass
class MockObjects:
    http_session: shmdash.HTTPSession
    client: shmdash.Client


@pytest.fixture
def mock() -> MockObjects:
    http_session = create_autospec(spec=shmdash.HTTPSession, instance=True)
    return MockObjects(
        http_session=http_session,
        client=shmdash.Client(url=URL, api_key=API_KEY, http_session=http_session),
    )


def json_response(obj, status: int = 200) -> shmdash.HTTPResponse:
    encoding = "utf-8"
    return shmdash.HTTPResponse(
        url="",
        method="",
        status=status,
        headers={},
        content=json.dumps(obj).encode(encoding),
        encoding=encoding,
    )


async def test_close(mock):
    mock.http_session.close = AsyncMock()
    await mock.client.close()
    mock.http_session.close.assert_awaited_once()


async def test_context_manager(mock):
    mock.http_session.close = AsyncMock()
    async with mock.client:
        ...
    mock.http_session.close.assert_awaited_once()


async def test_request_headers(mock):
    mock.http_session.request = AsyncMock(return_value=json_response(SETUP_DICT))
    await mock.client.get_setup()
    mock.http_session.request.assert_awaited_once_with(
        shmdash.HTTPRequest(
            "GET",
            URL_SETUP,
            headers={
                "Content-Type": "application/json",
                "UPLOAD-API-KEY": API_KEY,
            },
        )
    )


async def test_get_setup(mock):
    mock.http_session.request = AsyncMock(return_value=json_response(SETUP_DICT))
    setup = await mock.client.get_setup()
    mock.http_session.request.assert_awaited_once_with(
        shmdash.HTTPRequest("GET", URL_SETUP, headers=ANY)
    )

    assert len(setup.attributes) == 3
    assert setup.attributes[0].identifier == "AbsDateTime"
    assert setup.attributes[1].identifier == "Pressure"
    assert setup.attributes[2].identifier == "WindSpeed"

    assert len(setup.virtual_channels) == 2
    assert setup.virtual_channels[0].identifier == "0"
    assert setup.virtual_channels[1].identifier == "1"


async def test_get_setup_empty(mock):
    mock.http_session.request = AsyncMock(return_value=json_response({}))
    setup = await mock.client.get_setup()
    assert setup.is_empty()


async def test_get_setup_error(mock):
    mock.http_session.request = AsyncMock(return_value=json_response({}, status=400))
    with pytest.raises(shmdash.ResponseError):
        await mock.client.get_setup()


SETUP_DICT = {
    "attributes": {
        "AbsDateTime": {
            "descr": "Absolute time UTC",
            "type": "dateTime",
            "format": "YYYY-MM-DDThh:mm:ss.ssssssZ",
        },
        "Pressure": {
            "descr": "Atmospheric pressure",
            "unit": "hPa",
            "type": "float32",
            "format": "%.2f",
            "softLimits": (900, 1100),
        },
        "WindSpeed": {
            "descr": "Wind speed",
            "unit": "m/s",
            "type": "float32",
            "format": "%.2f",
            "softLimits": (0, None),
        },
    },
    "virtual_channels": {
        "0": {
            "attributes": ["AbsDateTime", "Pressure"],
        },
        "1": {
            "attributes": ["AbsDateTime", "Pressure", "WindSpeed"],
        },
    },
}


async def test_setup(mock):
    mock.http_session.request = AsyncMock(return_value=json_response({}))
    setup = shmdash.Setup.from_dict(SETUP_DICT)
    await mock.client.setup(setup.attributes, setup.virtual_channels)
    mock.http_session.request.assert_awaited_with(
        shmdash.HTTPRequest(
            "POST",
            URL_SETUP,
            headers=ANY,
            content=json.dumps(SETUP_DICT),
        )
    )


async def test_setup_error(mock):
    mock.http_session.request = AsyncMock(return_value=json_response({}, status=400))
    with pytest.raises(shmdash.ResponseError):
        await mock.client.setup([], [])


async def test_setup_existing(mock):
    mock.http_session.request = AsyncMock(return_value=json_response(SETUP_DICT))
    setup = shmdash.Setup.from_dict(SETUP_DICT)
    await mock.client.setup(setup.attributes, setup.virtual_channels)
    mock.http_session.request.assert_awaited_once_with(
        shmdash.HTTPRequest(
            "GET",
            URL_SETUP,
            headers=ANY,
        )
    )


async def test_setup_partial_existing(mock):
    setup_dict_existing = deepcopy(SETUP_DICT)
    setup_dict_existing["attributes"].popitem()
    setup_dict_existing["virtual_channels"].popitem()
    mock.http_session.request = AsyncMock(return_value=json_response(setup_dict_existing))
    setup = shmdash.Setup.from_dict(SETUP_DICT)
    await mock.client.setup(setup.attributes, setup.virtual_channels)
    mock.http_session.request.assert_awaited_with(
        shmdash.HTTPRequest(
            "POST",
            URL_COMMANDS,
            headers=ANY,
            content=ANY,
        )
    )


ATTRIBUTE = shmdash.Attribute(
    identifier="Pressure",
    description="Atmospheric pressure",
    unit="hPa",
    type=shmdash.AttributeType.FLOAT32,
)


async def test_add_attribute(mock):
    mock.http_session.request = AsyncMock(return_value=json_response({}))
    await mock.client.add_attribute(ATTRIBUTE)
    mock.http_session.request.assert_awaited_once_with(
        shmdash.HTTPRequest(
            "POST",
            URL_COMMANDS,
            headers=ANY,
            content=json.dumps(
                {
                    "commands": [
                        {
                            "cmdName": "addAttribute",
                            "attributeId": "Pressure",
                            "descr": "Atmospheric pressure",
                            "unit": "hPa",
                            "type": "float32",
                        }
                    ]
                }
            ),
        )
    )


async def test_add_attribute_error(mock):
    mock.http_session.request = AsyncMock(return_value=json_response({}, status=400))
    with pytest.raises(shmdash.ResponseError):
        await mock.client.add_attribute(ATTRIBUTE)


VIRTUAL_CHANNEL = shmdash.VirtualChannel(
    identifier="0",
    name=None,
    description=None,
    attributes=["AbsDateTime", "Pressure"],
)


async def test_add_virtual_channel(mock):
    mock.http_session.request = AsyncMock(return_value=json_response({}))
    await mock.client.add_virtual_channel(VIRTUAL_CHANNEL)
    mock.http_session.request.assert_awaited_once_with(
        shmdash.HTTPRequest(
            "POST",
            URL_COMMANDS,
            headers=ANY,
            content=json.dumps(
                {
                    "commands": [
                        {
                            "cmdName": "addVirtualChannel",
                            "virtualChannelId": "0",
                            "attributes": ["AbsDateTime", "Pressure"],
                        }
                    ]
                }
            ),
        )
    )


async def test_add_virtual_channel_error(mock):
    mock.http_session.request = AsyncMock(return_value=json_response({}, status=400))
    with pytest.raises(shmdash.ResponseError):
        await mock.client.add_virtual_channel(VIRTUAL_CHANNEL)


async def test_add_virtual_channel_attributes(mock):
    mock.http_session.request = AsyncMock(return_value=json_response({}))
    await mock.client.add_virtual_channel_attributes("0", ["WindSpeed"])
    mock.http_session.request.assert_awaited_once_with(
        shmdash.HTTPRequest(
            "POST",
            URL_COMMANDS,
            headers=ANY,
            content=json.dumps(
                {
                    "commands": [
                        {
                            "cmdName": "addVirtualChannelAttributes",
                            "virtualChannelId": "0",
                            "attributes": ["WindSpeed"],
                        }
                    ]
                }
            ),
        )
    )


async def test_add_virtual_channel_attributes_error(mock):
    mock.http_session.request = AsyncMock(return_value=json_response({}, status=400))
    with pytest.raises(shmdash.ResponseError):
        await mock.client.add_virtual_channel_attributes("0", ["WindSpeed"])


UPLOAD_DATA = shmdash.Data(
    timestamp=datetime(
        year=2024,
        month=1,
        day=1,
        hour=11,
        minute=11,
        second=11,
        microsecond=111111,
        tzinfo=timezone.utc,
    ),
    values=[11.11],
)


async def test_upload_data(mock):
    mock.http_session.request = AsyncMock(return_value=json_response({}))
    await mock.client.upload_data("0", [UPLOAD_DATA])
    mock.http_session.request.assert_called_once_with(
        shmdash.HTTPRequest(
            "POST",
            URL_DATA,
            headers=ANY,
            content=json.dumps(
                {
                    "conflict": "IGNORE",
                    "data": [
                        ["0", "2024-01-01T11:11:11.111111Z", 11.11],
                    ],
                }
            ),
        )
    )


async def test_upload_data_payload_too_large(mock):
    mock.http_session.request = AsyncMock(return_value=json_response({}, status=413))
    with pytest.raises(shmdash.ResponseError):
        await mock.client.upload_data("0", [UPLOAD_DATA] * 16)

    assert mock.http_session.request.await_count == 5

    def upload_data_count(await_args):
        return len(json.loads(await_args[0][0].content)["data"])

    assert upload_data_count(mock.http_session.request.await_args_list[0]) == 16
    assert upload_data_count(mock.http_session.request.await_args_list[1]) == 8
    assert upload_data_count(mock.http_session.request.await_args_list[2]) == 4
    assert upload_data_count(mock.http_session.request.await_args_list[3]) == 2
    assert upload_data_count(mock.http_session.request.await_args_list[4]) == 1


async def test_upload_annotation(mock):
    mock.http_session.request = AsyncMock(return_value=json_response({}))
    annotation = shmdash.Annotation(
        timestamp=datetime.now(tz=timezone.utc),
        severity=shmdash.Severity.WARNING,
        description="Annotation",
    )
    await mock.client.upload_annotation(annotation)
    mock.http_session.request.assert_called_once_with(
        shmdash.HTTPRequest(
            "POST",
            URL_ANNOTATION,
            headers=ANY,
            content=json.dumps(annotation.to_dict()),
        )
    )


async def test_delete_data(mock):
    mock.http_session.request = AsyncMock(return_value=json_response({}))
    await mock.client.delete_data()
    mock.http_session.request.assert_awaited_once_with(
        shmdash.HTTPRequest(
            "DELETE",
            URL_DEV_DATA,
            headers=ANY,
        )
    )


async def test_delete_data_error(mock):
    mock.http_session.request = AsyncMock(return_value=json_response({}, status=400))
    with pytest.raises(shmdash.ResponseError):
        await mock.client.delete_data()


async def test_recreate(mock):
    mock.http_session.request = AsyncMock(return_value=json_response({}))
    await mock.client.recreate()
    mock.http_session.request.assert_awaited_once_with(
        shmdash.HTTPRequest(
            "GET",
            URL_DEV_RECREATE,
            headers=ANY,
        )
    )


async def test_recreate_error(mock):
    mock.http_session.request = AsyncMock(return_value=json_response({}, status=400))
    with pytest.raises(shmdash.ResponseError):
        await mock.client.recreate()
