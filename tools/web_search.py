"""Small, provider-neutral online search client.

The module deliberately returns plain dataclasses so an AI tool adapter can use it
without depending on HTTP response details or the QQ message layer. Network I/O is
performed only when ``search``/``asearch`` is called, never at import time.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Protocol
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

import configs


class WebSearchError(RuntimeError):
    """Base error for configuration, transport, and response failures."""


class SearchConfigurationError(WebSearchError):
    """Raised when the selected provider cannot be configured."""


class SearchResponseError(WebSearchError):
    """Raised when a provider returns a response that cannot be normalized."""


class SearchQuotaExceeded(SearchResponseError):
    """Raised when a provider has exhausted its request quota."""

    def __init__(self, message: str, *, monthly: bool = False):
        super().__init__(message)
        self.monthly = monthly


_serpapi_quota_disabled_until = 0.0
_serpapi_quota_lock = threading.Lock()
_SERPAPI_QUOTA_STATE_PATH = Path(__file__).resolve().parents[1] / "data" / "serpapi_quota.json"


def _serpapi_quota_cooldown() -> float:
    return _positive_int(
        configs.config.get("SERPAPI_QUOTA_COOLDOWN_SECONDS", 86400),
        86400,
        maximum=30 * 24 * 60 * 60,
    )


def _serpapi_is_temporarily_disabled() -> bool:
    with _serpapi_quota_lock:
        if time.monotonic() < _serpapi_quota_disabled_until:
            return True
        try:
            state = json.loads(_SERPAPI_QUOTA_STATE_PATH.read_text(encoding="utf-8"))
            disabled_until = datetime.fromisoformat(str(state["disabled_until"]))
            return disabled_until > datetime.now(disabled_until.tzinfo)
        except (FileNotFoundError, OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return False


def _serpapi_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(str(configs.config.get("BOT_TIMEZONE", "Asia/Shanghai")))
    except Exception:
        return ZoneInfo("Asia/Shanghai")


def _next_month_start() -> datetime:
    now = datetime.now(_serpapi_timezone())
    return datetime(now.year + (now.month == 12), 1 if now.month == 12 else now.month + 1, 1, tzinfo=now.tzinfo)


def _disable_serpapi_for_quota(*, monthly: bool = False) -> None:
    global _serpapi_quota_disabled_until
    with _serpapi_quota_lock:
        if monthly:
            disabled_until = _next_month_start()
            _SERPAPI_QUOTA_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = _SERPAPI_QUOTA_STATE_PATH.with_suffix(".json.tmp")
            temporary_path.write_text(
                json.dumps({"disabled_until": disabled_until.isoformat(), "reason": "monthly_quota"}),
                encoding="utf-8",
            )
            temporary_path.replace(_SERPAPI_QUOTA_STATE_PATH)
            return
        _serpapi_quota_disabled_until = time.monotonic() + _serpapi_quota_cooldown()


def _looks_like_monthly_quota_error(value: Any) -> bool:
    text = str(value).strip().lower()
    return any(marker in text for marker in (
        "monthly limit", "monthly searches", "searches limit",
        "no searches left", "run out of searches", "out of searches",
    ))


def _looks_like_quota_error(value: Any) -> bool:
    text = str(value).strip().lower()
    return any(
        marker in text
        for marker in (
            "quota",
            "rate limit",
            "rate-limit",
            "monthly limit",
            "monthly searches",
            "searches limit",
            "too many requests",
            "exhausted",
            "no searches left",
            "run out of searches",
            "out of searches",
        )
    )


def open_url(url: str, *, max_chars: int = 8000) -> dict[str, str]:
    """Fetch a public HTTP(S) page and return compact readable text.

    This is intentionally provider-neutral and is used by LLM tool loops when
    a model needs to verify a search result. Private/local addresses are
    rejected to avoid turning the bot into an internal network fetcher.
    """
    parsed = urlparse(str(url).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SearchResponseError("open_url requires an http(s) URL")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        address = None
    if address and (address.is_private or address.is_loopback or address.is_link_local):
        raise SearchResponseError("open_url refuses private addresses")
    response = _request_get(
        str(url).strip(),
        headers={"Accept": "text/html,text/plain,application/xhtml+xml", "User-Agent": "ToogleBot/web-search"},
        timeout=min(_timeout(), 15.0),
        proxies=getattr(configs, "proxies", None),
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "noscript", "svg"]):
        element.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    text = " ".join(soup.get_text(" ", strip=True).split())
    return {"url": str(url).strip(), "title": title[:500], "content": text[:max_chars]}


@dataclass(frozen=True, slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    source: str = ""
    published: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def as_dict(self) -> dict[str, Any]:
        result = {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
        }
        if self.published:
            result["published"] = self.published
        return result


@dataclass(frozen=True, slots=True)
class SearchResponse:
    query: str
    results: tuple[SearchResult, ...]
    provider: str
    took_ms: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "provider": self.provider,
            "took_ms": self.took_ms,
            "results": [result.as_dict() for result in self.results],
        }


class SearchProvider(Protocol):
    name: str

    def search(self, query: str, max_results: int) -> list[SearchResult]: ...


def _positive_int(value: Any, default: int, *, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(parsed, maximum))


def _result_from_mapping(item: Mapping[str, Any]) -> SearchResult | None:
    url = str(item.get("url") or item.get("link") or item.get("href") or "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return None
    title = str(item.get("title") or item.get("name") or url).strip()
    snippet = str(
        item.get("snippet")
        or item.get("description")
        or item.get("content")
        or item.get("body")
        or ""
    ).strip()
    source = str(item.get("source") or "").strip()
    published = item.get("published") or item.get("publishedDate") or item.get("date")
    return SearchResult(
        title=title,
        url=url,
        snippet=snippet,
        source=source,
        published=str(published).strip() if published else None,
        raw=item,
    )


class DuckDuckGoProvider:
    name = "duckduckgo"

    def __init__(self, endpoint: str, timeout: float, proxies: Mapping[str, str] | None = None):
        self.endpoint = endpoint.rstrip("?")
        self.timeout = timeout
        self.proxies = dict(proxies or {}) or None

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        response = _request_get(
            self.endpoint,
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            headers={"Accept": "application/json", "User-Agent": "ToogleBot/web-search"},
            timeout=self.timeout,
            proxies=self.proxies,
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            raise SearchResponseError("DuckDuckGo returned invalid JSON") from exc
        if not isinstance(payload, Mapping):
            raise SearchResponseError("DuckDuckGo returned a non-object response")

        results: list[SearchResult] = []
        abstract = _result_from_mapping(
            {
                "title": payload.get("Heading"),
                "url": payload.get("AbstractURL"),
                "snippet": payload.get("AbstractText"),
                "source": "DuckDuckGo",
            }
        )
        if abstract:
            results.append(abstract)
        for topic in payload.get("RelatedTopics", []):
            if not isinstance(topic, Mapping):
                continue
            result = _result_from_mapping(
                {
                    "title": topic.get("Text"),
                    "url": topic.get("FirstURL"),
                    "snippet": topic.get("Text"),
                    "source": "DuckDuckGo",
                }
            )
            if result:
                results.append(result)
            if len(results) >= max_results:
                break
        if not results:
            raise SearchResponseError("DuckDuckGo returned no usable results")
        return results[:max_results]


class Qihoo360Provider:
    """HTML search fallback available on networks where DuckDuckGo is blocked."""

    name = "qihoo360"

    def __init__(self, endpoint: str, timeout: float, proxies: Mapping[str, str] | None = None):
        self.endpoint = endpoint
        self.timeout = timeout
        self.proxies = dict(proxies or {}) or None

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        response = _request_get(
            self.endpoint,
            params={"q": query},
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "User-Agent": "Mozilla/5.0 (ToogleBot web search)",
            },
            timeout=self.timeout,
            proxies=self.proxies,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        results: list[SearchResult] = []
        seen: set[str] = set()
        for item in soup.select(".r-results .res-list, li.res-list"):
            link = item.select_one(".res-title a, h3.res-title a")
            if not link and item.select_one("a.alink"):
                link = item.select_one("a.alink")
            if not link and item.select_one("a > h3.res-title"):
                link = item.select_one("a > h3.res-title").parent
            if not link:
                continue
            url = link.get("data-mdurl") or link.get("href")
            if not url or url in seen:
                continue
            seen.add(url)
            result = _result_from_mapping(
                {
                    "title": link.get_text(" ", strip=True),
                    "url": url,
                    "snippet": (
                        item.select_one(".summary, .res-desc, .res-list-summary").get_text(" ", strip=True)
                        if item.select_one(".summary, .res-desc, .res-list-summary")
                        else ""
                    ),
                    "source": item.select_one(".res-supplement, .mh-cite, cite").get_text(" ", strip=True)
                    if item.select_one(".res-supplement, .mh-cite, cite")
                    else "360搜索",
                }
            )
            if result:
                results.append(result)
            if len(results) >= max_results:
                break
        if not results:
            raise SearchResponseError("Qihoo360 returned no usable results")
        return results


class SerpApiProvider:
    """Structured Google results from SerpApi (no HTML scraping/captcha flow)."""

    name = "serpapi-google"

    def __init__(
        self,
        endpoint: str,
        timeout: float,
        api_key: str,
        language: str = "",
        country: str = "",
        proxies: Mapping[str, str] | None = None,
    ):
        if not api_key:
            raise SearchConfigurationError("SERPAPI_API_KEY is required for the serpapi provider")
        self.endpoint = endpoint or "https://serpapi.com/search.json"
        self.timeout = timeout
        self.api_key = api_key
        self.language = language
        self.country = country
        self.proxies = dict(proxies or {}) or None

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        params: dict[str, Any] = {
            "engine": "google",
            "q": query,
            "api_key": self.api_key,
            "num": max_results,
        }
        if self.language:
            # SerpApi accepts Google interface locales such as ``zh-CN``;
            # reducing them to ``zh`` produces a 400 response.
            params["hl"] = self.language
        if self.country:
            params["gl"] = self.country
        response = _request_get(
            self.endpoint,
            params=params,
            headers={"Accept": "application/json", "User-Agent": "ToogleBot/web-search"},
            timeout=self.timeout,
            proxies=self.proxies,
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            if getattr(response, "status_code", None) == 429:
                try:
                    error_payload = response.json()
                except ValueError:
                    error_payload = None
                if isinstance(error_payload, Mapping) and _looks_like_quota_error(error_payload.get("error")):
                    error = error_payload.get("error")
                    raise SearchQuotaExceeded(
                        "SerpApi quota exhausted",
                        monthly=_looks_like_monthly_quota_error(error),
                    ) from exc
            raise
        try:
            payload = response.json()
        except ValueError as exc:
            raise SearchResponseError("SerpApi returned invalid JSON") from exc
        if not isinstance(payload, Mapping):
            raise SearchResponseError("SerpApi returned a non-object response")
        if payload.get("error"):
            if _looks_like_quota_error(payload.get("error")):
                raise SearchQuotaExceeded(
                    "SerpApi quota exhausted",
                    monthly=_looks_like_monthly_quota_error(payload.get("error")),
                )
            raise SearchResponseError("SerpApi returned an API error")
        metadata = payload.get("search_metadata")
        if isinstance(metadata, Mapping) and _looks_like_quota_error(metadata.get("status")):
            raise SearchQuotaExceeded(
                "SerpApi quota exhausted",
                monthly=_looks_like_monthly_quota_error(metadata.get("status")),
            )
        items = payload.get("organic_results", [])
        if not isinstance(items, list):
            raise SearchResponseError("SerpApi organic_results must be an array")
        results = [
            result
            for item in items
            if isinstance(item, Mapping)
            for result in [_result_from_mapping(item)]
            if result is not None
        ][:max_results]
        if not results:
            raise SearchResponseError("SerpApi returned no usable results")
        return results


def provider_label(provider: str) -> str:
    """Human-readable provider name for message attribution."""
    return {
        "serpapi-google": "SerpApi Google",
        "duckduckgo": "DuckDuckGo",
        "qihoo360": "360",
        "json": "自建搜索",
    }.get(provider, provider)


class JsonSearchProvider:
    """Provider for SearXNG-like JSON APIs with a ``results`` array."""

    name = "json"

    def __init__(
        self,
        endpoint: str,
        timeout: float,
        api_key: str = "",
        language: str = "",
        proxies: Mapping[str, str] | None = None,
    ):
        if not endpoint:
            raise SearchConfigurationError("WEB_SEARCH_API_URL is required for the json provider")
        self.endpoint = endpoint
        self.timeout = timeout
        self.api_key = api_key
        self.language = language
        self.proxies = dict(proxies or {}) or None

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        headers = {"Accept": "application/json", "User-Agent": "ToogleBot/web-search"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        params: dict[str, Any] = {"q": query, "format": "json"}
        if self.language:
            params["language"] = self.language
        response = _request_get(
            self.endpoint,
            params=params,
            headers=headers,
            timeout=self.timeout,
            proxies=self.proxies,
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            raise SearchResponseError("search provider returned invalid JSON") from exc
        if not isinstance(payload, Mapping):
            raise SearchResponseError("search provider returned a non-object response")
        items = payload.get("results", [])
        if not isinstance(items, list):
            raise SearchResponseError("search provider results must be an array")
        return [
            result
            for item in items
            if isinstance(item, Mapping)
            for result in [_result_from_mapping(item)]
            if result is not None
        ][:max_results]


def _timeout() -> float:
    try:
        return max(0.1, min(float(configs.config.get("WEB_SEARCH_TIMEOUT_SECONDS", 10)), 120.0))
    except (TypeError, ValueError):
        return 10.0


def get_provider() -> SearchProvider:
    provider = str(configs.config.get("WEB_SEARCH_PROVIDER", "serpapi")).strip().lower()
    endpoint = str(configs.config.get("WEB_SEARCH_API_URL", "")).strip()
    proxies = getattr(configs, "proxies", None)
    if provider in {"serpapi", "serpapi-google", "google"}:
        return SerpApiProvider(
            endpoint or str(configs.config.get("SERPAPI_API_URL") or "https://serpapi.com/search.json"),
            _timeout(),
            str(configs.config.get("SERPAPI_API_KEY", "")).strip(),
            language=str(configs.config.get("WEB_SEARCH_LANGUAGE", "")),
            country=str(configs.config.get("SERPAPI_COUNTRY", "")),
            proxies=proxies,
        )
    if provider in {"duckduckgo", "ddg"}:
        return DuckDuckGoProvider(endpoint or "https://api.duckduckgo.com/", _timeout(), proxies)
    if provider in {"qihoo360", "360", "so"}:
        return Qihoo360Provider(endpoint or "https://m.so.com/index.php", _timeout(), proxies)
    if provider in {"json", "searxng", "generic"}:
        return JsonSearchProvider(
            endpoint,
            _timeout(),
            api_key=str(configs.config.get("WEB_SEARCH_API_KEY", "")),
            language=str(configs.config.get("WEB_SEARCH_LANGUAGE", "")),
            proxies=proxies,
        )
    raise SearchConfigurationError(f"unsupported WEB_SEARCH_PROVIDER: {provider!r}")


def _request_get(url: str, *, proxies: Mapping[str, str] | None = None, **kwargs: Any) -> requests.Response:
    """Use configured proxy first, then retry once without it when unavailable."""
    try:
        return requests.get(url, proxies=proxies, **kwargs)
    except requests.exceptions.ProxyError as proxy_error:
        if not proxies or not any(proxies.values()):
            raise
        try:
            return requests.get(url, proxies=None, **kwargs)
        except requests.exceptions.RequestException as direct_error:
            raise direct_error from proxy_error


def search(query: str, max_results: int | None = None) -> SearchResponse:
    """Search online and return normalized results.

    ``requests`` exceptions are intentionally allowed to retain their type and
    context for callers; provider/schema errors use ``WebSearchError`` subclasses.
    """
    query = str(query).strip()
    if not query:
        raise ValueError("search query must not be empty")
    configured_limit = _positive_int(configs.config.get("WEB_SEARCH_MAX_RESULTS", 5), 5, maximum=20)
    limit = configured_limit if max_results is None else _positive_int(max_results, configured_limit, maximum=20)
    configured_provider = str(configs.config.get("WEB_SEARCH_PROVIDER", "serpapi")).strip().lower()
    try:
        if configured_provider in {"serpapi", "serpapi-google", "google"} and _serpapi_is_temporarily_disabled():
            provider = DuckDuckGoProvider(
                "https://api.duckduckgo.com/", _timeout(), getattr(configs, "proxies", None)
            )
        else:
            provider = get_provider()
    except SearchConfigurationError:
        # A missing/invalid primary SerpApi configuration should not disable
        # the free fallback provider.
        if configured_provider in {"serpapi", "serpapi-google", "google"}:
            provider = DuckDuckGoProvider(
                "https://api.duckduckgo.com/", _timeout(), getattr(configs, "proxies", None)
            )
        else:
            raise
    started = time.monotonic()
    providers = [provider]
    if provider.name == "serpapi-google":
        providers.append(DuckDuckGoProvider("https://api.duckduckgo.com/", _timeout(), getattr(configs, "proxies", None)))
    if provider.name in {"serpapi-google", "duckduckgo"}:
        providers.append(Qihoo360Provider(
            str(configs.config.get("WEB_SEARCH_FALLBACK_URL") or "https://m.so.com/index.php"),
            _timeout(),
            getattr(configs, "proxies", None),
        ))
    last_error: Exception | None = None
    for candidate in providers:
        try:
            results = candidate.search(query, limit)
            provider = candidate
            break
        except SearchQuotaExceeded as exc:
            _disable_serpapi_for_quota(monthly=exc.monthly)
            last_error = exc
        except (requests.exceptions.RequestException, SearchResponseError) as exc:
            last_error = exc
    else:
        raise last_error or SearchResponseError("all configured search providers failed")
    return SearchResponse(
        query=query,
        results=tuple(results),
        provider=provider.name,
        took_ms=max(0, int((time.monotonic() - started) * 1000)),
    )


async def asearch(query: str, max_results: int | None = None) -> SearchResponse:
    """Async facade that keeps blocking HTTP off the event loop."""
    return await asyncio.to_thread(search, query, max_results)


async_search = asearch
search_web = search
web_search = search
