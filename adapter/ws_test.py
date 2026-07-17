import asyncio
from typing import Any

import websockets

from adapter.server import build_ws_uri, decode_frame


def frame_summary(payload: dict[str, Any]) -> dict[str, Any]:
    message = payload.get("message")
    segment_types = (
        [item.get("type") for item in message if isinstance(item, dict)]
        if isinstance(message, list)
        else []
    )
    return {
        "keys": sorted(payload),
        "post_type": payload.get("post_type"),
        "message_type": payload.get("message_type"),
        "notice_type": payload.get("notice_type"),
        "status": payload.get("status"),
        "retcode": payload.get("retcode"),
        "has_echo": "echo" in payload,
        "segment_types": segment_types,
    }


async def main() -> None:
    async with websockets.connect(build_ws_uri()) as ws:
        while True:
            payload = decode_frame(await ws.recv())
            print(frame_summary(payload))


if __name__ == "__main__":
    asyncio.run(main())
