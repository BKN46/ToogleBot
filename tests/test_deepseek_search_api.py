import asyncio
import copy
import json
import unittest
from unittest.mock import MagicMock, patch

import requests

from configs import config
from plugins.gpt import SearchExecutionError, WhatIs, llm
from toogle.llm_adapter import LLMError
from toogle.message import Group, Member, MessageChain, Plain, Quote
from toogle.message_handler import MessagePack
from tools import web_search


SEARCH_FIXTURE = {"results": [{
    "rerank_score": 2.4, "title": "Fixture title", "url": "https://example.com/article",
    "snippet": "Short snippet", "summary": "Detailed evidence for the model",
    "content": "", "site_name": "Fixture News", "site_icon": None,
    "date": "2026-10-16T00:00:00Z", "authority": 3,
}]}


def tool_turn(count=1):
    return {"choices": [{"finish_reason": "tool_calls", "message": {
        "role": "assistant", "content": None, "tool_calls": [{
            "id": f"search-{index}", "type": "function", "function": {
                "name": "web_search", "arguments": '{"query":"fixture query"}',
            },
        } for index in range(count)],
    }}]}


def answer_turn(text="Final answer", finish_reason="stop"):
    return {"choices": [{"finish_reason": finish_reason,
                         "message": {"role": "assistant", "content": text}}]}


class DeepSeekSearchAPITests(unittest.TestCase):
    def setUp(self):
        self.config_patch = patch.dict(config, {
            "GPTSecretDeepseek": "fixture-key", "WEB_SEARCH_MAX_RESULTS": "10",
            "WEB_SEARCH_TIMEOUT_SECONDS": "10", "WEB_SEARCH_PROVIDER": "serpapi",
            "WEB_SEARCH_API_URL": "https://legacy.invalid/search",
            "KIMI_SEARCH_MODEL": "old-model", "DEEPSEEK_WEB_MODEL": "old-model",
            "DEEPSEEK_WEB_URL": "https://api.deepseek.com",
        }, clear=True)
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)
        self.session = MagicMock()
        self.response = self.session.post.return_value.__enter__.return_value
        self.response.json.return_value = copy.deepcopy(SEARCH_FIXTURE)
        session_patch = patch("tools.web_search.requests.Session")
        session_patch.start().return_value.__enter__.return_value = self.session
        self.addCleanup(session_patch.stop)

    def test_official_endpoint_auth_body_and_long_summary(self):
        result = web_search.search_deepseek("fixture query")
        self.session.post.assert_called_once_with(
            "https://api.deepseek.com/v1/tools/search",
            headers={"Authorization": "Bearer fixture-key", "Content-Type": "application/json"},
            json={"query": "fixture query", "count": 10, "need_content": False}, timeout=(5, 10.0),
        )
        self.assertFalse(self.session.trust_env)
        self.assertEqual(result.provider, "deepseek")
        self.assertEqual(result.results[0].snippet, "Detailed evidence for the model")
        self.assertEqual(result.results[0].source, "Fixture News")
        self.assertEqual(result.results[0].published, "2026-10-16T00:00:00Z")

    def test_query_length_and_count_bounds(self):
        for query in ["", " \t", "x" * 129]:
            with self.subTest(query_length=len(query)), self.assertRaises(web_search.SearchResponseError):
                web_search.search_deepseek(query)
        self.session.post.assert_not_called()
        web_search.search_deepseek("x" * 128, max_results=100)
        self.assertEqual(self.session.post.call_args.kwargs["json"]["count"], 50)

    def test_empty_results_are_valid_but_invalid_schema_is_rejected(self):
        self.response.json.return_value = {"results": []}
        self.assertEqual(web_search.search_deepseek("fixture").results, ())
        for payload in [{}, [], {"results": None}, {"results": [None]}, {"results": [{"url": "invalid"}]}]:
            with self.subTest(payload=payload), self.assertRaises(web_search.SearchResponseError):
                self.response.json.return_value = payload
                web_search.search_deepseek("fixture")
        self.response.json.side_effect = ValueError("bad JSON")
        with self.assertRaises(web_search.SearchResponseError):
            web_search.search_deepseek("fixture")

    def test_missing_credentials_fail_before_http(self):
        with patch.dict(config, {"GPTSecretDeepseek": ""}, clear=True):
            with self.assertRaises(web_search.SearchConfigurationError):
                web_search.search_deepseek("fixture")
        self.session.post.assert_not_called()

    def model_requests(self, payloads):
        seen = []

        def request(profile, body, **kwargs):
            self.assertEqual(profile.model, "deepseek-flash")
            self.assertEqual(profile.base_url, "https://api.deepseek.com")
            seen.append(copy.deepcopy(body))
            response = MagicMock()
            response.json.return_value = payloads.pop(0)
            return response

        request_patch = patch.object(llm, "_request", side_effect=request)
        request_patch.start()
        self.addCleanup(request_patch.stop)
        return seen

    def test_command_round_trip_only_uses_deepseek_for_group_and_private(self):
        for message_type, group_id in [("group", 100), ("private", 0)]:
            with self.subTest(message_type=message_type):
                seen = self.model_requests([tool_turn(), answer_turn()])
                message = MessagePack(id=42, message=MessageChain.plain("查一下 fixture"),
                                      group=Group(group_id, "fixture"), member=Member(200, "fixture"),
                                      quote=None, message_type=message_type)
                with patch.object(llm, "kimi_search") as kimi, \
                        patch("tools.web_search.search") as legacy:
                    result = asyncio.run(WhatIs().ret(message))
                kimi.assert_not_called()
                legacy.assert_not_called()
                self.assertEqual(result.get(Plain)[-1].text, "Final answer\n\n[通过DeepSeek搜索]")
                self.assertTrue(result.get(Quote))
                self.assertFalse(result.no_charge)
                tool_result = json.loads(seen[-1]["messages"][-1]["content"])
                self.assertEqual(tool_result["results"][0]["snippet"], "Detailed evidence for the model")

    def test_http_errors_do_not_use_any_fallback(self):
        for status in [401, 402, 429, 500]:
            with self.subTest(status=status):
                self.model_requests([tool_turn()])
                self.response.raise_for_status.side_effect = requests.HTTPError(str(status))
                with patch.object(llm, "kimi_search") as kimi, patch("tools.web_search.search") as legacy:
                    with self.assertRaises(SearchExecutionError):
                        WhatIs.search("fixture")
                kimi.assert_not_called()
                legacy.assert_not_called()

    def test_memory_only_answer_and_empty_search_results_cannot_succeed(self):
        self.model_requests([answer_turn("Memory only")] * 10)
        with self.assertRaises(SearchExecutionError):
            WhatIs.search("fixture")
        self.response.json.return_value = {"results": []}
        self.model_requests([tool_turn()] + [answer_turn("Memory only")] * 9)
        with self.assertRaises(SearchExecutionError):
            WhatIs.search("fixture")

    def test_progress_continues_with_context_and_truncation_fails(self):
        seen = self.model_requests([tool_turn(), answer_turn("请稍等。"), tool_turn(), answer_turn()])
        self.assertIn("Final answer", WhatIs.search("fixture"))
        self.assertEqual(seen[2]["messages"][-2]["content"], "请稍等。")
        self.model_requests([tool_turn(), answer_turn("Partial", "length")])
        with self.assertRaisesRegex(LLMError, "incomplete"):
            WhatIs.search("fixture")

    def test_search_budget_and_final_model_request(self):
        seen = self.model_requests([tool_turn(10), answer_turn()])
        WhatIs.search("fixture")
        self.assertEqual(self.session.post.call_count, 10)
        self.assertEqual(seen[-1]["tool_choice"], "none")
        self.session.post.reset_mock()
        self.model_requests([tool_turn(11)])
        with self.assertRaisesRegex(LLMError, "budget"):
            WhatIs.search("fixture")
        self.session.post.assert_not_called()
        seen = self.model_requests([tool_turn()] * 9 + [answer_turn()])
        WhatIs.search("fixture")
        self.assertEqual(len(seen), 10)
        self.assertEqual(seen[-1]["tool_choice"], "none")


if __name__ == "__main__":
    unittest.main()
