import asyncio
import unittest
from unittest.mock import Mock, patch

import configs
import requests
from tools import web_search


class WebSearchTest(unittest.TestCase):
    def setUp(self):
        self.original = dict(configs.config)

    def tearDown(self):
        configs.config.clear()
        configs.config.update(self.original)

    def test_duckduckgo_results_are_normalized_and_limited(self):
        response = Mock()
        response.json.return_value = {
            "Heading": "Fixture",
            "AbstractText": "An abstract",
            "AbstractURL": "https://example.com/abstract",
            "RelatedTopics": [
                {"Text": "Result one", "FirstURL": "https://example.com/one"},
                {"Text": "Result two", "FirstURL": "https://example.com/two"},
            ],
        }
        with patch.dict(configs.config, {"WEB_SEARCH_PROVIDER": "duckduckgo"}, clear=False), \
                patch("tools.web_search.requests.get", return_value=response) as get:
            result = web_search.search("fixture", max_results=2)

        self.assertEqual(result.provider, "duckduckgo")
        self.assertEqual([item.url for item in result.results], [
            "https://example.com/abstract",
            "https://example.com/one",
        ])
        self.assertEqual(get.call_args.kwargs["params"]["q"], "fixture")
        response.raise_for_status.assert_called_once_with()

    def test_json_provider_uses_bearer_key_and_skips_invalid_urls(self):
        configs.config.update({
            "WEB_SEARCH_PROVIDER": "json",
            "WEB_SEARCH_API_URL": "https://search.example/api",
            "WEB_SEARCH_API_KEY": "fixture-key",
        })
        response = Mock()
        response.json.return_value = {
            "results": [
                {"title": "Good", "url": "https://example.com", "content": "text"},
                {"title": "Bad", "url": "javascript:alert(1)"},
            ]
        }
        with patch("tools.web_search.requests.get", return_value=response) as get:
            result = web_search.search("fixture")
        self.assertEqual(len(result.results), 1)
        self.assertEqual(get.call_args.kwargs["headers"]["Authorization"], "Bearer fixture-key")

    def test_serpapi_google_results_are_normalized(self):
        configs.config.update({
            "WEB_SEARCH_PROVIDER": "serpapi",
            "SERPAPI_API_KEY": "fixture-key",
        })
        response = Mock()
        response.json.return_value = {
            "organic_results": [
                {"title": "Fixture result", "link": "https://example.com", "snippet": "A snippet"},
                {"title": "Invalid result", "link": "javascript:alert(1)"},
            ]
        }
        with patch("tools.web_search.requests.get", return_value=response) as get:
            result = web_search.search("fixture", max_results=3)
        self.assertEqual(result.provider, "serpapi-google")
        self.assertEqual(len(result.results), 1)
        self.assertEqual(result.results[0].title, "Fixture result")
        self.assertEqual(get.call_args.kwargs["params"]["engine"], "google")
        self.assertEqual(get.call_args.kwargs["params"]["api_key"], "fixture-key")
        self.assertEqual(get.call_args.kwargs["params"]["hl"], "zh-CN")

    def test_serpapi_api_error_is_normalized_without_exposing_payload(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"error": "fixture secret should not escape"}
        with patch("tools.web_search.requests.get", return_value=response):
            with self.assertRaises(web_search.SearchResponseError) as ctx:
                web_search.SerpApiProvider(
                    "https://serpapi.example/search.json", 1, "fixture-key"
                ).search("fixture", 3)
        self.assertEqual(str(ctx.exception), "SerpApi returned an API error")

    def test_serpapi_failure_falls_back_to_free_duckduckgo_api(self):
        configs.config.update({
            "WEB_SEARCH_PROVIDER": "serpapi",
            "SERPAPI_API_KEY": "fixture-key",
        })
        serp_response = Mock()
        serp_response.raise_for_status.side_effect = requests.HTTPError("serpapi fixture failure")
        ddg_response = Mock()
        ddg_response.raise_for_status.return_value = None
        ddg_response.json.return_value = {
            "Heading": "Free fallback",
            "AbstractText": "Fallback snippet",
            "AbstractURL": "https://fallback.example",
            "RelatedTopics": [],
        }
        with patch("tools.web_search.requests.get", side_effect=[serp_response, ddg_response]) as get:
            result = web_search.search("fixture", max_results=3)
        self.assertEqual(result.provider, "duckduckgo")
        self.assertEqual(result.results[0].url, "https://fallback.example")
        self.assertEqual(get.call_count, 2)

    def test_missing_serpapi_key_uses_free_duckduckgo_fallback(self):
        configs.config.update({"WEB_SEARCH_PROVIDER": "serpapi", "SERPAPI_API_KEY": ""})
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "Heading": "Free fallback",
            "AbstractText": "Fallback snippet",
            "AbstractURL": "https://fallback.example",
            "RelatedTopics": [],
        }
        with patch("tools.web_search.requests.get", return_value=response):
            result = web_search.search("fixture")
        self.assertEqual(result.provider, "duckduckgo")

    def test_empty_query_is_rejected_without_network(self):
        with patch("tools.web_search.requests.get") as get:
            with self.assertRaises(ValueError):
                web_search.search("  ")
        get.assert_not_called()

    def test_async_facade_offloads_search(self):
        expected = web_search.SearchResponse("fixture", (), "duckduckgo", 1)
        async def run():
            with patch("tools.web_search.search", return_value=expected) as search:
                result = await web_search.asearch("fixture")
            search.assert_called_once_with("fixture", None)
            return result
        self.assertIs(asyncio.run(run()), expected)

    def test_duckduckgo_failure_falls_back_to_qihoo360(self):
        ddg_error = requests.exceptions.ProxyError("fixture proxy unavailable")
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = """
        <ul><li class='res-list'><h3 class='res-title'><a data-mdurl='https://example.com'>Fixture title</a></h3>
        <p class='res-desc'>Fixture snippet</p><cite>example.com</cite></li></ul>
        """
        with patch.dict(configs.config, {"WEB_SEARCH_PROVIDER": "duckduckgo"}, clear=False), \
                patch.object(configs, "proxies", {"http": "http://127.0.0.1:5876", "https": "http://127.0.0.1:5876"}), \
                patch("tools.web_search.requests.get", side_effect=[ddg_error, ddg_error, response]) as get:
            result = web_search.search("fixture")
        self.assertEqual(result.provider, "qihoo360")
        self.assertEqual(result.results[0].url, "https://example.com")
        self.assertEqual(get.call_count, 3)
        self.assertIsNone(get.call_args_list[1].kwargs["proxies"])

    def test_qihoo_mobile_result_markup_is_normalized(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = """
        <div class='r-results'>
          <div class='res-list g-card'>
            <h3 class='res-title'><a data-mdurl='https://mobile.example'>Mobile title</a></h3>
            <div class='summary'>Mobile snippet</div>
            <div class='res-supplement'>mobile.example</div>
          </div>
        </div>
        """
        with patch.dict(configs.config, {"WEB_SEARCH_PROVIDER": "qihoo360"}, clear=False), \
                patch("tools.web_search.requests.get", return_value=response):
            result = web_search.search("fixture")
        self.assertEqual(result.provider, "qihoo360")
        self.assertEqual(result.results[0].title, "Mobile title")
        self.assertEqual(result.results[0].snippet, "Mobile snippet")


if __name__ == "__main__":
    unittest.main()
