import asyncio
import datetime
import time

import requests
from requests.exceptions import HTTPError as RequestsError
from urllib3.exceptions import HTTPError as UrllibError

from adapter import msg_queue
from adapter.post_process import message_post_process
from configs import config
import toogle.adapter as adapter
import toogle.scheduler as scheduler
from toogle.exceptions import VisibleException
from toogle.index import get_export_plugins
from toogle.logger import logger
from toogle.message_handler import MessagePack


def _config_int(key: str, default: int) -> int:
    try:
        return max(1, int(config.get(key, default)))
    except (TypeError, ValueError):
        return default


WORK_QUEUE: asyncio.Queue[MessagePack | None] = asyncio.Queue(
    maxsize=_config_int("WORK_QUEUE_SIZE", 500)
)
WORKER_TASKS: list[asyncio.Task[None]] = []
scheduler.set_dispatch_queue(WORK_QUEUE)


async def process_loop() -> None:
    while True:
        message_pack = await msg_queue.recv_queue.get()
        try:
            try:
                await message_post_process(message_pack)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Message post-process failed")
            await WORK_QUEUE.put(message_pack)
        finally:
            msg_queue.recv_queue.task_done()


async def _run_plugin(
    plugin_wrapper,
    message_pack: MessagePack,
    worker_index: int,
) -> None:
    plugin = plugin_wrapper.plugin
    prepared = await plugin_wrapper.prepare(message_pack)
    if prepared is None:
        return

    started = time.monotonic()
    result = await plugin.ret(prepared)
    if result is None or not result.root:
        return
    execution_ms = (time.monotonic() - started) * 1000
    if plugin.interval and not result.no_interval:
        adapter.interval_limiter.force_user_interval(
            plugin.name,
            prepared.member.id,
            interval=plugin.interval,
        )
    if plugin.price > 0 and not result.no_charge:
        adapter.take_balance(prepared.member.id, plugin.price)
    adapter.bot_send_message(message_pack, result)
    adapter.print_call(plugin, prepared)

    total_ms = (time.monotonic() - started) * 1000
    log = logger.info if execution_ms < 10_000 else logger.warning
    log(
        "%s in worker %d completed (execution=%.2fms total=%.2fms)",
        plugin.name,
        worker_index,
        execution_ms,
        total_ms,
    )
    if execution_ms >= 10_000:
        with open("log/slow.tsv", "a", encoding="utf-8") as slow_log:
            print(
                f"{datetime.datetime.now()}\t{plugin.name}\t"
                f"{execution_ms:.2f}\t{total_ms:.2f}",
                file=slow_log,
            )


def _notify_plugin_error(plugin, message_pack: MessagePack, error: Exception) -> None:
    try:
        error_message = adapter.print_err(error, plugin, message_pack)
    except Exception:
        logger.exception("Failed to format plugin error: %s", plugin.name)
        return
    admins = config.get("ADMIN_LIST", [])
    if admins:
        adapter.bot_send_message(int(admins[0]), error_message, friend=True)
    else:
        logger.error("No ADMIN_LIST recipient configured for plugin error")


async def process_message(message_pack: MessagePack, worker_index: int) -> None:
    display_text = message_pack.message.asDisplay()
    for plugin_wrapper in get_export_plugins():
        plugin = plugin_wrapper.plugin
        try:
            if not plugin.is_trigger(display_text):
                continue
            await _run_plugin(plugin_wrapper, message_pack, worker_index)
        except asyncio.CancelledError:
            raise
        except (
            UrllibError,
            RequestsError,
            requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout,
            requests.exceptions.ConnectTimeout,
            requests.exceptions.HTTPError,
        ) as exc:
            try:
                adapter.print_err(exc, plugin, message_pack)
            except Exception:
                logger.exception("Failed to record network error: %s", plugin.name)
            adapter.bot_send_message(message_pack, "爬虫网络连接错误，请稍后尝试")
        except VisibleException as exc:
            adapter.bot_send_message(message_pack, str(exc))
        except Exception as exc:
            if "误触发" not in repr(exc):
                _notify_plugin_error(plugin, message_pack, exc)


async def worker_loop(index: int) -> None:
    while True:
        message_pack = await WORK_QUEUE.get()
        try:
            if message_pack is None:
                return
            try:
                await process_message(message_pack, index)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Unhandled plugin worker error: worker=%d", index)
        finally:
            WORK_QUEUE.task_done()


def worker_start(worker_num: int | None = None) -> tuple[asyncio.Task[None], ...]:
    global WORK_QUEUE
    if WORKER_TASKS:
        return tuple(WORKER_TASKS)
    WORK_QUEUE = asyncio.Queue(maxsize=_config_int("WORK_QUEUE_SIZE", 500))
    scheduler.set_dispatch_queue(WORK_QUEUE)
    count = worker_num or _config_int("WORKER_NUM", 1)
    for index in range(count):
        WORKER_TASKS.append(
            asyncio.create_task(worker_loop(index), name=f"plugin-worker-{index}")
        )
    logger.info("Started %d plugin worker task(s)", count)
    return tuple(WORKER_TASKS)


async def worker_shutdown(timeout: float = 10.0) -> None:
    if not WORKER_TASKS:
        return
    for _ in WORKER_TASKS:
        await WORK_QUEUE.put(None)
    try:
        await asyncio.wait_for(
            asyncio.gather(*WORKER_TASKS, return_exceptions=True),
            timeout=timeout,
        )
    except TimeoutError:
        logger.warning("Plugin worker shutdown timed out; cancelling tasks")
        for task in WORKER_TASKS:
            task.cancel()
        await asyncio.gather(*WORKER_TASKS, return_exceptions=True)
    finally:
        WORKER_TASKS.clear()
    logger.info("All plugin workers stopped")
