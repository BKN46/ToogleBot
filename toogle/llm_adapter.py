"""Provider-neutral OpenAI-compatible LLM adapter.

All model HTTP traffic should go through this module. Provider profiles only
resolve credentials, base URLs and defaults; callers use capability methods.
"""

from __future__ import annotations

import json
import html
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

import requests

import configs


class LLMError(RuntimeError):
    """Base adapter error."""


class LLMConfigurationError(LLMError):
    """Provider profile is missing required configuration."""


class KimiSearchUnavailable(LLMError):
    """The official search execution service rejected a request."""


_DSML_INVOKE_RE = re.compile(
    r"<(?:｜｜DSML｜｜)?invoke\s+name=[\"'](?P<name>[^\"']+)[\"']\s*>"
    r"(?P<body>.*?)</(?:｜｜DSML｜｜)?invoke>",
    re.DOTALL,
)
_DSML_PARAMETER_RE = re.compile(
    r"<(?:｜｜DSML｜｜)?parameter\s+name=[\"'](?P<name>[^\"']+)[\"'][^>]*>"
    r"(?P<value>.*?)</(?:｜｜DSML｜｜)?parameter>",
    re.DOTALL,
)
_KIMI_SEARCH_PROGRESS_RE = re.compile(
    r"(?:请(?:稍等|稍候|耐心等待)|稍等(?:一下|片刻)|稍后(?:为你|为您)?(?:确认|回复|答复)"
    r"|(?:我(?:还)?(?:需要|将|会)|让我)[^。！？\n]{0,160}(?:搜索|查询|核实|确认|查证)[^。！？\n]*"
    r"|please\s+wait|let\s+me\s+(?:search|check|verify)[^.!?\n]*)[。！？.!?\s]*$",
    re.IGNORECASE,
)


def parse_dsml_tool_calls(content: str) -> tuple[list[dict[str, Any]], str]:
    """Extract DSML invoke blocks emitted by some OpenAI-compatible models.

    Returns synthetic OpenAI tool calls plus the human-readable content with
    the DSML blocks removed. The synthetic IDs let the next request use the
    normal assistant/tool message contract.
    """
    if not isinstance(content, str) or "DSML" not in content or "invoke" not in content:
        return [], content or ""
    calls: list[dict[str, Any]] = []
    spans: list[tuple[int, int]] = []
    for index, match in enumerate(_DSML_INVOKE_RE.finditer(content), start=1):
        arguments: dict[str, Any] = {}
        for parameter in _DSML_PARAMETER_RE.finditer(match.group("body")):
            arguments[parameter.group("name")] = html.unescape(parameter.group("value")).strip()
        calls.append({
            "id": f"dsml-call-{index}",
            "type": "function",
            "function": {"name": match.group("name"), "arguments": json.dumps(arguments, ensure_ascii=False)},
        })
        spans.append(match.span())
    if not calls:
        return [], content
    cleaned = content
    for start, end in reversed(spans):
        cleaned = cleaned[:start] + cleaned[end:]
    cleaned = re.sub(r"<｜｜DSML｜｜tool_calls>|</｜｜DSML｜｜tool_calls>", "", cleaned)
    return calls, cleaned.strip()


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    name: str
    api_key: str
    base_url: str
    model: str

    def endpoint(self, path: str = "/chat/completions") -> str:
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"


def _value(*keys: str, default: str = "") -> str:
    for key in keys:
        value = str(configs.config.get(key, "") or "").strip()
        if value:
            return value
    return default


def get_provider(name: str | None = None, *, model: str = "", url: str = "", api_key: str = "") -> ProviderConfig:
    requested = (name or "moonshot").strip().lower().replace("_", "-")
    aliases = {
        "deepseek": "deepseek",
        "ds": "deepseek",
        "moonshot": "moonshot",
        "kimi": "moonshot",
        "orcarouter": "orcarouter",
        "orca-router": "orcarouter",
        "openrouter": "orcarouter",
        "tencent": "tencent",
    }
    profile = aliases.get(requested)
    if not profile:
        raise LLMConfigurationError(f"unsupported LLM provider: {name!r}")
    defaults = {
        "deepseek": (
            ("GPTSecretDeepseek", "GPTSecret"),
            ("DEEPSEEK_WEB_URL",),
            ("DEEPSEEK_WEB_MODEL",),
            "https://api.deepseek.com",
            "deepseek-v4-flash-vision-exp",
        ),
        "moonshot": (
            ("GPTSecretMoonshot", "GPTSecret"),
            ("GPTUrl",),
            ("GPTModel",),
            "https://api.moonshot.cn/v1",
            "kimi-k3",
        ),
        "orcarouter": (
            ("ORCAROUTER_API_KEY",),
            ("ORCAROUTER_API_URL",),
            ("ORCAROUTER_MODEL",),
            "https://api.orcarouter.ai/v1",
            "z-ai/glm-5.3-flash",
        ),
        "tencent": (
            ("GPTSecretTencent", "GPTSecret"),
            ("GPTUrl",),
            ("GPTModel",),
            "https://api.openai.com/v1",
            "gpt-4o-mini",
        ),
    }
    key_keys, url_keys, model_keys, default_url, default_model = defaults[profile]
    # Legacy GPT call sites pass the Moonshot values explicitly. When the
    # default profile is switched, do not let those stale values override the
    # selected provider's own defaults.
    if profile == "orcarouter":
        if model in {str(configs.config.get("GPTModel", "")), str(configs.config.get("GPTModelLarge", ""))}:
            model = ""
        if url == str(configs.config.get("GPTUrl", "")):
            url = ""
    resolved_key = api_key.strip() or _value(*key_keys)
    resolved_url = url.strip() or _value(*url_keys, default=default_url)
    resolved_model = model.strip() or _value(*model_keys, default=default_model)
    if not resolved_key:
        raise LLMConfigurationError(f"{profile} API key is not configured")
    return ProviderConfig(profile, resolved_key, resolved_url, resolved_model)


class LLMAdapter:
    def kimi_search(self, text: str | list, *, model: str, url: str, settings: str = "") -> str:
        profile = get_provider("moonshot", model=model, url=url)
        formula = "/formulas/moonshot/web-search:latest"
        with requests.Session() as session:
            session.trust_env = False
            session.headers.update({"Authorization": f"Bearer {profile.api_key}"})

            def call(method: str, path: str, body=None):
                with session.request(method, profile.endpoint(path), json=body, timeout=(5, 60)) as response:
                    if response.status_code >= 400:
                        from toogle.logger import logger
                        stage = "search_execution" if path.endswith("/fibers") else (
                            "tool_declaration" if path.endswith("/tools") else "model")
                        logger.warning("Kimi search HTTP failure: stage=%s status=%d",
                                       stage, response.status_code)
                        if stage == "search_execution":
                            raise KimiSearchUnavailable(
                                "Kimi官方搜索工具暂不可用，请稍后重试。"
                            )
                    response.raise_for_status()
                    return response.json()

            tools = call("GET", formula + "/tools").get("tools")
            if not isinstance(tools, list) or not tools:
                raise LLMError("Kimi search tools unavailable")
            allowed = {tool["function"]["name"] for tool in tools}
            messages = self._messages(text, settings + (
                "\n请先使用联网搜索核实信息，再回答并注明依据。需要继续核实时请实际调用搜索工具，"
                "不要只回复搜索计划或请稍等；无法核实的内容请在最终答案中明确说明，不要编造。"
            ))
            max_rounds = 10
            max_searches = 10
            searches = 0
            final_requested = False
            for round_number in range(max_rounds):
                finalizing = searches >= max_searches or round_number == max_rounds - 1
                if finalizing and searches and not final_requested:
                    messages.append({
                        "role": "user",
                        "content": "搜索次数已达上限或已进入最后一次模型请求。请基于已有搜索证据直接给出完整最终答案并注明依据。"
                                   "未查到或不能确认的信息请明确说明，不要编造，不要描述下一步计划或说请稍等。",
                    })
                    final_requested = True
                result = call("POST", "/chat/completions", {
                    "model": profile.model, "messages": messages, "tools": tools,
                    "tool_choice": "none" if finalizing else "auto",
                    "max_tokens": 8000,
                })
                choice = result["choices"][0]
                message = choice["message"]
                calls = message.get("tool_calls") or []
                if not calls:
                    content = message.get("content") or ""
                    if choice.get("finish_reason") != "stop" or not content.strip():
                        raise LLMError("Kimi search answer incomplete")
                    if not searches:
                        if round_number == max_rounds - 1:
                            break
                        messages.extend([message, {"role": "user", "content": "请先调用联网搜索工具核实，不要仅凭记忆回答。"}])
                        continue
                    # A protocol stop can still be a search plan rather than an answer.
                    if _KIMI_SEARCH_PROGRESS_RE.search(content.strip()):
                        if round_number == max_rounds - 1:
                            raise LLMError("Kimi search returned only a progress message")
                        messages.extend([message, {
                            "role": "user",
                            "content": "上一条只说明了后续计划，没有完成回答。请继续完成查询并给出最终答案和依据。"
                                       "如果无法继续核实，请基于已有证据回答并说明缺失信息，不要再说请稍等。",
                        }])
                        continue
                    return content.strip() + "\n\n[通过Kimi搜索]"
                if choice.get("finish_reason") == "length":
                    raise LLMError("Kimi search tool call incomplete")
                if searches + len(calls) > max_searches or finalizing:
                    raise LLMError("Kimi search tool budget exceeded")
                # Preserve reasoning_content as required by K2.7 thinking/tool turns.
                messages.append(message)
                for tool_call in calls:
                    function = tool_call["function"]
                    if function.get("name") not in allowed:
                        raise LLMError("Kimi returned an unknown search tool")
                    fiber = call("POST", formula + "/fibers", function)
                    if fiber.get("status") != "succeeded":
                        raise LLMError("Kimi search execution failed")
                    context = fiber.get("context") or {}
                    output = context.get("output") or context.get("encrypted_output")
                    if not output:
                        raise LLMError("Kimi search returned no evidence")
                    messages.append({"role": "tool", "tool_call_id": tool_call["id"],
                                     "content": output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)})
                    searches += 1
            raise LLMError("Kimi search did not produce a verified answer")

    def __init__(self, *, proxies: Mapping[str, str] | None = None, verify: bool = False):
        self.proxies = dict(proxies or getattr(configs, "proxies", {}) or {}) or None
        self.verify = verify

    @staticmethod
    def _messages(text: str | list | None, settings: str = "", other_history: Iterable[Any] = ()) -> list[dict[str, Any]]:
        messages = [{"role": "user", "content": text}] if text is not None and text != "" else []
        if other_history:
            messages = [({"role": "user", "content": x} if isinstance(x, str) else x) for x in other_history] + messages
        if settings:
            messages.insert(0, {"role": "system", "content": settings})
        return messages

    def _request(self, provider: ProviderConfig, body: dict[str, Any], *, stream: bool = False, timeout: float = 60) -> requests.Response:
        kwargs = {
            "headers": {"Authorization": f"Bearer {provider.api_key}", "Content-Type": "application/json"},
            "json": body,
            "timeout": timeout,
            "stream": stream,
            "verify": self.verify,
        }
        try:
            response = requests.post(provider.endpoint(), proxies=self.proxies, **kwargs)
        except requests.exceptions.ProxyError as proxy_error:
            if not self.proxies:
                raise
            try:
                response = requests.post(provider.endpoint(), proxies=None, **kwargs)
            except requests.exceptions.RequestException as direct_error:
                raise direct_error from proxy_error
        response.raise_for_status()
        return response

    def chat(self, text: str | list | None = None, *, provider: str = "moonshot", model: str = "", url: str = "", api_key: str = "", settings: str = "", other_history: Iterable[Any] = (), tools: list | None = None, json_output: bool = False, raw_output: bool = False, other_params: Mapping[str, Any] | None = None, timeout: float = 60) -> Any:
        profile = get_provider(provider, model=model, url=url, api_key=api_key)
        body: dict[str, Any] = {"model": profile.model, "messages": self._messages(text, settings, other_history)}
        if profile.name == "orcarouter":
            body["reasoning_effort"] = "low"
        if tools:
            body["tools"] = tools
        if json_output:
            body["response_format"] = {"type": "json_object"}
        body.update(other_params or {})
        payload = self._request(profile, body, timeout=timeout).json()
        if raw_output:
            return payload
        try:
            return (payload["choices"][0]["message"].get("content") or "").strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("LLM response missing choices/message content") from exc

    def completion(self, text: str, *, provider: str = "moonshot", model: str = "", url: str = "", api_key: str = "", timeout: float = 30) -> str:
        profile = get_provider(provider, model=model, url=url, api_key=api_key)
        payload = self._request(profile, {"model": profile.model, "prompt": f"You: {text}\nAssistant: ", "max_tokens": 512, "temperature": 0.5, "top_p": 1, "n": 1, "stream": False, "stop": "You: "}, timeout=timeout).json()
        try:
            return str(payload["choices"][0]["text"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("LLM completion response missing text") from exc

    def chat_stream(self, text: str | list, *, provider: str = "moonshot", model: str = "", url: str = "", api_key: str = "", settings: str = "", other_history: Iterable[Any] = (), max_tokens: int = 1000, max_time: float = 30, tools: list | None = None) -> str:
        profile = get_provider(provider, model=model, url=url, api_key=api_key)
        body: dict[str, Any] = {"model": profile.model, "messages": self._messages(text, settings, other_history), "stream": True, "max_tokens": max_tokens}
        if profile.name == "orcarouter":
            body["reasoning_effort"] = "low"
        if tools:
            body["tools"] = tools
        response = self._request(profile, body, stream=True, timeout=15)
        content = ""
        started = time.monotonic()
        for line in response.iter_lines():
            if time.monotonic() - started > max_time:
                content += "\n[由于时长限制后续生成直接截断]"
                break
            if not line:
                continue
            decoded = line.decode("utf-8")
            if not decoded.startswith("data:") or decoded.endswith("[DONE]"):
                continue
            try:
                delta = json.loads(decoded[5:].strip())["choices"][0]["delta"]
            except (ValueError, KeyError, IndexError, TypeError):
                continue
            content += delta.get("content") or ""
        return content.strip()

    def stream_logic_chain(self, text: str | list, *, provider: str = "deepseek", model: str = "", url: str = "", api_key: str = "", settings: str = "", other_history: Iterable[Any] = (), max_tokens: int = 1000, max_time: float = 30, tools: list | None = None):
        result = self.chat_stream(text, provider=provider, model=model, url=url, api_key=api_key, settings=settings, other_history=other_history, max_tokens=max_tokens, max_time=max_time, tools=tools)
        yield {"yield": result, "reason": "", "res": result, "usage": 0, "error": "", "use_time": 0}

    def tool_loop(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], executor: Callable[[str, dict[str, Any]], Any], *, provider: str = "deepseek", model: str = "", url: str = "", api_key: str = "", max_rounds: int = 3, require_search: bool = False) -> tuple[str, list[str]]:
        profile = get_provider(provider, model=model, url=url, api_key=api_key)
        used: list[str] = []
        max_tool_rounds = max(1, max_rounds - 1)
        tool_rounds = 0
        tool_calls = 0
        final_requested = False
        for round_number in range(max_rounds if require_search else max_rounds + 2):
            if require_search and (round_number == max_rounds - 1 or tool_calls >= 10) and not final_requested:
                final_requested = True
                messages.append({"role": "user", "content": "请基于已有搜索证据给出完整最终答案，不要继续调用工具或说请稍等；无法核实的内容请明确说明。"})
            tools_enabled = tool_rounds < max_tool_rounds and not final_requested
            body: dict[str, Any] = {"model": profile.model, "messages": messages, "thinking": {"type": "disabled"}, "max_tokens": 8000 if require_search else 1000}
            if tools_enabled:
                body["tools"] = tools
                body["tool_choice"] = "auto"
            else:
                body["tool_choice"] = "none"
            payload = self._request(profile, body, timeout=60).json()
            try:
                choice = payload["choices"][0]
                assistant = choice.get("message") or {}
            except (KeyError, IndexError, TypeError) as exc:
                raise LLMError("LLM tool response missing choices") from exc
            structured_calls = assistant.get("tool_calls") or []
            dsml_calls, cleaned_content = parse_dsml_tool_calls(assistant.get("content") or "")
            if dsml_calls and not structured_calls:
                for index, call in enumerate(dsml_calls, start=1):
                    call["id"] = f"dsml-call-{round_number}-{index}"
                structured_calls = dsml_calls
                assistant = {"role": "assistant", "content": cleaned_content or None, "tool_calls": structured_calls}
            if not structured_calls:
                content = cleaned_content or assistant.get("content") or ""
                if require_search:
                    if choice.get("finish_reason") != "stop" or not content.strip():
                        raise LLMError("LLM search answer incomplete")
                    if not used:
                        if round_number == max_rounds - 1:
                            return "", used
                        messages.extend([assistant, {"role": "user", "content": "请先调用联网搜索核实，不要仅凭记忆回答。"}])
                        continue
                    if _KIMI_SEARCH_PROGRESS_RE.search(content.strip()):
                        messages.extend([assistant, {"role": "user", "content": "请完成查询并给出最终答案，不要只回复计划或请稍等。"}])
                        continue
                return content, used
            if require_search and (not tools_enabled or tool_calls + len(structured_calls) > 10):
                raise LLMError("LLM search tool budget exceeded")
            messages.append(assistant)
            for call in structured_calls:
                function = call.get("function") or {}
                name = function.get("name", "")
                try:
                    arguments = json.loads(function.get("arguments") or "{}")
                except (TypeError, ValueError):
                    arguments = {}
                result, label = executor(name, arguments)
                if label:
                    used.append(label)
                messages.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": json.dumps(result, ensure_ascii=False)})
            tool_rounds += 1
            tool_calls += len(structured_calls)
            if tool_rounds >= max_tool_rounds:
                final_requested = True
                messages.append({
                    "role": "user",
                    "content": "请基于以上搜索和页面内容直接给出完整最终答案。不要继续调用工具，不要描述搜索过程，不要说稍后确认。",
                })
        raise LLMError("LLM tool loop exceeded limit")


llm = LLMAdapter()

# Small module-level facade for plugins that do not need an adapter instance.
chat = llm.chat
chat_stream = llm.chat_stream
completion = llm.completion
stream_logic_chain = llm.stream_logic_chain
tool_loop = llm.tool_loop
