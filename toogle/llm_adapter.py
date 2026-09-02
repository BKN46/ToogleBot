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

    def tool_loop(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], executor: Callable[[str, dict[str, Any]], Any], *, provider: str = "deepseek", model: str = "", url: str = "", api_key: str = "", max_rounds: int = 3) -> tuple[str, list[str]]:
        profile = get_provider(provider, model=model, url=url, api_key=api_key)
        used: list[str] = []
        max_tool_rounds = max(1, max_rounds - 1)
        tool_rounds = 0
        final_requested = False
        for round_number in range(max_rounds + 2):
            tools_enabled = tool_rounds < max_tool_rounds and not final_requested
            body: dict[str, Any] = {"model": profile.model, "messages": messages, "thinking": {"type": "disabled"}, "max_tokens": 1000}
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
                return (cleaned_content or assistant.get("content") or ""), used
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
