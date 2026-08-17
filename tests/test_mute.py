import unittest
from unittest.mock import patch

from configs import config
from toogle import adapter
from plugins.admin import VOTE_MUTE_DICT, VoteMute
from toogle.message import Group, Image, Member, MessageChain, Quote
from toogle.message_handler import MessagePack


def make_vote_pack(member_id: int, quote_sender_id: int = 987) -> MessagePack:
    return MessagePack(
        id=member_id,
        message=MessageChain.plain("💩"),
        group=Group(123, "fixture group"),
        member=Member(member_id, "fixture member"),
        quote=Quote(
            456,
            quote_sender_id,
            123,
            123,
            MessageChain.plain("quoted message"),
        ),
        message_type="group",
    )


class VoteMuteTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        VOTE_MUTE_DICT.clear()

    def tearDown(self):
        VOTE_MUTE_DICT.clear()

    async def test_three_votes_offload_group_ban(self):
        with patch.dict(config, {"ANTI_SHIT_LIST": ["123"]}), patch(
            "plugins.admin.mute_member"
        ) as mute:
            plugin = VoteMute()
            for member_id in (1, 2, 3):
                await plugin.ret(make_vote_pack(member_id))

        mute.assert_called_once_with(123, 987, 600)

    async def test_quote_text_is_not_mixed_into_vote_command(self):
        message = make_vote_pack(1)
        wrapper = adapter.PluginWrapper(VoteMute)

        prepared = await wrapper.prepare(message)

        self.assertIsNotNone(prepared)
        self.assertEqual(prepared.message.asDisplay(), "💩")

    async def test_private_message_does_not_vote_or_call_group_ban(self):
        message = make_vote_pack(1)
        message.message_type = "private"
        with patch.dict(config, {"ANTI_SHIT_LIST": ["123"]}), patch(
            "plugins.admin.mute_member"
        ) as mute:
            await VoteMute().ret(message)

        mute.assert_not_called()
        self.assertEqual(VOTE_MUTE_DICT, {})

    async def test_missing_quote_sender_is_rejected(self):
        with patch.dict(config, {"ANTI_SHIT_LIST": ["123"]}), patch(
            "plugins.admin.mute_member"
        ) as mute:
            result = await VoteMute().ret(make_vote_pack(1, quote_sender_id=0))

        mute.assert_not_called()
        self.assertIn("找不到被引用消息", result.asDisplay())

    async def test_picture_detection_offloads_ban_and_recall(self):
        from toogle.msg_proc import shit_pic_detect

        message = make_vote_pack(1)
        message.message = MessageChain([Image(bytes=b"fixture")])
        with patch("toogle.msg_proc.is_shit_pic", return_value=True), patch(
            "toogle.msg_proc.mute_member"
        ) as mute, patch("toogle.msg_proc.recall_msg") as recall, patch(
            "toogle.msg_proc.bot_send_message"
        ):
            await shit_pic_detect(message, message.message.get(Image))

        mute.assert_called_once_with(123, 1, 600)
        recall.assert_called_once_with(1)

    async def test_admin_can_exempt_images_from_shit_registration(self):
        message = make_vote_pack(1)
        message.message = MessageChain.plain("这个不屎")
        message.quote.message = MessageChain([Image(bytes=b"fixture")])
        with patch("plugins.admin.is_admin", return_value=True), patch(
            "plugins.admin.unregister_shit_pic"
        ) as unregister:
            result = await VoteMute().ret(message)

        unregister.assert_called_once_with(b"fixture")
        self.assertIn("已取消 1 张图片", result.asDisplay())

    async def test_non_admin_cannot_exempt_images(self):
        message = make_vote_pack(1)
        message.message = MessageChain.plain("这个不屎")
        message.quote.message = MessageChain([Image(bytes=b"fixture")])
        with patch("plugins.admin.is_admin", return_value=False), patch(
            "plugins.admin.unregister_shit_pic"
        ) as unregister:
            result = await VoteMute().ret(message)

        unregister.assert_not_called()
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
