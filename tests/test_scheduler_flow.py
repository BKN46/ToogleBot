import asyncio
import datetime
import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import plugins.schedule as schedule_plugins
import toogle.scheduler as scheduler
from plugins.schedule import (
    CreateSchedule,
    DailySetuRanking,
    MembershipSchedule,
    ScheduledMonitor,
)
from toogle.message import MessageChain


class SchedulerFlowTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.path_patch = patch.object(
            scheduler, "MANUAL_SCHEDULE_PATH", root / "schedule.json"
        )
        self.error_patch = patch.object(
            scheduler, "SCHEDULE_ERROR_LOG", root / "schedule_err.log"
        )
        self.path_patch.start()
        self.error_patch.start()
        scheduler.native_scheduler.remove_all_jobs()
        scheduler.set_dispatch_queue(None)

    async def asyncTearDown(self):
        scheduler.native_scheduler.remove_all_jobs()
        scheduler.set_dispatch_queue(None)
        self.error_patch.stop()
        self.path_patch.stop()
        self.tempdir.cleanup()

    async def test_all_code_schedules_register_with_expected_cron(self):
        modules = [DailySetuRanking(), MembershipSchedule(), ScheduledMonitor()]
        for module in modules:
            module.register()

        jobs = scheduler.native_scheduler.get_jobs()
        self.assertEqual(len(jobs), 3)
        self.assertEqual(len({job.id for job in jobs}), 3)
        triggers = {job.name: str(job.trigger) for job in jobs}
        self.assertEqual(
            triggers["每日色图排行"],
            "cron[hour='0', minute='0', second='0']",
        )
        self.assertEqual(
            triggers["会员业务定时任务"],
            "cron[month='*', day='1', hour='0', minute='0', second='0']",
        )
        self.assertEqual(
            triggers["定时监测"],
            "cron[minute='*/5', second='0']",
        )

    async def test_scheduler_lifecycle_is_idempotent(self):
        fresh_scheduler = AsyncIOScheduler(event_loop=asyncio.get_running_loop())
        with patch.object(scheduler, "native_scheduler", fresh_scheduler):
            scheduler.scheduler_start()
            scheduler.scheduler_start()
            self.assertTrue(fresh_scheduler.running)
            scheduler.scheduler_shutdown()
            await asyncio.sleep(0)
            self.assertFalse(fresh_scheduler.running)

    async def test_scheduler_uses_timezone_and_bounded_execution_defaults(self):
        self.assertEqual(scheduler.native_scheduler.timezone, ZoneInfo("Asia/Shanghai"))
        job = DailySetuRanking().register()
        scheduler.scheduler_start()
        await asyncio.sleep(0)
        try:
            self.assertTrue(job.coalesce)
            self.assertEqual(job.max_instances, 1)
            self.assertEqual(job.misfire_grace_time, 300)
        finally:
            scheduler.scheduler_shutdown()
            await asyncio.sleep(0)

    async def test_manual_direct_and_programmed_paths(self):
        direct = scheduler.create_manual_schedule(
            text="direct message",
            program=False,
            single_time=False,
            group_id=100,
            creator_id=200,
            time_config={"minute": "1", "second": "0"},
        )
        queue = asyncio.Queue()
        scheduler.set_dispatch_queue(queue)
        programmed = scheduler.create_manual_schedule(
            text="programmed command",
            program=True,
            single_time=False,
            group_id=101,
            creator_id=201,
            time_config={"minute": "2", "second": "0"},
        )

        with patch("toogle.scheduler.bot_send_message") as send:
            direct_job = scheduler.native_scheduler.get_job(
                scheduler.get_job_name(direct)
            )
            self.assertIsNotNone(direct_job)
            self.assertTrue(await direct_job.func())
        send.assert_called_once_with(100, "direct message")

        programmed_job = scheduler.native_scheduler.get_job(
            scheduler.get_job_name(programmed)
        )
        self.assertIsNotNone(programmed_job)
        self.assertTrue(await programmed_job.func())
        message = queue.get_nowait()
        queue.task_done()
        self.assertEqual(message.group.id, 101)
        self.assertEqual(message.member.id, 201)
        self.assertEqual(message.message.asDisplay(), "programmed command")

    async def test_single_time_removes_job_and_persistence_only_after_success(self):
        item = scheduler.create_manual_schedule(
            text="one shot",
            program=False,
            single_time=True,
            group_id=100,
            creator_id=200,
            time_config={"minute": "3", "second": "0"},
        )
        job_id = scheduler.get_job_name(item)
        job = scheduler.native_scheduler.get_job(job_id)
        with patch("toogle.scheduler.bot_send_message"):
            self.assertTrue(await job.func())
        self.assertIsNone(scheduler.native_scheduler.get_job(job_id))
        self.assertEqual(scheduler.read_manual_schedules(), [])

        send_failed = scheduler.create_manual_schedule(
            text="send failed one shot",
            program=False,
            single_time=True,
            group_id=100,
            creator_id=200,
            time_config={"minute": "4", "second": "0"},
        )
        send_failed_job_id = scheduler.get_job_name(send_failed)
        send_failed_job = scheduler.native_scheduler.get_job(send_failed_job_id)
        with patch("toogle.scheduler.bot_send_message", return_value=False), patch.dict(
            scheduler.config, {"ADMIN_LIST": []}, clear=False
        ):
            self.assertFalse(await send_failed_job.func())
        self.assertIsNotNone(
            scheduler.native_scheduler.get_job(send_failed_job_id)
        )

        failed = scheduler.create_manual_schedule(
            text="failed one shot",
            program=True,
            single_time=True,
            group_id=100,
            creator_id=200,
            time_config={"minute": "5", "second": "0"},
        )
        failed_job_id = scheduler.get_job_name(failed)
        failed_job = scheduler.native_scheduler.get_job(failed_job_id)
        scheduler.set_dispatch_queue(None)
        with patch.dict(scheduler.config, {"ADMIN_LIST": []}, clear=False):
            self.assertFalse(await failed_job.func())
        self.assertIsNotNone(scheduler.native_scheduler.get_job(failed_job_id))
        self.assertEqual(len(scheduler.read_manual_schedules()), 2)

    async def test_delete_uses_creator_filtered_index(self):
        other = scheduler.create_manual_schedule(
            text="other creator",
            program=False,
            single_time=False,
            group_id=100,
            creator_id=999,
            time_config={"minute": "5", "second": "0"},
        )
        own = scheduler.create_manual_schedule(
            text="own schedule",
            program=False,
            single_time=False,
            group_id=100,
            creator_id=200,
            time_config={"minute": "6", "second": "0"},
        )

        self.assertEqual(CreateSchedule().del_schedule(200, 1), "删除成功")
        remaining = scheduler.read_manual_schedules()
        self.assertEqual([item["id"] for item in remaining], [other["id"]])
        self.assertIsNone(
            scheduler.native_scheduler.get_job(scheduler.get_job_name(own))
        )

    async def test_daily_membership_and_monitor_task_boundaries(self):
        setu_path = Path(self.tempdir.name) / "setu.json"
        setu_path.write_text("{}", encoding="utf-8")

        @contextmanager
        def memory_json(name):
            yield {}

        with patch.object(schedule_plugins, "SETU_RECORD_PATH", str(setu_path)), patch.dict(
            schedule_plugins.config, {"NSFW_LIST": []}, clear=False
        ), patch.object(schedule_plugins, "modify_json_file", memory_json):
            await DailySetuRanking().ret(None)
        self.assertEqual(json.loads(setu_path.read_text(encoding="utf-8")), {})

        future = (
            datetime.datetime.now() + datetime.timedelta(days=1)
        ).strftime("%Y-%m-%d %H:%M:%S")

        @contextmanager
        def membership_json(name):
            yield {
                "200": {
                    "time_due": future,
                    "trade_plan": "regular",
                }
            }

        with patch.object(
            schedule_plugins, "modify_json_file", membership_json
        ), patch.object(schedule_plugins, "get_balance", return_value=100), patch.object(
            schedule_plugins, "give_balance"
        ) as give:
            await MembershipSchedule().ret(None)
        give.assert_called_once_with(200, 400)

        monitor = ScheduledMonitor()
        with patch.object(
            monitor,
            "get_earth_quake",
            return_value=MessageChain.plain("earthquake"),
        ), patch.object(
            monitor,
            "get_save_old_otaku",
            return_value=MessageChain.plain("weibo"),
        ), patch.object(
            monitor,
            "_load_subscriptions",
            return_value={"300": ["earth_quake", "save_old_otaku"]},
        ), patch.object(schedule_plugins, "bot_send_message") as send:
            await monitor.ret(None)
        self.assertEqual(send.call_count, 2)

        idle_monitor = ScheduledMonitor()
        with patch.object(
            idle_monitor,
            "_load_subscriptions",
            return_value={},
        ), patch.object(
            idle_monitor,
            "get_earth_quake",
        ) as earth_quake, patch.object(
            idle_monitor,
            "get_save_old_otaku",
        ) as save_old_otaku:
            await idle_monitor.ret(None)
        earth_quake.assert_not_called()
        save_old_otaku.assert_not_called()

    async def test_earthquake_monitor_uses_current_official_schema(self):
        monitor = ScheduledMonitor()
        response = Mock()
        response.json.return_value = [
            {
                "magnitude": 4.8,
                "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "location": "测试区域",
            }
        ]

        with patch.object(
            schedule_plugins.requests,
            "get",
            return_value=response,
        ) as request:
            result = monitor.get_earth_quake()

        response.raise_for_status.assert_called_once_with()
        request.assert_called_once_with(
            "https://www.ceic.ac.cn/data/data.json",
            headers={"User-Agent": "ToogleBot earthquake monitor"},
            timeout=(5, 15),
        )
        self.assertIn("4.8级地震", result.asDisplay())
        self.assertIn("测试区域", result.asDisplay())


if __name__ == "__main__":
    unittest.main()
