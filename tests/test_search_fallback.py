import unittest
from unittest.mock import patch

import requests

from plugins.gpt import GetOpenAIConversation, WhatIs, SearchExecutionError, llm
from toogle.llm_adapter import LLMError


class SearchFallbackTests(unittest.TestCase):
    def test_search_uses_flash_directly_without_kimi(self):
        with patch.object(llm, "kimi_search") as kimi, \
             patch.object(GetOpenAIConversation, "get_web_search", return_value="answer") as search:
            self.assertEqual(WhatIs.search("fixture"), "answer")
            self.assertEqual(search.call_args.kwargs["model"], "deepseek-flash")
            self.assertTrue(search.call_args.kwargs["require_search"])
            kimi.assert_not_called()

    def test_failures_do_not_fallback_to_kimi_or_other_search(self):
        for error in [SearchExecutionError("fixture"), LLMError("search returned only a progress message"),
                      requests.ReadTimeout("fixture"), requests.HTTPError("fixture")]:
            with self.subTest(error=type(error).__name__), \
                 patch.object(llm, "kimi_search") as kimi, \
                 patch("plugins.gpt.web_search.search") as legacy, \
                 patch.object(GetOpenAIConversation, "get_web_search", side_effect=error):
                with self.assertRaises(type(error)):
                    WhatIs.search("fixture")
                kimi.assert_not_called()
                legacy.assert_not_called()

    def test_command_must_actually_search(self):
        with patch.object(llm, "tool_loop", return_value=("memory only", [])):
            with self.assertRaises(SearchExecutionError):
                GetOpenAIConversation.get_web_search("fixture", require_search=True)

    def test_search_failure_returns_free_error(self):
        import asyncio
        from toogle.message import Group, Member, MessageChain
        from toogle.message_handler import MessagePack
        message = MessagePack(id=1, message=MessageChain.plain("查一下 fixture"),
                              group=Group(100, "fixture"), member=Member(200, "fixture"),
                              quote=None, message_type="group")
        with patch.object(GetOpenAIConversation, "get_web_search", side_effect=SearchExecutionError("fixture")):
            result = asyncio.run(WhatIs().ret(message))
        self.assertTrue(result.no_charge)
        self.assertTrue(result.no_interval)
