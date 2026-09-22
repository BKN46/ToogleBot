import unittest
from unittest.mock import patch

import requests

from plugins.gpt import GetOpenAIConversation, WhatIs, SearchExecutionError, llm
from toogle.llm_adapter import KimiSearchUnavailable


class SearchFallbackTests(unittest.TestCase):
    def test_kimi_success_does_not_call_fallback(self):
        with patch.object(llm, "kimi_search", return_value="kimi answer"), \
             patch.object(GetOpenAIConversation, "get_web_search") as fallback:
            self.assertEqual(WhatIs.search_with_fallback("fixture"), "kimi answer")
            fallback.assert_not_called()

    def test_search_server_and_network_failures_use_flash_with_local_search(self):
        for error in [KimiSearchUnavailable("fixture"), requests.ReadTimeout("fixture"), requests.HTTPError("fixture")]:
            with patch.object(llm, "kimi_search", side_effect=error), \
                 patch.object(GetOpenAIConversation, "get_web_search", return_value="local answer") as fallback:
                self.assertEqual(WhatIs.search_with_fallback("fixture", model="kimi-k2.7-code"), "local answer")
                self.assertEqual(fallback.call_args.kwargs["model"], "deepseek-flash")
                self.assertTrue(fallback.call_args.kwargs["require_search"])

    def test_fallback_must_actually_search(self):
        with patch.object(llm, "tool_loop", return_value=("memory only", [])):
            with self.assertRaises(SearchExecutionError):
                GetOpenAIConversation.get_web_search("fixture", require_search=True)

    def test_both_fail_return_free_error(self):
        import asyncio
        from toogle.message import Group, Member, MessageChain
        from toogle.message_handler import MessagePack
        message = MessagePack(id=1, message=MessageChain.plain("查一下 fixture"),
                              group=Group(100, "fixture"), member=Member(200, "fixture"),
                              quote=None, message_type="group")
        with patch.object(llm, "kimi_search", side_effect=KimiSearchUnavailable("fixture")), \
             patch.object(GetOpenAIConversation, "get_web_search", side_effect=SearchExecutionError("fixture")):
            result = asyncio.run(WhatIs().ret(message))
        self.assertTrue(result.no_charge)
        self.assertTrue(result.no_interval)
