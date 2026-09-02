import json
import unittest
from unittest.mock import Mock, patch

import configs
from toogle.llm_adapter import LLMAdapter, get_provider, parse_dsml_tool_calls


class LLMAdapterTest(unittest.TestCase):
    def setUp(self):
        self.original = dict(configs.config)

    def tearDown(self):
        configs.config.clear()
        configs.config.update(self.original)

    def test_profiles_resolve_provider_defaults(self):
        configs.config.update({
            "GPTSecretDeepseek": "deepseek-key",
            "GPTSecretMoonshot": "moonshot-key",
            "ORCAROUTER_API_KEY": "orca-key",
        })
        deepseek = get_provider("deepseek")
        moonshot = get_provider("moonshot")
        orca = get_provider("orcarouter")
        self.assertEqual(deepseek.name, "deepseek")
        self.assertEqual(deepseek.api_key, "deepseek-key")
        self.assertEqual(moonshot.base_url, "https://api.moonshot.cn/v1")
        self.assertEqual(orca.model, "z-ai/glm-5.3-flash")

    def test_parse_dsml_tool_calls_extracts_multiple_invocations(self):
        content = """<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="web_search">
<｜｜DSML｜｜parameter name="query" string="true">first query</｜｜DSML｜｜parameter>
</｜｜DSML｜｜invoke>
<｜｜DSML｜｜invoke name="web_search">
<｜｜DSML｜｜parameter name="query" string="true">second &amp; query</｜｜DSML｜｜parameter>
</｜｜DSML｜｜invoke>
</｜｜DSML｜｜tool_calls>"""
        calls, cleaned = parse_dsml_tool_calls(content)
        self.assertEqual([call["function"]["name"] for call in calls], ["web_search", "web_search"])
        self.assertEqual(json.loads(calls[1]["function"]["arguments"])["query"], "second & query")
        self.assertEqual(cleaned, "")

    def test_chat_uses_orcarouter_profile_and_openai_shape(self):
        configs.config.update({"ORCAROUTER_API_KEY": "orca-key", "GPTModel": "kimi-k3", "GPTUrl": "https://api.moonshot.cn/v1"})
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [{"message": {"content": "fixture answer"}}]
        }
        with patch("toogle.llm_adapter.requests.post", return_value=response) as post:
            result = LLMAdapter().chat("fixture", provider="orcarouter", model="kimi-k3", url="https://api.moonshot.cn/v1")
        self.assertEqual(result, "fixture answer")
        self.assertEqual(post.call_args.args[0], "https://api.orcarouter.ai/v1/chat/completions")
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer orca-key")
        self.assertEqual(post.call_args.kwargs["json"]["model"], "z-ai/glm-5.3-flash")

    def test_legacy_facade_can_switch_default_provider(self):
        configs.config.update({"LLM_DEFAULT_PROVIDER": "orcarouter", "ORCAROUTER_API_KEY": "orca-key", "GPTModel": "kimi-k3", "GPTUrl": "https://api.moonshot.cn/v1"})
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"choices": [{"message": {"content": "switched"}}]}
        from plugins.gpt import GetOpenAIConversation
        with patch("toogle.llm_adapter.requests.post", return_value=response) as post:
            result = GetOpenAIConversation.get_chat("fixture", model="kimi-k3", url="https://api.moonshot.cn/v1")
        self.assertEqual(result, "switched")
        self.assertEqual(post.call_args.args[0], "https://api.orcarouter.ai/v1/chat/completions")

    def test_tool_loop_executes_callback_and_returns_final_content(self):
        configs.config.update({"GPTSecretDeepseek": "deepseek-key"})
        first = Mock()
        first.raise_for_status.return_value = None
        first.json.return_value = {
            "choices": [{
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "tool_calls": [{
                        "id": "call-1",
                        "function": {"name": "fixture", "arguments": json.dumps({"q": "x"})},
                    }],
                },
            }]
        }
        second = Mock()
        second.raise_for_status.return_value = None
        second.json.return_value = {
            "choices": [{"finish_reason": "stop", "message": {"content": "done"}}]
        }
        tool = [{"type": "function", "function": {"name": "fixture"}}]
        with patch("toogle.llm_adapter.requests.post", side_effect=[first, second]):
            result, used = LLMAdapter().tool_loop(
                [{"role": "user", "content": "x"}],
                tool,
                lambda name, args: ({"ok": args["q"]}, "fixture-engine"),
                provider="deepseek",
            )
        self.assertEqual(result, "done")
        self.assertEqual(used, ["fixture-engine"])

    def test_tool_loop_normalizes_dsml_content_and_does_not_leak_protocol(self):
        configs.config.update({"GPTSecretDeepseek": "deepseek-key"})
        first = Mock()
        first.raise_for_status.return_value = None
        first.json.return_value = {
            "choices": [{
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": """<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="fixture">
<｜｜DSML｜｜parameter name="q" string="true">x</｜｜DSML｜｜parameter>
</｜｜DSML｜｜invoke>
</｜｜DSML｜｜tool_calls>"""},
            }]
        }
        second = Mock()
        second.raise_for_status.return_value = None
        second.json.return_value = {
            "choices": [{"finish_reason": "stop", "message": {"content": "clean final"}}]
        }
        with patch("toogle.llm_adapter.requests.post", side_effect=[first, second]) as post:
            result, used = LLMAdapter().tool_loop(
                [{"role": "user", "content": "x"}],
                [{"type": "function", "function": {"name": "fixture"}}],
                lambda name, args: ({"ok": args["q"]}, "fixture-engine"),
                provider="deepseek",
            )
        self.assertEqual(result, "clean final")
        self.assertEqual(used, ["fixture-engine"])
        self.assertEqual(post.call_count, 2)
        second_messages = post.call_args_list[1].kwargs["json"]["messages"]
        self.assertEqual(second_messages[-2]["role"], "assistant")
        self.assertEqual(second_messages[-1]["role"], "tool")

    def test_tool_loop_finishes_after_dsml_open_url_in_finalization_round(self):
        configs.config.update({"GPTSecretDeepseek": "deepseek-key"})
        responses = []
        for index, name in enumerate(("web_search", "web_search", "open_url")):
            response = Mock()
            response.raise_for_status.return_value = None
            argument = {"query": f"query {index}"} if name == "web_search" else {"url": "https://example.com"}
            response.json.return_value = {
                "choices": [{
                    "finish_reason": "tool_calls" if index < 2 else "stop",
                    "message": {
                        "role": "assistant",
                        "content": "checking",
                        "tool_calls": [{
                            "id": f"call-{index}",
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(argument)},
                        }],
                    },
                }]
            }
            responses.append(response)
        final = Mock()
        final.raise_for_status.return_value = None
        final.json.return_value = {"choices": [{"finish_reason": "stop", "message": {"content": "complete answer"}}]}
        responses.append(final)
        captured = []

        def post_fixture(*args, **kwargs):
            captured.append(json.loads(json.dumps(kwargs["json"])))
            return responses[len(captured) - 1]

        def execute(name, arguments):
            if name == "web_search":
                return {"results": [arguments["query"]]}, "SerpApi Google"
            return {"content": "page"}, ""

        with patch("toogle.llm_adapter.requests.post", side_effect=post_fixture):
            result, used = LLMAdapter().tool_loop(
                [{"role": "user", "content": "x"}],
                [{"type": "function", "function": {"name": "web_search"}}, {"type": "function", "function": {"name": "open_url"}}],
                execute,
                provider="deepseek",
            )
        self.assertEqual(result, "complete answer")
        self.assertEqual(used, ["SerpApi Google", "SerpApi Google"])
        self.assertEqual(len(captured), 4)
        self.assertEqual(captured[3]["messages"][-2]["role"], "tool")
        self.assertEqual(captured[3]["messages"][-1]["role"], "user")

    def test_proxy_failure_retries_llm_request_direct(self):
        configs.config.update({"ORCAROUTER_API_KEY": "orca-key"})
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"choices": [{"message": {"content": "direct"}}]}
        with patch("toogle.llm_adapter.requests.post", side_effect=[
            __import__("requests").exceptions.ProxyError("proxy down"), response
        ]) as post:
            result = LLMAdapter(proxies={"https": "http://127.0.0.1:5876"}).chat("fixture", provider="orcarouter")
        self.assertEqual(result, "direct")
        self.assertIsNone(post.call_args_list[1].kwargs["proxies"])


if __name__ == "__main__":
    unittest.main()
