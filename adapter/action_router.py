import asyncio
from typing import Any

from adapter import msg_queue


class ActionError(RuntimeError):
    pass


_pending: dict[str, asyncio.Future[dict[str, Any]]] = {}


def resolve_response(payload: dict[str, Any]) -> bool:
    echo = payload.get("echo")
    if echo is None:
        return False
    future = _pending.get(str(echo))
    if future is None or future.done():
        return False
    future.set_result(payload)
    return True


def fail_pending(reason: BaseException) -> None:
    for future in list(_pending.values()):
        if not future.done():
            future.set_exception(reason)
    _pending.clear()


async def call_action(
    action: str,
    params: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    payload = msg_queue.make_action(action, params or {})
    echo = str(payload["echo"])
    loop = asyncio.get_running_loop()
    future: asyncio.Future[dict[str, Any]] = loop.create_future()
    _pending[echo] = future
    if not msg_queue.enqueue_outbound(payload):
        _pending.pop(echo, None)
        raise ActionError("NapCat transport is not ready")
    try:
        response = await asyncio.wait_for(future, timeout=timeout)
    except TimeoutError as exc:
        raise ActionError(f"NapCat action timed out: {action}") from exc
    finally:
        _pending.pop(echo, None)
    return response
