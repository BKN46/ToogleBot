"""Terminate an unresponsive event loop so the service manager can recover it."""

import asyncio
import os
import threading
import time


async def watch_event_loop(timeout: float) -> None:
    stopped = threading.Event()
    heartbeat = [time.monotonic()]

    def monitor():
        while not stopped.wait(1):
            if time.monotonic() - heartbeat[0] > timeout:
                os.write(2, b"Event loop watchdog timeout; exiting for service recovery\n")
                os._exit(1)

    thread = threading.Thread(target=monitor, name="event-loop-watchdog", daemon=True)
    thread.start()
    try:
        while True:
            heartbeat[0] = time.monotonic()
            await asyncio.sleep(1)
    finally:
        stopped.set()
