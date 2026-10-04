#!/usr/bin/env python3

import asyncio

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakGATTProtocolError

DEVICE_NAME = "Cat-Feeding-Inator"
COMMAND_UUID = "12345678-1234-1234-1234-123456789003"
STATUS_UUID = "12345678-1234-1234-1234-123456789004"


async def read_text(client, uuid, retries=5):
    for attempt in range(retries):
        try:
            raw = await client.read_gatt_char(uuid)
            return bytes(raw).decode("utf-8", errors="replace")
        except BleakGATTProtocolError as exc:
            print(f"Temporary BLE read error ({attempt + 1}/{retries}): {exc}")
            if attempt == retries - 1:
                raise
            await asyncio.sleep(0.5)


async def write_text(client, uuid, text, retries=5):
    for attempt in range(retries):
        try:
            await client.write_gatt_char(
                uuid,
                text.encode("utf-8"),
                response=True,
            )
            return
        except BleakGATTProtocolError as exc:
            print(f"Temporary BLE write error ({attempt + 1}/{retries}): {exc}")
            if attempt == retries - 1:
                raise
            await asyncio.sleep(0.5)


async def wait_for_status(client, prefixes, timeout=10):
    deadline = asyncio.get_running_loop().time() + timeout
    last_status = None
    while asyncio.get_running_loop().time() < deadline:
        status = await read_text(client, STATUS_UUID)
        if status != last_status:
            print(f"ESP32: {status}")
            last_status = status
        if any(status.startswith(prefix) for prefix in prefixes):
            return status
        await asyncio.sleep(0.5)
    raise TimeoutError("Timed out waiting for ESP32.")


async def main() -> int:
    print(f"Searching for {DEVICE_NAME}...")

    device = await BleakScanner.find_device_by_name(
        DEVICE_NAME,
        timeout=10.0,
    )

    if device is None:
        print(f"ERROR: Could not find {DEVICE_NAME}.")
        print("Make sure the ESP32-C3 is powered and advertising.")
        return 1

    print(f"Found: {device.name}")
    print(f"Address: {device.address}")
    print("Connecting...")

    try:
        async with BleakClient(device, timeout=10.0) as client:
            if not client.is_connected:
                print("ERROR: BLE connection failed.")
                return 1

            print("Connected.")
            print("Sending FEED...")

            await write_text(client, COMMAND_UUID, "FEED")

            print("FEED command sent successfully.")

            try:
                status = await wait_for_status(
                    client,
                    ("FEED:STARTED", "FEED:OK", "FEED:BUSY", "ERROR:"),
                    timeout=10,
                )
            except Exception as exc:
                print(f"WARNING: could not read status: {exc}")
                return 1

            if status.startswith("FEED:BUSY"):
                print(f"Feed rejected (busy): {status}")
                return 1

            if status.startswith("ERROR:"):
                print(f"Feed failed: {status}")
                return 1

            if status == "FEED:STARTED":
                # Non-blocking firmware: STARTED -> OK once pulse finishes (~1.1 s).
                try:
                    status = await wait_for_status(
                        client,
                        ("FEED:OK", "FEED:BUSY", "ERROR:"),
                        timeout=10,
                    )
                except Exception as exc:
                    print(f"WARNING: could not confirm feed completion: {exc}")
                    return 1

            print(f"Status: {status}")
            if not status.startswith("FEED:OK"):
                print(f"Feed did not complete: {status}")
                return 1

    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
