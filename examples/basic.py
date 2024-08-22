import asyncio
import contextlib
import logging
import random
from datetime import datetime

from shmdash import Attribute, AttributeType, Client, UploadData, VirtualChannel

URL = "https://dev.shmdash.de"
API_KEY = "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"

ATTRIBUTES = [
    Attribute(
        identifier="AbsDateTime",
        desc="Absolute time UTC",
        unit=None,
        format_="YYYY-MM-DDThh:mm:ss.ssssssZ",
        type_=AttributeType.DATETIME,
        soft_limits=[None, None],
    ),
    Attribute(
        identifier="Temperature",
        desc="Temperature",
        unit="°C",
        format_="%.2f",
        type_=AttributeType.FLOAT32,
    ),
    Attribute(
        identifier="Pressure",
        desc="Atmospheric pressure",
        unit="hPa",
        format_="%.0f",
        type_=AttributeType.FLOAT32,
    ),
    Attribute(
        identifier="Humidity",
        desc="Humidity",
        unit="%",
        format_="%.0f",
        type_=AttributeType.FLOAT32,
        soft_limits=[0, None],
    ),
    Attribute(
        identifier="WindSpeed",
        desc="Wind speed",
        unit="km/h",
        format_="%.2f",
        type_=AttributeType.FLOAT32,
    ),
    Attribute(
        identifier="WindDegree",
        desc="Wind degree",
        unit="°",
        format_="%.0f",
        type_=AttributeType.UINT16,
        soft_limits=[0, 360],
    ),
    Attribute(
        identifier="Rain1h",
        desc="Rain volume in last hour",
        unit="mm",
        format_="%.2f",
        type_=AttributeType.FLOAT32,
    ),
    Attribute(
        identifier="WeatherDescription",
        desc="Weather description",
        unit=None,
        format_="%s",
        type_=AttributeType.STRING,
    ),
]

VIRTUAL_CHANNELS = [
    VirtualChannel(
        identifier=100,
        name="Weather",
        desc="Just random test data",
        attributes=[attr.identifier for attr in ATTRIBUTES],
        properties=["STREAM", "PAR"],
    ),
]


async def main():
    logging.basicConfig(level=logging.DEBUG)

    async with Client(URL, API_KEY) as client:
        # delete all data
        # await client.delete_data()
        # delete all data and setups
        # await client.recreate()

        # setup attributes and virtual channel
        await client.setup(ATTRIBUTES, VIRTUAL_CHANNELS)
        print(await client.get_attributes())
        print(await client.get_virtual_channels())

        # upload random data
        while True:
            await client.upload_data(
                virtual_channel_id="100",
                data=[
                    UploadData(
                        timestamp=datetime.now(),
                        data=[
                            random.gauss(20, 1),  # temperature
                            random.gauss(1013.25, 1),  # pressure
                            random.gauss(0.5, 0.01),  # humidity
                            random.gauss(11.0, 0.1),  # wind speed
                            random.randint(320, 330),  # wind direction
                            random.uniform(0, 1),  # rain
                            "random weather",  # description
                        ],
                    ),
                ],
            )
            await asyncio.sleep(10)


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
