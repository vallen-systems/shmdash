import asyncio
import contextlib
import logging
import random
from datetime import datetime, timezone

from shmdash import Attribute, AttributeType, Client, Data, VirtualChannel

URL = "https://dev.shmdash.de"
API_KEY = "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"

ATTRIBUTES = [
    Attribute(
        identifier="AbsDateTime",
        description="Absolute time UTC",
        unit=None,
        format="YYYY-MM-DDThh:mm:ss.ssssssZ",
        type=AttributeType.DATETIME,
        soft_limits=(None, None),
    ),
    Attribute(
        identifier="Temperature",
        description="Temperature",
        unit="°C",
        format="%.2f",
        type=AttributeType.FLOAT32,
    ),
    Attribute(
        identifier="Pressure",
        description="Atmospheric pressure",
        unit="hPa",
        format="%.0f",
        type=AttributeType.FLOAT32,
    ),
    Attribute(
        identifier="Humidity",
        description="Humidity",
        unit="%",
        format="%.0f",
        type=AttributeType.FLOAT32,
        soft_limits=(0, None),
    ),
    Attribute(
        identifier="WindSpeed",
        description="Wind speed",
        unit="km/h",
        format="%.2f",
        type=AttributeType.FLOAT32,
    ),
    Attribute(
        identifier="WindDegree",
        description="Wind degree",
        unit="°",
        format="%.0f",
        type=AttributeType.UINT16,
        soft_limits=(0, 360),
    ),
    Attribute(
        identifier="Rain1h",
        description="Rain volume in last hour",
        unit="mm",
        format="%.2f",
        type=AttributeType.FLOAT32,
    ),
    Attribute(
        identifier="WeatherDescription",
        description="Weather description",
        unit=None,
        format="%s",
        type=AttributeType.STRING,
    ),
]

VIRTUAL_CHANNELS = [
    VirtualChannel(
        identifier="100",
        name="Weather",
        description="Just random test data",
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
        print(await client.get_setup())

        # upload random data
        while True:
            await client.upload_data(
                virtual_channel_id="100",
                data=[
                    Data(
                        timestamp=datetime.now(tz=timezone.utc),
                        values=[
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
