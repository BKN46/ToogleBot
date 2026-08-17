import base64
import contextlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from plugins import debug
from toogle.message import AtAll, ForwardMessage, Group, Image, Member, MessageChain
from toogle.message_handler import MessageHandler, MessagePack


def make_pack(
    text: str,
    *,
    group_id: int = 100,
    member_id: int = 200,
    member_name: str = "tester",
    message_type: str = "group",
) -> MessagePack:
    return MessagePack(
        id=1,
        message=MessageChain.plain(text),
        group=Group(group_id if message_type == "group" else 0, "fixture"),
        member=Member(member_id, member_name),
        quote=None,
        message_type=message_type,
    )


class DebugPluginTest(unittest.IsolatedAsyncioTestCase):
    def test_module_exposes_all_debug_plugins(self):
        classes = {
            candidate.__name__
            for candidate in vars(debug).values()
            if isinstance(candidate, type)
            and candidate.__module__ == debug.__name__
            and issubclass(candidate, MessageHandler)
            and candidate is not MessageHandler
        }

        self.assertEqual(
            classes,
            {
                "AsyncDebug",
                "CounterPlugin",
                "DarkstarServerPing",
                "DebugPlugin",
                "DebugPlugin2",
                "PoliticsOrNot",
                "RecallDebugPlugin",
                "TooglePicGen",
                "ToogleWorldDebug",
                "WitsAndWagers",
                "gbLuckyPocket",
            },
        )
        self.assertTrue(debug.DebugPlugin.admin_only)
        self.assertTrue(debug.DebugPlugin2.admin_only)
        self.assertTrue(debug.RecallDebugPlugin.admin_only)
        self.assertTrue(debug.CounterPlugin.admin_only)
        self.assertTrue(debug.PoliticsOrNot.admin_only)
        self.assertTrue(debug.AsyncDebug.admin_only)
        self.assertTrue(debug.ToogleWorldDebug.admin_only)

    async def test_weibo_debug_commands_build_forward_messages(self):
        saved_posts = [
            (
                "fixture time",
                "fixture post",
                ["https://example.invalid/image.png"],
                "https://example.invalid/detail",
                (1, ["fixture comment"]),
                "fixture key",
            )
        ]
        with patch("plugins.debug.is_admin", return_value=True), patch(
            "plugins.debug.get_save_old_otaku", return_value=saved_posts
        ):
            result = await debug.DebugPlugin().ret(make_pack("send_debug"))

        self.assertIsInstance(result.root[0], ForwardMessage)
        self.assertEqual(len(result.root[0].node_list), 2)

        with patch(
            "plugins.debug.get_comments",
            return_value=(2, ["first", "second"]),
        ):
            comments = await debug.DebugPlugin2().ret(make_pack("看眼评论"))

        self.assertIsInstance(comments.root[0], ForwardMessage)
        self.assertEqual(len(comments.root[0].node_list), 3)

    async def test_recall_statistics_and_counter_handle_local_state(self):
        state = {"debug_cnt": {"错判": 1, "漏判": 2, "漏发": 1}}

        @contextlib.contextmanager
        def fake_modify(name):
            yield state.setdefault(name, {})

        with tempfile.TemporaryDirectory() as temp_dir:
            recall_path = Path(temp_dir) / "recall.log"
            recall_path.write_text("a\tb\t3\ninvalid\na\tb\t2\n", encoding="utf-8")
            plugin = debug.RecallDebugPlugin()
            plugin.recall_log_path = recall_path
            with patch("plugins.debug.modify_json_file", fake_modify):
                result = await plugin.ret(make_pack("自动撤回统计"))
                counter = await debug.CounterPlugin().ret(make_pack("记录 漏发 2"))

        self.assertIn("总撤回图片数: 5", result.asDisplay())
        self.assertEqual(counter.asDisplay(), "漏发 计数器: 3")

    async def test_recall_statistics_degrades_when_log_is_missing(self):
        plugin = debug.RecallDebugPlugin()
        plugin.recall_log_path = Path("/tmp/nonexistent-toogle-recall.log")

        result = await plugin.ret(make_pack("自动撤回统计"))

        self.assertEqual(result.asDisplay(), "暂无撤回统计数据")

    async def test_darkstar_query_is_offloaded_and_formatted(self):
        server = SimpleNamespace(player_count=2, max_players=16, ping=0.012)
        with patch.dict(
            debug.config,
            {
                "DARKSTAR_SERVER_HOST": "server.example.invalid",
                "DARKSTAR_SERVER_PORT": "27015",
            },
            clear=False,
        ), patch("plugins.debug.a2s.info", return_value=server) as query:
            result = await debug.DarkstarServerPing().ret(make_pack("暗星"))

        query.assert_called_once()
        self.assertIn("人数：2/16", result.asDisplay())
        self.assertIn("12.00ms", result.asDisplay())

        with patch.dict(
            debug.config,
            {"DARKSTAR_SERVER_HOST": "", "DARKSTAR_SERVER_PORT": ""},
            clear=False,
        ):
            unavailable = await debug.DarkstarServerPing().ret(make_pack("暗星"))
        self.assertEqual(unavailable.asDisplay(), "暗星服务器未配置")

    async def test_wits_and_wagers_sends_question_without_blocking(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            question_path = Path(temp_dir) / "wnw.data"
            question_path.write_text("question\nanswer\n", encoding="utf-8")
            plugin = debug.WitsAndWagers()
            plugin.question_path = question_path
            with patch.dict(
                debug.config,
                {"WNW_ANSWER_DELAY_SECONDS": "0"},
                clear=False,
            ), patch("plugins.debug.random.randrange", return_value=0), patch(
                "plugins.debug.bot_send_message", return_value=True
            ) as send:
                result = await plugin.ret(make_pack("/clcq"))
            indexed = await plugin.ret(make_pack("/clcq 0"))

        send.assert_called_once()
        self.assertIn("答案:\nanswer", result.asDisplay())
        self.assertEqual(indexed.asDisplay(), "问题0答案:\nanswer")

    async def test_censor_and_wait_debug_paths(self):
        with patch("plugins.debug.gpt_censor", return_value=(42, "fixture", 0)):
            result = await debug.PoliticsOrNot().ret(make_pack("这个政不政 fixture"))
        self.assertIn("分数: 42", result.asDisplay())

        followup = make_pack("11111")
        with patch("plugins.debug.is_admin", return_value=True), patch(
            "plugins.debug.bot_send_message", return_value=True
        ), patch.object(
            debug.WaitCommandHandler,
            "run",
            new=AsyncMock(return_value=followup),
        ):
            waited = await debug.AsyncDebug().ret(make_pack("async"))
        self.assertEqual(waited.asDisplay(), "11111")

    async def test_toogleworld_debug_reads_only_last_twenty_lines(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "server.log"
            log_path.write_text(
                "".join(f"line-{index}\n" for index in range(25)),
                encoding="utf-8",
            )
            with patch.dict(
                debug.config,
                {"TOOGLEWORLD_LOG_PATH": str(log_path)},
                clear=False,
            ), patch("plugins.debug.is_admin", return_value=True):
                result = await debug.ToogleWorldDebug().ret(
                    make_pack("toogleworlddebug")
                )

        self.assertNotIn("line-4\n", result.asDisplay())
        self.assertIn("line-5\n", result.asDisplay())
        self.assertIn("line-24\n", result.asDisplay())

    async def test_gb_pocket_allows_every_pocket_to_be_claimed(self):
        state = {}

        @contextlib.contextmanager
        def fake_modify(name):
            yield state.setdefault(name, {})

        with patch("plugins.debug.modify_json_file", fake_modify), patch(
            "plugins.debug.is_admin", return_value=True
        ), patch("plugins.debug.random.sample", return_value=[2]):
            created = await debug.gbLuckyPocket().ret(
                make_pack("发gb红包 5 2 fixture", member_id=1)
            )
        self.assertIsInstance(created.root[0], AtAll)

        with patch("plugins.debug.modify_json_file", fake_modify), patch(
            "plugins.debug.give_balance"
        ) as give, patch(
            "plugins.debug.bot_send_message", return_value=True
        ) as send:
            first = await debug.gbLuckyPocket().ret(
                make_pack("领gb红包", member_id=2, member_name="first")
            )
            final = await debug.gbLuckyPocket().ret(
                make_pack("领gb红包", member_id=3, member_name="second")
            )

        self.assertIn("你领取了 2 GB", first.asDisplay())
        self.assertIn("GB红包已被领完", final.asDisplay())
        self.assertEqual(state["gbLuckyPocket"]["100"]["index"], 2)
        self.assertEqual(give.call_count, 2)
        send.assert_called_once()

    async def test_pic_generation_returns_image_without_real_request(self):
        encoded = base64.b64encode(b"fixture image").decode("ascii")
        payload = {
            "generation_job_id": "fixture-job",
            "status": "completed",
            "result_data_url": f"data:image/png;base64,{encoded}",
        }
        with patch("plugins.debug.is_admin", return_value=True), patch(
            "plugins.debug.bot_send_message", return_value=True
        ), patch.object(
            debug.TooglePicGen,
            "run_generation_until_done",
            return_value=payload,
        ):
            result = await debug.TooglePicGen().ret(make_pack("土狗生图 fixture"))

        self.assertEqual(result.get(Image)[0].base64, encoded)
        self.assertIn("用时 ", result.asDisplay())

    def test_pic_generation_http_helpers_are_configurable(self):
        accepted_response = Mock()
        accepted_response.raise_for_status.return_value = None
        accepted_response.json.return_value = {"generation_job_id": "fixture-job"}
        with patch("plugins.debug.requests.post", return_value=accepted_response) as post:
            accepted = debug.TooglePicGen.submit_generation(
                "fixture",
                base_url="http://generator.invalid",
                token="fixture-token",
                timeout=3,
            )

        self.assertEqual(accepted["generation_job_id"], "fixture-job")
        self.assertEqual(post.call_args.args[0], "http://generator.invalid/api/generations")
        self.assertEqual(post.call_args.kwargs["timeout"], 3)

        running = Mock()
        running.raise_for_status.return_value = None
        running.json.return_value = {"status": "running"}
        completed = Mock()
        completed.raise_for_status.return_value = None
        completed.json.return_value = {"status": "completed"}
        with patch(
            "plugins.debug.requests.get",
            side_effect=[running, completed],
        ) as get:
            result = debug.TooglePicGen.poll_generation_job(
                "fixture-job",
                base_url="http://generator.invalid",
                token="fixture-token",
                interval=0,
                request_timeout=3,
                timeout=1,
            )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(get.call_count, 2)

    def test_pic_generation_reference_and_orchestration_helpers(self):
        encoded = base64.b64encode(b"reference image").decode("ascii")
        accepted_response = Mock()
        accepted_response.raise_for_status.return_value = None
        accepted_response.json.return_value = {"generation_job_id": "fixture-job"}
        with patch("plugins.debug.requests.post", return_value=accepted_response) as post:
            debug.TooglePicGen.submit_generation(
                "fixture",
                reference_image_base64_list=[f"data:image/png;base64,{encoded}"],
                base_url="http://generator.invalid",
                token="fixture-token",
                timeout=3,
            )

        sent_file = post.call_args.kwargs["files"][0]
        self.assertEqual(sent_file[0], "reference_images")
        self.assertEqual(sent_file[1][1], b"reference image")
        self.assertEqual(sent_file[1][2], "image/png")

        completed = {
            "generation_job_id": "fixture-job",
            "status": "completed",
            "result_data_url": f"data:image/png;base64,{encoded}",
        }
        with patch.object(
            debug.TooglePicGen,
            "submit_generation",
            return_value={"generation_job_id": "fixture-job"},
        ) as submit, patch.object(
            debug.TooglePicGen,
            "poll_generation_job",
            return_value=completed,
        ) as poll:
            result = debug.TooglePicGen.run_generation_until_done(
                "fixture",
                base_url="http://generator.invalid",
                token="fixture-token",
                interval=0,
                request_timeout=3,
                timeout=1,
            )

        self.assertIs(result, completed)
        submit.assert_called_once()
        poll.assert_called_once_with(
            "fixture-job",
            base_url="http://generator.invalid",
            token="fixture-token",
            interval=0,
            request_timeout=3,
            timeout=1,
        )
        self.assertEqual(
            debug.TooglePicGen.parse_generation_result_image_base64(result),
            encoded,
        )

    def test_debug_config_list_parser(self):
        with patch.dict(
            debug.config,
            {"TOOGLEPICGEN_GROUP_LIST": ["100", 200, "invalid"]},
            clear=False,
        ):
            self.assertEqual(
                debug._configured_int_set("TOOGLEPICGEN_GROUP_LIST"),
                {100, 200},
            )

    def test_pic_generation_requires_configured_token(self):
        with patch.dict(
            debug.config,
            {"TOOGLEPICGEN_ACCESS_TOKEN": ""},
            clear=False,
        ):
            with self.assertRaisesRegex(RuntimeError, "TOOGLEPICGEN_ACCESS_TOKEN"):
                debug.TooglePicGen.auth_headers()
        with patch.dict(
            debug.config,
            {"TOOGLEPICGEN_BASE_URL": ""},
            clear=False,
        ):
            with self.assertRaisesRegex(RuntimeError, "TOOGLEPICGEN_BASE_URL"):
                debug.TooglePicGen.api_base_url()


if __name__ == "__main__":
    unittest.main()
