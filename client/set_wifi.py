#!/usr/bin/env python3

import asyncio

from bleak import BleakClient
from bleak import BleakScanner
from bleak.exc import BleakGATTProtocolError


DEVICE_NAME = "Cat-Feeding-Inator"

SSID_UUID = (
    "12345678-1234-1234-1234-123456789001"
)

PASSWORD_UUID = (
    "12345678-1234-1234-1234-123456789002"
)

COMMAND_UUID = (
    "12345678-1234-1234-1234-123456789003"
)

STATUS_UUID = (
    "12345678-1234-1234-1234-123456789004"
)


async def read_text(
    client,
    uuid,
    retries=5,
):
    for attempt in range(retries):

        try:
            raw = await client.read_gatt_char(
                uuid
            )

            return bytes(raw).decode(
                "utf-8",
                errors="replace",
            )

        except BleakGATTProtocolError as error:

            print(
                f"Temporary BLE read error "
                f"({attempt + 1}/{retries}): "
                f"{error}"
            )

            if attempt == retries - 1:
                raise

            await asyncio.sleep(0.5)


async def write_text(
    client,
    uuid,
    text,
    retries=5,
):
    for attempt in range(retries):

        try:
            await client.write_gatt_char(
                uuid,
                text.encode("utf-8"),
                response=True,
            )

            return

        except BleakGATTProtocolError as error:

            print(
                f"Temporary BLE write error "
                f"({attempt + 1}/{retries}): "
                f"{error}"
            )

            if attempt == retries - 1:
                raise

            await asyncio.sleep(0.5)


async def wait_for_status(
    client,
    prefixes,
    timeout=30,
):

    deadline = (
        asyncio.get_running_loop().time()
        + timeout
    )

    last_status = None

    while (
        asyncio.get_running_loop().time()
        < deadline
    ):

        status = await read_text(
            client,
            STATUS_UUID,
        )

        if status != last_status:

            print(
                f"ESP32: {status}"
            )

            last_status = status

        if any(
            status.startswith(prefix)
            for prefix in prefixes
        ):
            return status

        await asyncio.sleep(0.5)

    raise TimeoutError(
        "Timed out waiting for ESP32."
    )


async def main():

    # ------------------------------------------
    # User enters Wi-Fi information directly
    # ------------------------------------------

    ssid = input(
        "Wi-Fi SSID: "
    ).strip()

    if not ssid:
        raise SystemExit(
            "SSID cannot be empty."
        )

    # Visible intentionally while testing.
    # Press Enter for an open network.
    password = input(
        "Wi-Fi password "
        "(press Enter if none): "
    )


    # ------------------------------------------
    # Find ESP32 over BLE
    # ------------------------------------------

    print()
    print(
        f"Searching for {DEVICE_NAME}..."
    )

    device = (
        await
        BleakScanner.find_device_by_name(
            DEVICE_NAME,
            timeout=10,
        )
    )

    if device is None:

        raise SystemExit(
            f"{DEVICE_NAME} was not found."
        )


    print(
        f"Found: {device.name}"
    )

    print(
        f"Address: {device.address}"
    )

    print(
        "Connecting over Bluetooth..."
    )


    # ------------------------------------------
    # Connect over BLE
    # ------------------------------------------

    async with BleakClient(
        device,
        timeout=10,
    ) as client:

        print(
            "Bluetooth connected."
        )


        # --------------------------------------
        # Send SSID
        # --------------------------------------

        print()
        print(
            f"Sending SSID: {ssid}"
        )

        await write_text(
            client,
            SSID_UUID,
            ssid,
        )

        status = await wait_for_status(
            client,
            (
                "SSID:RECEIVED",
                "ERROR:",
            ),
            timeout=5,
        )

        if status.startswith(
            "ERROR:"
        ):
            raise SystemExit(
                status
            )


        # --------------------------------------
        # Send password
        # --------------------------------------

        print(
            "Sending password..."
        )

        await write_text(
            client,
            PASSWORD_UUID,
            password,
        )

        status = await wait_for_status(
            client,
            (
                "PASSWORD:RECEIVED",
                "ERROR:",
            ),
            timeout=5,
        )

        if status.startswith(
            "ERROR:"
        ):
            raise SystemExit(
                status
            )

        print(
            "Password sent."
        )


        # Small pause to avoid hammering BLE
        await asyncio.sleep(0.5)


        # --------------------------------------
        # Tell ESP32 to connect
        # --------------------------------------

        print(
            "Requesting Wi-Fi connection..."
        )

        await write_text(
            client,
            COMMAND_UUID,
            "CONNECT",
        )


        status = await wait_for_status(
            client,
            (
                "CONNECT:REQUESTED",
                "WIFI:CONNECTING",
                "WIFI:CONNECTED",
                "WIFI:FAILED",
                "ERROR:",
            ),
            timeout=5,
        )


        if status.startswith(
            "ERROR:"
        ):
            raise SystemExit(
                status
            )


        # --------------------------------------
        # Wait for final result
        # --------------------------------------

        print(
            "Waiting for Wi-Fi connection..."
        )

        status = await wait_for_status(
            client,
            (
                "WIFI:CONNECTED",
                "WIFI:FAILED",
                "ERROR:",
            ),
            timeout=30,
        )


        if status.startswith(
            "WIFI:CONNECTED"
        ):

            print()
            print(
                f"SUCCESS: {status}"
            )

            return


        print()
        print(
            f"FAILED: {status}"
        )


if __name__ == "__main__":
    asyncio.run(main())
