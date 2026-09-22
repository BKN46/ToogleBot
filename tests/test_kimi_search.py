import copy
import unittest
from unittest.mock import MagicMock, patch

from configs import config
from toogle.llm_adapter import KimiSearchUnavailable, LLMAdapter, LLMError


class KimiSearchTests(unittest.TestCase):
    def run_search(self, payloads):
        session = MagicMock()
        seen = []
        def request(method, url, **kwargs):
            seen.append((method, url, copy.deepcopy(kwargs)))
            response = MagicMock()
            response.__enter__.return_value = response
            payload = payloads.pop(0)
            response.status_code = payload.pop("_http_status", 200)
            response.json.return_value = payload
            return response
        session.request.side_effect = request
        with patch("toogle.llm_adapter.requests.Session") as factory, patch.dict(config, {"GPTSecretMoonshot": "fixture"}):
            factory.return_value.__enter__.return_value = session
            result = LLMAdapter().kimi_search("fixture", model="kimi-k2.7-code", url="https://example.com/v1")
        return result, seen

    def test_formula_roundtrip_preserves_reasoning_and_arguments(self):
        assistant = {"role": "assistant", "content": None, "reasoning_content": "reasoning fixture",
                     "tool_calls": [{"id": "search1", "type": "function", "function": {
                         "name": "web_search", "arguments": '{"query":"fixture"}'}}]}
        result, seen = self.run_search([
            {"tools": [{"type": "function", "function": {"name": "web_search"}}]},
            {"choices": [{"message": assistant, "finish_reason": "tool_calls"}]},
            {"status": "succeeded", "context": {"encrypted_output": "encrypted fixture"}},
            {"choices": [{"message": {"content": "answer"}, "finish_reason": "stop"}]},
        ])
        self.assertIn("Kimi搜索", result)
        self.assertEqual(seen[2][2]["json"], assistant["tool_calls"][0]["function"])
        body = seen[3][2]["json"]
        self.assertEqual(body["model"], "kimi-k2.7-code")
        self.assertNotIn("thinking", body)
        self.assertEqual(body["messages"][-2], assistant)
        self.assertEqual(body["messages"][-1]["content"], "encrypted fixture")

    def test_no_search_cannot_return_a_paid_unverified_answer(self):
        with self.assertRaises(LLMError):
            self.run_search([{"tools": [{"function": {"name": "web_search"}}]}] + [
                {"choices": [{"message": {"role": "assistant", "content": "memory answer"}, "finish_reason": "stop"}]}
            ] * 4)

    def test_formula_server_failure_is_identified_as_search_unavailable(self):
        with self.assertRaises(KimiSearchUnavailable):
            self.run_search([
                {"tools": [{"function": {"name": "web_search"}}]},
                {"choices": [{"message": {"role": "assistant", "tool_calls": [
                    {"id": "s1", "function": {"name": "web_search", "arguments": "{}"}}
                ]}}]},
                {"_http_status": 500, "error": {"message": "upstream unauthorized"}},
            ])
