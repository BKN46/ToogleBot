import copy
import unittest
from unittest.mock import MagicMock, patch

from configs import config
from toogle.llm_adapter import KimiSearchUnavailable, LLMAdapter, LLMError


TOOLS = {"tools": [{"type": "function", "function": {"name": "web_search"}}]}
EVIDENCE = {"status": "succeeded", "context": {"encrypted_output": "encrypted fixture"}}
PROGRESS = "我需要进一步确认650 km极地/太阳同步轨道的具体报价，以及中国商业发射的最新价格区间。请稍等。"


def tool_turn(*call_ids):
    return {"choices": [{"finish_reason": "tool_calls", "message": {
        "role": "assistant", "content": "我会继续查询。", "reasoning_content": "reasoning fixture",
        "tool_calls": [{"id": call_id, "type": "function", "function": {
            "name": "web_search", "arguments": '{"query":"fixture"}'}} for call_id in call_ids],
    }}]}


def answer_turn(content, finish_reason="stop"):
    return {"choices": [{"message": {"role": "assistant", "content": content},
                          "finish_reason": finish_reason}]}


class KimiSearchTests(unittest.TestCase):
    def run_search(self, payloads, seen=None):
        session = MagicMock()
        seen = [] if seen is None else seen
        def request(method, url, **kwargs):
            seen.append((method, url, copy.deepcopy(kwargs)))
            response = MagicMock()
            response.__enter__.return_value = response
            payload = copy.deepcopy(payloads.pop(0))
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
            ] * 10)

    def test_reported_progress_reply_continues_search_with_context(self):
        progress = answer_turn(PROGRESS)
        result, seen = self.run_search([
            TOOLS, tool_turn("s1"), EVIDENCE, progress,
            tool_turn("s2"), EVIDENCE, answer_turn("fixture final answer"),
        ])
        self.assertEqual(result, "fixture final answer\n\n[通过Kimi搜索]")
        continuation = seen[4][2]["json"]
        self.assertEqual(continuation["tool_choice"], "auto")
        self.assertEqual(continuation["messages"][-2], progress["choices"][0]["message"])
        self.assertEqual(continuation["messages"][-4]["reasoning_content"], "reasoning fixture")
        self.assertIn("完成查询", continuation["messages"][-1]["content"])

    def test_ten_searches_are_allowed_then_explicitly_finalize(self):
        call_ids = [f"s{index}" for index in range(10)]
        result, seen = self.run_search([
            TOOLS, tool_turn(*call_ids), *([EVIDENCE] * 10), answer_turn("final answer"),
        ])
        self.assertIn("final answer", result)
        self.assertEqual(sum(url.endswith("/fibers") for _, url, _ in seen), 10)
        final_body = seen[-1][2]["json"]
        self.assertEqual(final_body["tool_choice"], "none")
        self.assertIn("完整最终答案", final_body["messages"][-1]["content"])
        self.assertEqual([message["tool_call_id"] for message in final_body["messages"]
                          if message["role"] == "tool"], call_ids)

    def test_tenth_model_request_is_reserved_for_final_answer(self):
        payloads = [TOOLS]
        for index in range(9):
            payloads.extend([tool_turn(f"s{index}"), EVIDENCE])
        payloads.append(answer_turn("final answer"))
        _, seen = self.run_search(payloads)
        model_requests = [kwargs["json"] for _, url, kwargs in seen if url.endswith("/chat/completions")]
        self.assertEqual(len(model_requests), 10)
        self.assertTrue(all(body["tool_choice"] == "auto" for body in model_requests[:-1]))
        self.assertEqual(model_requests[-1]["tool_choice"], "none")
        self.assertIn("完整最终答案", model_requests[-1]["messages"][-1]["content"])

    def test_progress_after_search_budget_can_still_be_repaired(self):
        result, seen = self.run_search([
            TOOLS, tool_turn(*(f"s{index}" for index in range(10))), *([EVIDENCE] * 10),
            answer_turn(PROGRESS), answer_turn("无法确认具体报价；已查到的依据为fixture。"),
        ])
        self.assertNotIn(PROGRESS, result)
        self.assertEqual(seen[-1][2]["json"]["tool_choice"], "none")

    def test_repeated_progress_fails_within_ten_model_requests(self):
        seen = []
        with self.assertRaisesRegex(LLMError, "progress message"):
            self.run_search([TOOLS, tool_turn("s1"), EVIDENCE] + [answer_turn(PROGRESS)] * 9, seen)
        self.assertEqual(sum(url.endswith("/chat/completions") for _, url, _ in seen), 10)

    def test_factual_uncertainty_is_a_valid_final_answer(self):
        answer = "公开资料未披露650 km太阳同步轨道报价，需要进一步确认。"
        result, seen = self.run_search([TOOLS, tool_turn("s1"), EVIDENCE, answer_turn(answer)])
        self.assertEqual(result, answer + "\n\n[通过Kimi搜索]")
        self.assertEqual(len(seen), 4)

    def test_truncated_answer_cannot_return_success(self):
        with self.assertRaisesRegex(LLMError, "answer incomplete"):
            self.run_search([TOOLS, tool_turn("s1"), EVIDENCE, answer_turn("partial", "length")])

    def test_over_budget_batch_is_rejected_before_any_search_executes(self):
        seen = []
        with self.assertRaisesRegex(LLMError, "budget exceeded"):
            self.run_search([TOOLS, tool_turn(*(f"s{index}" for index in range(11)))], seen)
        self.assertFalse(any(url.endswith("/fibers") for _, url, _ in seen))

    def test_formula_server_failure_is_identified_as_search_unavailable(self):
        with self.assertRaises(KimiSearchUnavailable):
            self.run_search([
                {"tools": [{"function": {"name": "web_search"}}]},
                {"choices": [{"message": {"role": "assistant", "tool_calls": [
                    {"id": "s1", "function": {"name": "web_search", "arguments": "{}"}}
                ]}}]},
                {"_http_status": 500, "error": {"message": "upstream unauthorized"}},
            ])
