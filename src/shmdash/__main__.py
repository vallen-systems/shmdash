# ruff: noqa: T201

import asyncio
import logging
import random
from argparse import ArgumentParser
from datetime import datetime, timedelta, timezone

import shmdash


def _confirm(message: str) -> bool:
    while True:
        response = input(f"{message} (y/n): ").strip().lower()
        if response in ("y", "yes"):
            return True
        if response in ("n", "no"):
            return False
        print("Invalid input. Please enter 'y' or 'n'.")


async def main():
    parser = ArgumentParser(
        prog="shmdash",
        description="SHM Dash CLI.",
    )
    parser.add_argument(
        "url",
        help="Base URL of the SHM dashboard server",
    )
    parser.add_argument(
        "-k",
        "--api-key",
        required=True,
        help="API key for authentication",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Print setup",
    )
    parser.add_argument(
        "--create-demo",
        action="store_true",
        help="Create demo setup with random data",
    )
    parser.add_argument(
        "--delete-data",
        action="store_true",
        help="Delete all time-series data",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete all time-series data and setup information",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    async with shmdash.Client(args.url, args.api_key) as client:
        if args.setup:
            setup = await client.get_setup()
            print("\nAttributes:")
            for attr in setup.attributes:
                print(f"- {attr.identifier}: {attr.to_dict()}")
            print("\nVirtual channels:")
            for ch in setup.virtual_channels:
                print(f"- {ch.identifier}: {ch.to_dict()}")
            print()

        if args.delete_data:
            if _confirm("Delete all time-series data - are you sure?"):
                await client.delete_data()
            else:
                print("Operation cancelled.")

        if args.recreate:
            if _confirm("Delete all time-series data and setup information - are you sure?"):
                await client.recreate()
            else:
                print("Operation cancelled.")

        if args.create_demo:
            attributes = [
                shmdash.Attribute(
                    identifier="AbsDateTime",
                    description="Absolute time, ISO8601, UTC zulu zone",
                    unit=None,
                    type=shmdash.AttributeType.DATETIME,
                    format="YYYY-MM-DDThh:mm:ss.ssssssZ",
                ),
                shmdash.Attribute(
                    identifier="A",
                    description="Burst signal peak amplitude",
                    unit="dB",
                    format="%.2f",
                    type=shmdash.AttributeType.FLOAT32,
                ),
            ]
            virtual_channel = shmdash.VirtualChannel(
                identifier="1",
                name="Demo",
                description="Demo with random data",
                attributes=[attr.identifier for attr in attributes],
                properties=["STREAM", "HIT"],
            )
            print("Create demo setup")
            await client.setup(attributes=attributes, virtual_channels=[virtual_channel])
            print("Upload random data")
            now = datetime.now(tz=timezone.utc)
            await client.upload_data(
                virtual_channel_id=virtual_channel.identifier,
                data=[
                    shmdash.Data(
                        timestamp=now - timedelta(minutes=i),
                        values=[random.uniform(20, 100)],  # noqa: S311
                    )
                    for i in range(24 * 60)
                ],
            )


if __name__ == "__main__":
    asyncio.run(main())
