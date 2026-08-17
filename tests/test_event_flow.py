import asyncio
import json
import unittest
from unittest.mock import patch

from adapter import action_router, msg_queue
from adapter.server import decode_frame, encode_action, recv_loop, send_loop
from toogle import adapter
from toogle.message import (
    At,
    AtAll,
    ForwardMessage,
    Group,
    JsonCard,
    Markdown,
    Member,
    MessageChain,
    Plain,
    Quote,
    json_to_msg,
)
from toogle.message_handler import (
    MESSAGE_HISTORY,
    RECALL_HISTORY,
    MessageHandler,
    MessagePack,
)


def make_pack(
    message_id=1,
    text="hello",
    group_id=100,
    member_id=200,
    message_type="group",
    quote=None,
):
    return MessagePack(
        id=message_id,
        message=MessageChain.plain(text),
        group=Group(group_id if message_type == "group" else 0, "group"),
        member=Member(member_id, "member"),
        quote=quote,
        message_type=message_type,
    )


class EventConversionTest(unittest.TestCase):
    def setUp(self):
        self.previous_history = MESSAGE_HISTORY.history
        self.previous_recall_history = RECALL_HISTORY.history
        MESSAGE_HISTORY.history = {}
        RECALL_HISTORY.history = {}

    def tearDown(self):
        MESSAGE_HISTORY.history = self.previous_history
        RECALL_HISTORY.history = self.previous_recall_history

    def test_group_event_parses_segments_and_local_quote(self):
        original = make_pack(message_id=42, text="origin")
        MESSAGE_HISTORY.add(100, original)
        event = {
            "post_type": "message",
            "message_type": "group",
            "message_id": 43,
            "group_id": 100,
            "group_name": "fixture group",
            "user_id": 201,
            "self_id": 999,
            "time": 1234,
            "sender": {"user_id": 201, "card": "fixture user"},
            "message": [
                {"type": "reply", "data": {"id": "42"}},
                {"type": "text", "data": {"text": "hello"}},
                {"type": "at", "data": {"qq": "300"}},
                {"type": "at", "data": {"qq": "all"}},
                {"type": "future", "data": {}},
            ],
        }

        pack = msg_queue.parse_event(event)

        self.assertEqual(pack.id, 43)
        self.assertEqual(pack.group.name, "fixture group")
        self.assertEqual(pack.member.id, 201)
        self.assertEqual(pack.time, 1234)
        self.assertEqual(pack.message.get(At)[0].target, 300)
        self.assertEqual(len(pack.message.get(AtAll)), 1)
        self.assertIn("不支持的消息段:future", pack.message.asDisplay())
        self.assertIsNotNone(pack.quote)
        self.assertEqual(pack.quote.id, 42)
        self.assertEqual(pack.quote.message.asDisplay(), "origin")

    def test_self_message_is_not_enqueued(self):
        event = {
            "post_type": "message",
            "message_type": "private",
            "user_id": 999,
            "self_id": 999,
            "message": [],
            "sender": {"user_id": 999},
        }
        self.assertEqual(msg_queue.push_event(event), "self_message")

    def test_at_all_uses_standard_onebot_segment(self):
        result = msg_queue.toogle2nb(MessageChain([AtAll()]))
        self.assertEqual(result, [{"type": "at", "data": {"qq": "all"}}])

    def test_markdown_segment_round_trip(self):
        content = "# Fixture\n\n- **bold**\n- `code`"
        chain = msg_queue.nb2toogle(
            [{"type": "markdown", "data": {"content": content}}]
        )

        self.assertEqual(chain.get(Markdown)[0].content, content)
        self.assertEqual(chain.asDisplay(), content)
        self.assertEqual(
            msg_queue.toogle2nb(chain),
            [{"type": "markdown", "data": {"content": content}}],
        )

    def test_json_message_supports_markdown(self):
        chain = json_to_msg({"type": "markdown", "content": "**fixture**"})

        self.assertEqual(chain.get(Markdown)[0].content, "**fixture**")

    def test_json_card_segment_round_trip(self):
        payload = {
            "app": "com.tencent.structmsg",
            "prompt": "[fixture card]",
            "meta": {"news": {"title": "Fixture"}},
        }
        chain = msg_queue.nb2toogle(
            [{"type": "json", "data": {"data": payload}}]
        )

        card = chain.get(JsonCard)[0]
        payload["prompt"] = "mutated after parsing"
        self.assertEqual(card.data["prompt"], "[fixture card]")
        self.assertEqual(chain.asDisplay(), "[卡片消息]")
        self.assertEqual(
            card.to_dict(),
            {"type": "JsonCard", "data": "[redacted]", "data_type": "object"},
        )
        self.assertEqual(
            msg_queue.toogle2nb(chain),
            [
                {
                    "type": "json",
                    "data": {
                        "data": {
                            "app": "com.tencent.structmsg",
                            "prompt": "[fixture card]",
                            "meta": {"news": {"title": "Fixture"}},
                        }
                    },
                }
            ],
        )

    def test_json_card_string_and_internal_json_builder_are_lossless(self):
        payload = '{"app":"com.tencent.structmsg","prompt":"fixture"}'
        chain = json_to_msg({"type": "json_card", "content": payload})

        card = chain.get(JsonCard)[0]
        self.assertEqual(card.data, payload)
        self.assertEqual(
            msg_queue.toogle2nb(chain),
            [{"type": "json", "data": {"data": payload}}],
        )

    def test_invalid_json_card_degrades_without_exposing_payload(self):
        chain = msg_queue.nb2toogle(
            [{"type": "json", "data": {"data": ["not", "an", "object"]}}]
        )

        self.assertEqual(chain.asDisplay(), "[无效的卡片消息]")
        with self.assertRaises(ValueError):
            JsonCard('["not", "an", "object"]')

    def test_group_recall_notice_moves_message_to_recall_history(self):
        original = make_pack(message_id=42, text="recalled")
        MESSAGE_HISTORY.add(100, original)
        result = msg_queue.push_event(
            {
                "post_type": "notice",
                "notice_type": "group_recall",
                "group_id": 100,
                "message_id": 42,
            }
        )
        self.assertEqual(result, "notice")
        self.assertIs(RECALL_HISTORY.search(100, msg_id=42), original)

    def test_private_reply_preserves_member_target(self):
        captured = []
        original_send = adapter.BOT_SEND
        adapter.BOT_SEND = lambda pack: captured.append(pack) or True
        try:
            source = make_pack(message_type="private", member_id=321)
            self.assertTrue(adapter.bot_send_message(source, "reply"))
        finally:
            adapter.BOT_SEND = original_send
        self.assertEqual(captured[0].message_type, "private")
        self.assertEqual(captured[0].group.id, 0)
        self.assertEqual(captured[0].member.id, 321)

    def test_message_chain_flags_survive_quote_and_add(self):
        quote = Quote(1, 2, 3, 4, MessageChain.plain("origin"))
        left = MessageChain.plain("left", quote=quote, no_charge=True)
        right = MessageChain.plain("right", no_interval=True)
        result = left + right
        self.assertTrue(result.no_charge)
        self.assertTrue(result.no_interval)

    def test_forward_message_serializes_as_node_segments(self):
        chain = MessageChain(
            [
                ForwardMessage(
                    ForwardMessage.get_node_list(
                        [
                            (
                                123,
                                1700000000,
                                "Alice",
                                MessageChain.plain("hello"),
                            )
                        ]
                    ),
                    sender_id=0,
                    time=1700000000,
                    sender_name="fixture",
                    message_id=0,
                    message=MessageChain.plain("fixture forward"),
                )
            ]
        )

        self.assertEqual(
            msg_queue.toogle2nb(chain),
            [
                {
                    "type": "node",
                    "data": {
                        "user_id": 123,
                        "nickname": "Alice",
                        "content": [{"type": "text", "data": {"text": "hello"}}],
                    },
                }
            ],
        )

    def test_nested_forward_message_keeps_node_structure(self):
        inner = ForwardMessage(
            ForwardMessage.get_node_list(
                [(456, 1700000000, "Bob", MessageChain.plain("nested"))]
            ),
            sender_id=0,
            time=1700000000,
            sender_name="inner",
            message_id=0,
            message=MessageChain.plain("inner"),
        )
        outer = ForwardMessage(
            ForwardMessage.get_node_list(
                [(123, 1700000000, "Alice", MessageChain([inner]))]
            ),
            sender_id=0,
            time=1700000000,
            sender_name="outer",
            message_id=0,
            message=MessageChain.plain("outer"),
        )

        payload = msg_queue.toogle2nb(MessageChain([outer]))
        self.assertEqual(payload[0]["data"]["content"][0]["type"], "node")
        self.assertEqual(
            payload[0]["data"]["content"][0]["data"]["content"],
            [{"type": "text", "data": {"text": "nested"}}],
        )
        self.assertEqual(
            payload[0]["data"]["content"][0]["data"]["content"][0]["type"],
            "text",
        )

class QueueAndActionTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        msg_queue.reset_queues()
        msg_queue.bind_transport_loop(asyncio.get_running_loop())

    async def asyncTearDown(self):
        msg_queue.unbind_transport_loop(asyncio.get_running_loop())
        action_router.fail_pending(RuntimeError("test cleanup"))

    async def _take_action(self):
        action = await asyncio.wait_for(msg_queue.send_queue.get(), timeout=1)
        msg_queue.send_queue.task_done()
        return action

    async def test_private_action_has_echo_and_correct_target(self):
        pack = make_pack(message_type="private", member_id=321)
        self.assertTrue(msg_queue.send_message(pack))
        action = await asyncio.wait_for(msg_queue.send_queue.get(), timeout=1)
        msg_queue.send_queue.task_done()
        self.assertEqual(action["action"], "send_private_msg")
        self.assertEqual(action["params"]["user_id"], 321)
        self.assertTrue(action["echo"])

    async def test_group_forward_uses_forward_action_and_messages_nodes(self):
        chain = MessageChain(
            [
                ForwardMessage(
                    ForwardMessage.get_node_list(
                        [(123, 1700000000, "Alice", MessageChain.plain("hello"))]
                    ),
                    sender_id=0,
                    time=1700000000,
                    sender_name="fixture",
                    message_id=0,
                    message=MessageChain.plain("fixture"),
                )
            ]
        )
        pack = make_pack(message_type="group")
        pack.message = chain

        self.assertTrue(msg_queue.send_message(pack))
        action = await self._take_action()
        self.assertEqual(action["action"], "send_group_forward_msg")
        self.assertEqual(action["params"]["group_id"], 100)
        self.assertEqual(action["params"]["messages"][0]["type"], "node")

    async def test_private_forward_uses_private_forward_action(self):
        chain = MessageChain(
            [
                ForwardMessage(
                    ForwardMessage.get_node_list(
                        [(123, 1700000000, "Alice", MessageChain.plain("hello"))]
                    ),
                    sender_id=0,
                    time=1700000000,
                    sender_name="fixture",
                    message_id=0,
                    message=MessageChain.plain("fixture"),
                )
            ]
        )
        pack = make_pack(message_type="private", member_id=321)
        pack.message = chain

        self.assertTrue(msg_queue.send_message(pack))
        action = await self._take_action()
        self.assertEqual(action["action"], "send_private_forward_msg")
        self.assertEqual(action["params"]["user_id"], 321)
        self.assertIn("messages", action["params"])

    async def test_forward_message_cannot_mix_with_plain_segments(self):
        pack = make_pack(message_type="group")
        pack.message = MessageChain(
            [
                Plain("prefix"),
                ForwardMessage(
                    ForwardMessage.get_node_list(
                        [(123, 1700000000, "Alice", MessageChain.plain("hello"))]
                    ),
                    sender_id=0,
                    time=1700000000,
                    sender_name="fixture",
                    message_id=0,
                    message=MessageChain.plain("fixture"),
                ),
            ]
        )

        self.assertFalse(msg_queue.send_message(pack))
        self.assertTrue(msg_queue.send_queue.empty())

    async def test_action_response_is_correlated_by_echo(self):
        task = asyncio.create_task(action_router.call_action("get_status", timeout=1))
        action = await asyncio.wait_for(msg_queue.send_queue.get(), timeout=1)
        msg_queue.send_queue.task_done()
        response = {
            "status": "ok",
            "retcode": 0,
            "data": {"online": True},
            "echo": action["echo"],
        }
        self.assertTrue(action_router.resolve_response(response))
        self.assertEqual(await task, response)

    async def test_plugin_prepare_does_not_mutate_original_quote(self):
        class QuotedPlugin(MessageHandler):
            trigger = r"^command"

        quote = Quote(42, 2, 3, 100, MessageChain.plain(" origin"))
        original = make_pack(text="command", quote=quote)
        wrapper = adapter.PluginWrapper(QuotedPlugin)

        with patch("toogle.adapter.is_admin", return_value=True):
            first = await wrapper.prepare(original)
            second = await wrapper.prepare(original)

        self.assertEqual(original.message.asDisplay(), "command")
        self.assertEqual(first.message.asDisplay(), "command origin")
        self.assertEqual(second.message.asDisplay(), "command origin")

    async def test_recv_loop_skips_bad_frame_and_enqueues_event(self):
        event = {
            "post_type": "message",
            "message_type": "private",
            "message_id": 7,
            "user_id": 321,
            "self_id": 999,
            "sender": {"user_id": 321, "nickname": "fixture"},
            "message": [{"type": "text", "data": {"text": "hello"}}],
        }

        class FakeWebSocket:
            def __init__(self):
                self.frames = iter(["not-json", json.dumps(event)])

            async def recv(self):
                try:
                    return next(self.frames)
                except StopIteration:
                    raise asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await recv_loop(FakeWebSocket())
        pack = msg_queue.recv_queue.get_nowait()
        msg_queue.recv_queue.task_done()
        self.assertEqual(pack.member.id, 321)
        self.assertEqual(pack.message.asDisplay(), "hello")

    async def test_send_loop_serializes_action(self):
        sent = asyncio.Event()

        class FakeWebSocket:
            def __init__(self):
                self.frames = []

            async def send(self, frame):
                self.frames.append(frame)
                sent.set()

        ws = FakeWebSocket()
        msg_queue.send_queue.put_nowait(
            {"action": "get_status", "params": {}, "echo": "fixture"}
        )
        task = asyncio.create_task(send_loop(ws))
        await asyncio.wait_for(sent.wait(), timeout=1)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        self.assertEqual(json.loads(ws.frames[0])["echo"], "fixture")


class FrameCodecTest(unittest.TestCase):
    def test_frame_codec_requires_object_and_serializes_unicode(self):
        payload = {"action": "get_status", "params": {"text": "测试"}}
        encoded = encode_action(payload)
        self.assertEqual(decode_frame(encoded), payload)
        with self.assertRaises(ValueError):
            decode_frame("[]")


if __name__ == "__main__":
    unittest.main()
