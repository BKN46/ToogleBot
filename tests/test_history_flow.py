import time
import unittest
from unittest.mock import patch

from plugins.gpt import AIConclude
from toogle.message import Group, Member, MessageChain
from toogle.message_handler import MESSAGE_HISTORY, MessagePack


class HistoryFlowTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.original_history = MESSAGE_HISTORY.history
        MESSAGE_HISTORY.history = {}

    async def asyncTearDown(self):
        MESSAGE_HISTORY.history = self.original_history

    async def test_ai_conclude_uses_current_message_history(self):
        group = Group(100, "group")
        previous = MessagePack(
            id=1,
            message=MessageChain.plain("previous discussion"),
            group=group,
            member=Member(200, "member"),
            quote=None,
        )
        previous.time = time.time() - 60
        command = MessagePack(
            id=2,
            message=MessageChain.plain("刚才在聊什么"),
            group=group,
            member=Member(201, "member"),
            quote=None,
        )
        MESSAGE_HISTORY.add(group.id, previous)
        MESSAGE_HISTORY.add(group.id, command)

        with patch("plugins.gpt.bot_send_message"), patch(
            "plugins.gpt.GetOpenAIConversation.get_chat", return_value="summary"
        ) as get_chat:
            result = await AIConclude().ret(command)

        self.assertTrue(result.asDisplay().endswith("summary"))
        self.assertIn("previous discussion", get_chat.call_args.args[0])
        self.assertNotIn("刚才在聊什么", get_chat.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
