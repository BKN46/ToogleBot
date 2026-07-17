import asyncio
import datetime
import hashlib
import json
import re
import threading
import traceback
import uuid
from pathlib import Path
from typing import Any, Optional, Union
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from configs import config
from toogle.adapter import bot_send_message
from toogle.logger import logger
from toogle.message import Group, Member, MessageChain
from toogle.message_handler import MessagePack


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANUAL_SCHEDULE_PATH = PROJECT_ROOT / "data" / "schedule.json"
SCHEDULE_ERROR_LOG = PROJECT_ROOT / "log" / "schedule_err.log"
TIME_FIELDS = (
    "year",
    "month",
    "week",
    "day_of_week",
    "day",
    "hour",
    "minute",
    "second",
)

SCHEDULER_TIMEZONE = ZoneInfo(str(config.get("BOT_TIMEZONE", "Asia/Shanghai")))
native_scheduler = AsyncIOScheduler(
    timezone=SCHEDULER_TIMEZONE,
    job_defaults={
        "coalesce": True,
        "max_instances": 1,
        "misfire_grace_time": 300,
    },
)
SHARED_WORK_QUEUE: Optional[asyncio.Queue[MessagePack | None]] = None
_MANUAL_SCHEDULE_LOCK = threading.RLock()


def set_dispatch_queue(queue: asyncio.Queue[MessagePack | None] | None) -> None:
    global SHARED_WORK_QUEUE
    SHARED_WORK_QUEUE = queue


def _manual_schedule_id(item: dict[str, Any]) -> str:
    configured_id = str(item.get("id", "")).strip()
    if configured_id and re.fullmatch(r"[A-Za-z0-9_-]+", configured_id):
        return configured_id
    legacy_payload = json.dumps(item, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(legacy_payload.encode("utf-8")).hexdigest()[:20]
    return f"legacy-{digest}"


def normalize_manual_schedule(item: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("manual schedule must be an object")
    try:
        group_id = int(item["group_id"])
        creator_id = int(item["creator_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("manual schedule has invalid group_id/creator_id") from exc
    if group_id <= 0 or creator_id <= 0:
        raise ValueError("manual schedule group_id/creator_id must be positive")

    text = item.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("manual schedule text must not be empty")
    time_config = item.get("time")
    if not isinstance(time_config, dict) or not time_config:
        raise ValueError("manual schedule time must be a non-empty object")
    unknown_fields = set(time_config) - set(TIME_FIELDS)
    if unknown_fields:
        raise ValueError(
            f"manual schedule has unsupported time fields: {sorted(unknown_fields)!r}"
        )
    normalized_time: dict[str, str | int] = {}
    for key, value in time_config.items():
        if not isinstance(value, (str, int)) or str(value).strip() == "":
            raise ValueError(f"manual schedule time field {key!r} is invalid")
        normalized_time[key] = value

    for boolean_field in ("program", "single_time"):
        if not isinstance(item.get(boolean_field, False), bool):
            raise ValueError(f"manual schedule {boolean_field} must be a boolean")

    return {
        "id": _manual_schedule_id(item),
        "text": text,
        "program": bool(item.get("program", False)),
        "single_time": bool(item.get("single_time", False)),
        "group_id": group_id,
        "creator_id": creator_id,
        "time": normalized_time,
    }


def read_manual_schedules() -> list[dict[str, Any]]:
    with _MANUAL_SCHEDULE_LOCK:
        if not MANUAL_SCHEDULE_PATH.is_file():
            return []
        payload = json.loads(MANUAL_SCHEDULE_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("manual schedule file must contain a JSON list")
        return [normalize_manual_schedule(item) for item in payload]


def write_manual_schedules(items: list[dict[str, Any]]) -> None:
    with _MANUAL_SCHEDULE_LOCK:
        normalized = [normalize_manual_schedule(item) for item in items]
        MANUAL_SCHEDULE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = MANUAL_SCHEDULE_PATH.with_suffix(".json.tmp")
        temporary_path.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(MANUAL_SCHEDULE_PATH)


def get_job_name(item: dict[str, Any]) -> str:
    return f"manual:{normalize_manual_schedule(item)['id']}"


def remove_job(job_id_or_name: str) -> bool:
    for job in native_scheduler.get_jobs():
        if job.id == job_id_or_name or job.name == job_id_or_name:
            native_scheduler.remove_job(job.id)
            return True
    return False


def remove_manual_schedule(schedule_id: str) -> bool:
    with _MANUAL_SCHEDULE_LOCK:
        schedules = read_manual_schedules()
        remaining = [item for item in schedules if item["id"] != schedule_id]
        if len(remaining) == len(schedules):
            return False
        write_manual_schedules(remaining)
    remove_job(f"manual:{schedule_id}")
    return True


class ScheduleModule:
    name = "BKN的机器人定时组件"
    trigger = r""
    readme = "这是一个BKN的机器人定时组件"
    white_list = False
    thread_limit = False
    to_me_trigger = False
    interval = 0
    ignore_quote = False
    price = 0
    admin_only = False
    single_time = False

    year = -1
    month = -1
    week = -1
    day_of_week = -1
    day = -1
    hour = -1
    minute = -1
    second = 0

    _job_id = ""
    _manual_schedule_id = ""

    async def ret(self, message_pack: Union[MessagePack, None]):
        pass

    def is_trigger(self, message: Union[MessagePack, str]) -> bool:
        message_text = message if isinstance(message, str) else message.message.asDisplay()
        return bool(re.search(self.trigger, message_text))

    @property
    def job_id(self) -> str:
        if self._job_id:
            return self._job_id
        return f"code:{self.__class__.__module__}.{self.__class__.__qualname__}"

    async def ret_wrapper(self) -> bool:
        try:
            await self.ret(None)
            if self.single_time:
                if self._manual_schedule_id:
                    remove_manual_schedule(self._manual_schedule_id)
                else:
                    remove_job(self.job_id)
                logger.info("[Schedule][%s] done and removed", self.name)
            else:
                logger.info("[Schedule][%s] done", self.name)
            return True
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            err_info = (
                f"{'*' * 20}\n"
                f"[{datetime.datetime.now().strftime('%Y-%m-%d, %H:%M:%S')}]"
                f"[{self.name}] {exc!r}\n\n{'*' * 20}\n{traceback.format_exc()}"
            )
            SCHEDULE_ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
            with SCHEDULE_ERROR_LOG.open("a", encoding="utf-8") as error_log:
                print(err_info, file=error_log)
            logger.exception("[Schedule][%s] failed", self.name)
            admins = config.get("ADMIN_LIST", [])
            if admins:
                try:
                    bot_send_message(int(admins[0]), err_info, friend=True)
                except Exception:
                    logger.exception("Failed to notify schedule error: %s", self.name)
            return False

    def register(self):
        time_config = {
            field: getattr(self, field)
            for field in TIME_FIELDS
            if isinstance(getattr(self, field), str) or getattr(self, field) >= 0
        }
        existing_count = sum(
            job.id == self.job_id for job in native_scheduler.get_jobs()
        )
        for _ in range(existing_count):
            native_scheduler.remove_job(self.job_id)
        job = native_scheduler.add_job(
            self.ret_wrapper,
            "cron",
            id=self.job_id,
            replace_existing=True,
            name=self.name,
            **time_config,
        )
        logger.info("[Schedule][%s] registered", self.name)
        return job


def scheduler_start() -> None:
    if native_scheduler.running:
        return
    for job in native_scheduler.get_jobs():
        logger.info("[Schedule][%s] trigger: %s", job.name, job.trigger)
    native_scheduler.start()


def scheduler_shutdown() -> None:
    if native_scheduler.running:
        native_scheduler.shutdown(wait=False)


def load_manual_schedule(item: dict[str, Any]) -> ScheduleModule:
    normalized = normalize_manual_schedule(item)
    module = ScheduleModule()
    module.name = f"手动定时 {normalized['id']}"
    module._job_id = f"manual:{normalized['id']}"
    module._manual_schedule_id = normalized["id"]
    module.single_time = normalized["single_time"]
    for key, value in normalized["time"].items():
        setattr(module, key, value)

    if normalized["program"]:

        async def ret(message_pack: MessagePack | None):
            if SHARED_WORK_QUEUE is None:
                raise RuntimeError("schedule dispatch queue is not initialized")
            await SHARED_WORK_QUEUE.put(
                MessagePack(
                    id=0,
                    message=MessageChain.plain(normalized["text"]),
                    group=Group(normalized["group_id"], ""),
                    member=Member(normalized["creator_id"], ""),
                    quote=None,
                    message_type="group",
                )
            )

    else:

        async def ret(message_pack: MessagePack | None):
            if not bot_send_message(normalized["group_id"], normalized["text"]):
                raise RuntimeError("scheduled message could not be queued")

    module.ret = ret
    module.register()
    return module


def create_manual_schedule(
    *,
    text: str,
    program: bool,
    single_time: bool,
    group_id: int,
    creator_id: int,
    time_config: dict[str, str | int],
) -> dict[str, Any]:
    item = normalize_manual_schedule(
        {
            "id": uuid.uuid4().hex,
            "text": text,
            "program": program,
            "single_time": single_time,
            "group_id": group_id,
            "creator_id": creator_id,
            "time": time_config,
        }
    )
    module = load_manual_schedule(item)
    try:
        with _MANUAL_SCHEDULE_LOCK:
            schedules = read_manual_schedules()
            schedules.append(item)
            write_manual_schedules(schedules)
    except Exception:
        remove_job(module.job_id)
        raise
    return item


def reload_manual_scheduler() -> None:
    for item in read_manual_schedules():
        job_id = get_job_name(item)
        if native_scheduler.get_job(job_id) is None:
            load_manual_schedule(item)


def list_schedule_jobs() -> str:
    return "\n".join(job.name for job in native_scheduler.get_jobs())
