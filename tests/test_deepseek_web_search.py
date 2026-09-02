import copy
import json
import unittest
from unittest.mock import Mock, patch

from configs import config
from plugins.gpt import DEEPSEEK_WEB_MODEL, GetOpenAIConversation, SearchExecutionError, WhatIs
from toogle.message import Group, Member, MessageChain, Plain, Quote
from toogle.message_handler import MessagePack
from tools.web_search import SearchResponse, SearchResponseError, SearchResult


class DeepSeekWebSearchChainTest(unittest.TestCase):
    def test_function_tool_executes_search_and_returns_final_text(self):
        first = Mock()
        first.raise_for_status.return_value = None
        first.json.return_value = {
            "choices": [{
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_fixture",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": json.dumps({"query": "fixture query"}),
                        },
                    }],
                },
            }]
        }
        second = Mock()
        second.raise_for_status.return_value = None
        second.json.return_value = {
            "choices": [{
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "fixture answer"},
            }]
        }
        search_result = SearchResponse(
            query="fixture query",
            results=(SearchResult("Fixture", "https://example.com", "A snippet", "fixture"),),
            provider="json",
            took_ms=3,
        )
        captured = []

        def post_fixture(*args, **kwargs):
            captured.append(copy.deepcopy(kwargs))
            return (first, second)[len(captured) - 1]

        with patch.dict(config, {"GPTSecretDeepseek": "fixture-key"}, clear=False), \
                patch("plugins.gpt.requests.post", side_effect=post_fixture) as post, \
                patch("plugins.gpt.web_search.search", return_value=search_result) as search:
            result = GetOpenAIConversation.get_web_search("查一下 fixture", include_source=True)

        self.assertEqual(result, "fixture answer\n\n[通过自建搜索搜索]")
        search.assert_called_once_with("fixture query")
        self.assertEqual(post.call_count, 2)
        first_body = captured[0]["json"]
        self.assertEqual(first_body["model"], DEEPSEEK_WEB_MODEL)
        self.assertEqual(first_body["tools"][0]["type"], "function")
        self.assertEqual(first_body["tools"][0]["function"]["name"], "web_search")
        self.assertEqual(first_body["messages"][-1]["content"], "查一下 fixture")
        second_body = captured[1]["json"]
        self.assertEqual(second_body["messages"][-2]["role"], "assistant")
        tool_message = second_body["messages"][-1]
        self.assertEqual(tool_message["tool_call_id"], "call_fixture")
        self.assertEqual(json.loads(tool_message["content"]), search_result.as_dict())
        self.assertEqual(captured[0]["headers"]["Authorization"], "Bearer fixture-key")

    def test_what_is_keeps_plain_reply_and_quote_contract(self):
        message = MessagePack(
            id=42,
            message=MessageChain.plain("查一下 fixture"),
            group=Group(100, "fixture group"),
            member=Member(200, "fixture member"),
            quote=None,
            message_type="group",
        )

        async def run():
            with patch.object(GetOpenAIConversation, "get_web_search", return_value="fixture answer") as search:
                result = await WhatIs().ret(message)
                search.assert_called_once()
                self.assertTrue(search.call_args.kwargs["include_source"])
                return result

        import asyncio

        result = asyncio.run(run())
        self.assertEqual(result.get(Plain)[-1].asDisplay(), "fixture answer")
        self.assertIsNotNone(result.get(Quote))

    def test_repeated_searches_are_capped_then_forced_to_final_answer(self):
        responses = []
        for index in range(2):
            response = Mock()
            response.raise_for_status.return_value = None
            response.json.return_value = {
                "choices": [{
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": "searching",
                        "tool_calls": [{
                            "id": f"call_{index}",
                            "type": "function",
                            "function": {
                                "name": "web_search",
                                "arguments": json.dumps({"query": f"query {index}"}),
                            },
                        }],
                    },
                }]
            }
            responses.append(response)
        final = Mock()
        final.raise_for_status.return_value = None
        final.json.return_value = {
            "choices": [{
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "final answer"},
            }]
        }
        responses.append(final)
        search_result = SearchResponse("fixture", (SearchResult("title", "https://example.com"),), "fixture", 1)
        captured = []

        def post_fixture(*args, **kwargs):
            captured.append(copy.deepcopy(kwargs))
            return responses[len(captured) - 1]

        with patch.dict(config, {"GPTSecretDeepseek": "fixture-key"}, clear=False), \
                patch("plugins.gpt.requests.post", side_effect=post_fixture), \
                patch("plugins.gpt.web_search.search", return_value=search_result) as search:
            result = GetOpenAIConversation.get_web_search("查一下 fixture", include_source=True)

        self.assertEqual(result, "final answer\n\n[通过fixture搜索]")
        self.assertEqual(search.call_count, 2)
        self.assertEqual(len(captured), 3)
        self.assertNotIn("tools", captured[2]["json"])
        self.assertEqual(captured[2]["json"]["tool_choice"], "none")

    def test_search_failure_is_reported_separately_from_model_failure(self):
        message = MessagePack(
            id=43,
            message=MessageChain.plain("查一下 fixture"),
            group=Group(100, "fixture group"),
            member=Member(200, "fixture member"),
            quote=None,
            message_type="group",
        )

        async def run(error):
            with patch.object(GetOpenAIConversation, "get_web_search", side_effect=error):
                return await WhatIs().ret(message)

        import asyncio

        search_error = asyncio.run(run(SearchExecutionError("search down")))
        model_error = asyncio.run(run(RuntimeError("model down")))
        self.assertIn("搜索服务出错", search_error.asDisplay())
        self.assertIn("GPT模型服务可能出错", model_error.asDisplay())
        self.assertTrue(search_error.no_charge)
        self.assertTrue(search_error.no_interval)

    def test_page_fetch_failure_does_not_abort_search_answer(self):
        first = Mock()
        first.raise_for_status.return_value = None
        first.json.return_value = {"choices": [{
            "finish_reason": "tool_calls",
            "message": {"role": "assistant", "tool_calls": [{
                "id": "page-call",
                "type": "function",
                "function": {"name": "open_url", "arguments": json.dumps({"url": "https://example.com"})},
            }]},
        }]}
        second = Mock()
        second.raise_for_status.return_value = None
        second.json.return_value = {"choices": [{
            "finish_reason": "stop", "message": {"content": "answer from search"},
        }]}
        with patch.dict(config, {"GPTSecretDeepseek": "fixture-key"}, clear=False), \
                patch("plugins.gpt.llm._request", side_effect=[first, second]), \
                patch("plugins.gpt.web_search.open_url", side_effect=SearchResponseError("page timeout")):
            result = GetOpenAIConversation.get_web_search("查一下 fixture", include_source=True)
        self.assertEqual(result, "answer from search")


if __name__ == "__main__":
    unittest.main()
