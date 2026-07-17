import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from adapter import msg_queue, worker
from adapter.post_process import message_post_process
from configs import config
from plugins.meta import ActivePathProbe
from toogle import adapter
import toogle.index as registry
from toogle.message import Group, Member, MessageChain, Quote
from toogle.message_handler import MessageHandler, MessagePack
from toogle.scheduler import ScheduleModule, native_scheduler


class WorkerFlowTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        msg_queue.reset_queues()

    async def asyncTearDown(self):
        await worker.worker_shutdown(timeout=1)

    async def test_workers_start_only_when_requested(self):
        self.assertFalse(worker.WORKER_TASKS)
        tasks = worker.worker_start(worker_num=1)
        self.assertEqual(len(tasks), 1)
        self.assertFalse(tasks[0].done())
        await worker.worker_shutdown(timeout=1)
        self.assertFalse(worker.WORKER_TASKS)

    async def test_process_message_uses_derived_quote_view(self):
        seen = []
        sent = []

        class FixturePlugin(MessageHandler):
            name = "fixture"
            trigger = r"^command"

            async def ret(self, message):
                seen.append(message.message.asDisplay())
                return MessageChain.plain("ok")

        source = MessagePack(
            id=1,
            message=MessageChain.plain("command"),
            group=Group(100, "group"),
            member=Member(200, "member"),
            quote=Quote(42, 201, 200, 100, MessageChain.plain(" origin")),
            message_type="group",
        )
        wrapper = adapter.PluginWrapper(FixturePlugin)
        with patch("adapter.worker.get_export_plugins", return_value=(wrapper,)), patch(
            "toogle.adapter.is_admin", return_value=True
        ), patch("toogle.adapter.bot_send_message", side_effect=lambda *args: sent.append(args) or True), patch(
            "toogle.adapter.print_call"
        ):
            await worker.process_message(source, worker_index=0)

        self.assertEqual(seen, ["command origin"])
        self.assertEqual(source.message.asDisplay(), "command")
        self.assertEqual(len(sent), 1)

    async def test_schedule_registration_is_idempotent(self):
        class FixtureSchedule(ScheduleModule):
            name = "fixture-schedule-idempotency"
            minute = "0"

        schedule = FixtureSchedule()
        try:
            schedule.register()
            schedule.register()
            matching = [
                job for job in native_scheduler.get_jobs() if job.id == schedule.job_id
            ]
            self.assertEqual(len(matching), 1)
        finally:
            if any(job.id == schedule.job_id for job in native_scheduler.get_jobs()):
                native_scheduler.remove_job(schedule.job_id)

    async def test_schedule_command_uses_message_trigger_contract(self):
        class FixtureSchedule(ScheduleModule):
            trigger = r"^scheduled command$"

        schedule = FixtureSchedule()
        self.assertTrue(schedule.is_trigger("scheduled command"))
        self.assertFalse(schedule.is_trigger("other command"))

    async def test_active_probe_uses_post_process_send_path(self):
        source = MessagePack(
            id=1,
            message=MessageChain.plain("configured active trigger"),
            group=Group(100, "group"),
            member=Member(200, "sender"),
            quote=None,
            message_type="group",
        )
        active_config = {
            "CHAT_GROUP_LIST": ["100"],
            "NAPCAT_ACTIVE_PROBE_ENABLED": "true",
            "NAPCAT_SENDER_ACCOUNT": "200",
            "NAPCAT_TEST_GROUP": "100",
            "NAPCAT_ACTIVE_PROBE_TRIGGER": "configured active trigger",
            "NAPCAT_ACTIVE_PROBE_REPLY": "configured active reply",
        }
        with patch.dict(config, active_config, clear=False), patch(
            "adapter.post_process.active_plugins", [ActivePathProbe()]
        ), patch(
            "adapter.post_process.chat_earn", new=AsyncMock()
        ), patch(
            "adapter.post_process.bot_send_message"
        ) as send:
            await message_post_process(source)

        send.assert_called_once()
        self.assertIs(send.call_args.args[0], source)
        self.assertEqual(
            send.call_args.args[1].asDisplay(),
            "configured active reply",
        )

    async def test_event_to_group_action_round_trip(self):
        class EchoPlugin(MessageHandler):
            name = "echo-fixture"
            trigger = r"^ping$"

            async def ret(self, message):
                return MessageChain.plain("pong")

        previous_registry = list(registry.export_plugins)
        previous_send = adapter.BOT_SEND
        registry.export_plugins[:] = [adapter.PluginWrapper(EchoPlugin)]
        adapter.BOT_SEND = msg_queue.send_message
        msg_queue.bind_transport_loop(asyncio.get_running_loop())
        dispatcher = asyncio.create_task(worker.process_loop())
        try:
            worker.worker_start(worker_num=1)
            event = {
                "post_type": "message",
                "message_type": "group",
                "message_id": 1,
                "group_id": 100,
                "user_id": 200,
                "self_id": 999,
                "sender": {"user_id": 200, "nickname": "fixture"},
                "message": [{"type": "text", "data": {"text": "ping"}}],
            }
            with patch("adapter.worker.message_post_process", new=AsyncMock()), patch(
                "toogle.adapter.is_admin", return_value=True
            ), patch("toogle.adapter.print_call"):
                self.assertEqual(msg_queue.push_event(event), "message")
                action = await asyncio.wait_for(msg_queue.send_queue.get(), timeout=1)
                msg_queue.send_queue.task_done()
            self.assertEqual(action["action"], "send_group_msg")
            self.assertEqual(action["params"]["group_id"], 100)
            self.assertEqual(
                action["params"]["message"],
                [{"type": "text", "data": {"text": "pong"}}],
            )
        finally:
            dispatcher.cancel()
            await asyncio.gather(dispatcher, return_exceptions=True)
            await worker.worker_shutdown(timeout=1)
            msg_queue.unbind_transport_loop(asyncio.get_running_loop())
            adapter.BOT_SEND = previous_send
            registry.export_plugins[:] = previous_registry


if __name__ == "__main__":
    unittest.main()
