import asyncio
import json
from typing import Any
from urllib.parse import quote_plus

import websockets

import configs
from adapter import action_router, msg_queue
from adapter.post_process import on_bot_connect, on_startup
from toogle.logger import logger


connection_ready = asyncio.Event()


def build_ws_uri() -> str:
    configured_url = str(configs.config.get("WS_URL", "")).strip()
    token = str(configs.config.get("WS_TOKEN", ""))
    if configured_url:
        uri = configured_url
    else:
        host = configs.config.get("WS_HOST", "127.0.0.1")
        port = configs.config.get("WS_PORT", "3456")
        path = str(configs.config.get("WS_PATH", "/")) or "/"
        if not path.startswith("/"):
            path = f"/{path}"
        uri = f"ws://{host}:{port}{path}"
    if token and "access_token=" not in uri:
        separator = "&" if "?" in uri else "?"
        uri = f"{uri}{separator}access_token={quote_plus(token)}"
    return uri


def decode_frame(raw_frame: str | bytes) -> dict[str, Any]:
    if isinstance(raw_frame, bytes):
        raw_frame = raw_frame.decode("utf-8")
    payload = json.loads(raw_frame)
    if not isinstance(payload, dict):
        raise ValueError("OneBot frame must be a JSON object")
    return payload


def encode_action(action: dict[str, Any]) -> str:
    return json.dumps(action, ensure_ascii=False, separators=(",", ":"))


def _is_action_response(payload: dict[str, Any]) -> bool:
    return "echo" in payload and ("status" in payload or "retcode" in payload)


async def recv_loop(ws: Any) -> None:
    while True:
        raw_frame = await ws.recv()
        try:
            payload = decode_frame(raw_frame)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("Ignored invalid NapCat frame: %s", exc)
            continue

        if _is_action_response(payload):
            if not action_router.resolve_response(payload):
                logger.debug("Received NapCat action response without waiter")
            continue

        try:
            msg_queue.push_event(payload)
        except Exception:
            logger.exception(
                "Failed to process NapCat event: post_type=%r message_type=%r",
                payload.get("post_type"),
                payload.get("message_type"),
            )


async def send_loop(ws: Any) -> None:
    while True:
        action = await msg_queue.send_queue.get()
        try:
            await ws.send(encode_action(action))
        except Exception:
            try:
                msg_queue.send_queue.put_nowait(action)
            except asyncio.QueueFull:
                logger.error("Failed to requeue NapCat action after disconnect")
            raise
        finally:
            msg_queue.send_queue.task_done()


async def _run_connection(ws: Any) -> None:
    recv_task = asyncio.create_task(recv_loop(ws), name="napcat-recv")
    send_task = asyncio.create_task(send_loop(ws), name="napcat-send")
    tasks = {recv_task, send_task}
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
        raise ConnectionError("NapCat connection task stopped unexpectedly")
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def main() -> None:
    await on_startup()
    reconnect_delay = 1.0
    startup_notified = False
    loop = asyncio.get_running_loop()
    while True:
        try:
            async with websockets.connect(build_ws_uri()) as ws:
                msg_queue.bind_transport_loop(loop)
                connection_ready.set()
                reconnect_delay = 1.0
                logger.info("NapCat WebSocket connected")
                if not startup_notified:
                    await on_bot_connect(ws)
                    startup_notified = True
                await _run_connection(ws)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "NapCat WebSocket disconnected; retrying in %.1fs: %r",
                reconnect_delay,
                exc,
            )
        finally:
            connection_ready.clear()
            msg_queue.unbind_transport_loop(loop)
            action_router.fail_pending(ConnectionError("NapCat WebSocket disconnected"))
        await asyncio.sleep(reconnect_delay)
        reconnect_delay = min(reconnect_delay * 2, 30.0)


if __name__ == "__main__":
    asyncio.run(main())
