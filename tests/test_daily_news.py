import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import requests

import plugins.daily_news as plugin
import plugins.daily_news as news
import toogle.scheduler as scheduler
from toogle.message import Group, Member, MessageChain
from toogle.message_handler import MessagePack


TZ = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 9, 17, 10, 2, tzinfo=TZ)
RSS = b'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Fixture News</title>
<item><title>Start boundary</title><link>https://example.com/start</link>
<pubDate>Wed, 16 Sep 2026 10:00:00 +0800</pubDate></item>
<item><title>UTC story</title><link>https://example.com/utc</link>
<pubDate>Thu, 17 Sep 2026 01:59:59 GMT</pubDate></item>
<item><title>Too old</title><link>https://example.com/old</link>
<pubDate>Wed, 16 Sep 2026 09:59:59 +0800</pubDate></item>
<item><title>Next window</title><link>https://example.com/next</link>
<pubDate>Thu, 17 Sep 2026 10:00:00 +0800</pubDate></item>
<item><title>No date</title><link>https://example.com/unknown</link></item>
<item><title>No timezone</title><link>https://example.com/naive</link>
<pubDate>Thu, 17 Sep 2026 09:00:00</pubDate></item>
<item><title>Unsafe link</title><link>javascript:alert(1)</link>
<pubDate>Thu, 17 Sep 2026 09:00:00 +0800</pubDate></item>
</channel></rss>'''


class NewsTest(unittest.TestCase):
    def setUp(self):
        def select(text, **kwargs):
            payload = json.loads(text)
            return json.dumps({"items": [
                {"id": item["id"], "summary": "Fixture summary"}
                for item in payload["candidates"][:payload["count"]]
            ]})
        self.ai_patch = patch.object(news.LLMAdapter, "chat", side_effect=select)
        self.ai = self.ai_patch.start()
        self.addCleanup(self.ai_patch.stop)

    def test_manual_query_before_ten_uses_recent_news_not_previous_edition(self):
        now = NOW.replace(hour=9)
        with patch.object(news, "fetch_rss", return_value=news.parse_rss(RSS)):
            digest = news.build_digest(["https://example.com/rss"], 15, now)
        self.assertIn("Start boundary", digest)
        self.assertNotIn("UTC story", digest)
        self.assertNotIn("https://", digest)

    def test_window_is_past_24_hours_including_delayed_runs(self):
        start, end = news.news_window(NOW)
        self.assertEqual(start, datetime(2026, 9, 16, 10, 2, tzinfo=TZ))
        self.assertEqual(end, NOW)
        self.assertEqual(news.news_window(NOW.replace(hour=9))[1], NOW.replace(hour=9))

    def test_rss_dates_boundaries_and_deduplication(self):
        items = news.parse_rss(RSS)
        self.assertEqual(len(items), 4)
        with patch.object(news, "fetch_rss", return_value=items):
            digest = news.build_digest(["https://example.com/a", "https://example.com/b"], 15, NOW.replace(minute=0))
        self.assertIn("Start boundary", digest)
        self.assertIn("UTC story", digest)
        self.assertNotIn("Too old", digest)
        self.assertNotIn("Next window", digest)
        self.assertEqual(digest.count("UTC story"), 1)
        self.assertNotIn("Fixture News", digest)
        self.assertNotIn("https://", digest)

    def test_sections_share_limit(self):
        items = news.parse_rss(RSS)
        other = news.NewsItem("Other section", "https://example.com/other", NOW.replace(hour=8), "Other")
        with patch.object(news, "fetch_rss", side_effect=[items, [other]]):
            digest = news.build_digest(["https://example.com/a", "https://example.com/b"], 2, NOW)
        self.assertIn("Other section", digest)
        self.assertNotIn("Start boundary", digest)

    def test_partial_total_and_stale_source_failures(self):
        urls = ["https://example.com/a", "https://example.com/b"]
        with patch.object(news, "fetch_rss", side_effect=[requests.Timeout(), news.parse_rss(RSS)]):
            digest = news.build_digest(urls, 15, NOW)
            self.assertIn("Fixture summary", digest)
            self.assertNotIn("部分新闻源", digest)
        with patch.object(news, "fetch_rss", side_effect=requests.Timeout()):
            with self.assertRaisesRegex(RuntimeError, "all daily news"):
                news.build_digest(urls, 15, NOW)
        with patch.object(news, "fetch_rss", return_value=news.parse_rss(RSS)):
            self.assertIsNone(news.build_digest(urls, 15, NOW.replace(day=19)))

    def test_invalid_feed_is_not_silent_success(self):
        with self.assertRaises(ValueError):
            news.parse_rss(b"<html><body>Login required</body></html>")

    def test_rss_description_is_plain_text(self):
        fixture = RSS.replace(b"</item>", b"<description><![CDATA[<p>Fact &amp; detail</p><script>bad()</script>]]></description></item>", 1)
        self.assertEqual(news.parse_rss(fixture)[0].description, "Fact & detail")

    def test_ai_selects_from_all_candidates_and_controls_order(self):
        items = [news.NewsItem(f"Title {i}", f"https://example.com/{i}", NOW,
                               "Fixture News", f"Fact {i}") for i in range(20)]
        self.ai.side_effect = None
        self.ai.return_value = json.dumps({"items": [
            {"id": i, "summary": f"Summary {i}"} for i in range(19, 4, -1)
        ]})
        digest = news.select_news(items, 15)
        sent = json.loads(self.ai.call_args.args[0])
        self.assertEqual(len(sent["candidates"]), 20)
        self.assertEqual(sent["candidates"][19]["description"], "Fact 19")
        self.assertTrue(digest.startswith("1. Title 19\nSummary 19"))
        self.assertEqual(len(digest.split("\n\n")), 15)
        self.assertNotIn("https://", digest)
        self.assertNotIn("Fixture News", digest)
        self.assertNotIn("Title 0\n", digest)

    def test_invalid_ai_output_is_rejected_without_fallback(self):
        items = news.parse_rss(RSS)
        self.ai.side_effect = None
        for output in ["not json", "[]", '{"items":null}',
                       json.dumps({"items": [{"id": 999, "summary": "text"}]}),
                       json.dumps({"items": [{"id": True, "summary": "text"}]}),
                       json.dumps({"items": [{"id": 0, "summary": ""}]}),
                       json.dumps({"items": [{"id": 0, "summary": "https://example.com"}]})]:
            with self.subTest(output=output):
                self.ai.return_value = output
                with self.assertRaises(ValueError):
                    news.select_news(items, 1)
        self.ai.return_value = json.dumps({"items": [{"id": 0, "summary": "text"}] * 2})
        self.assertEqual(news.select_news(items, 2), "1. Start boundary\ntext")

    def test_numeric_string_ids_and_duplicates_keep_valid_news_in_order(self):
        self.ai.side_effect = None
        self.ai.return_value = json.dumps({"items": [
            {"id": " 1 ", "summary": "first"},
            {"id": 1, "summary": "duplicate"},
            {"id": "0", "summary": "second"},
        ]})
        result = news.select_news(news.parse_rss(RSS), 3)
        self.assertEqual(result, "1. UTC story\nfirst\n\n2. Start boundary\nsecond")

    def test_empty_window_does_not_call_ai(self):
        with patch.object(news, "fetch_rss", return_value=news.parse_rss(RSS)):
            self.assertIsNone(news.build_digest(["https://example.com/rss"], 15, NOW.replace(day=19)))
        self.ai.assert_not_called()

    def test_selection_may_drop_all_or_some_candidates_instead_of_filling_quota(self):
        items = news.parse_rss(RSS)
        self.ai.side_effect = None
        self.ai.return_value = '{"items":[]}'
        self.assertIsNone(news.select_news(items, 15))
        self.ai.return_value = '{"items":[{"id":0,"summary":"Concrete change"}]}'
        result = news.select_news(items, 15)
        self.assertEqual(result, "1. Start boundary\nConcrete change")
        prompt = self.ai.call_args.kwargs["settings"]
        for criterion in ["官话宣传", "学习贯彻", "就业工资", "医疗医保", "不要因为出现政府", "不足count条就少选"]:
            self.assertIn(criterion, prompt)

    def test_deepseek_request_is_direct_fast_and_bounded(self):
        self.ai_patch.stop()
        response = Mock()
        response.json.return_value = {"choices": [{"message": {"content": '{"items":[]}'}}]}
        items = [news.NewsItem(f"Title {i}", f"https://example.com/{i}", NOW,
                               "Source", "x" * 600) for i in range(150)]
        with patch.dict(plugin.config, {"GPTSecretDeepseek": "fixture-key",
                                       "NEWS_AI_MODEL": "deepseek-flash",
                                       "NEWS_AI_TIMEOUT_SECONDS": "45", "NEWS_AI_USE_PROXY": "0"}), \
                patch("toogle.llm_adapter.requests.post", return_value=response) as post:
            self.assertIsNone(news.select_news(items, 15))
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["proxies"], {"http": "", "https": ""})
        self.assertEqual(kwargs["timeout"], 45)
        self.assertEqual(kwargs["json"]["model"], "deepseek-flash")
        self.assertEqual(kwargs["json"]["thinking"], {"type": "disabled"})
        payload = json.loads(kwargs["json"]["messages"][-1]["content"])
        self.assertEqual(len(payload["candidates"]), 80)
        self.assertEqual(len(payload["candidates"][0]["description"]), 240)

    def test_ai_timeout_and_invalid_result_are_distinguished(self):
        with patch.object(news, "fetch_rss", return_value=news.parse_rss(RSS)):
            self.ai.side_effect = requests.ReadTimeout("fixture")
            with self.assertRaisesRegex(news.NewsAIError, "AI新闻筛选超时"):
                news.build_digest(["https://example.com/rss"], 15, NOW)
            self.ai.side_effect = None
            self.ai.return_value = "bad json"
            with self.assertRaisesRegex(news.NewsAIError, "AI新闻筛选结果不可用"):
                news.build_digest(["https://example.com/rss"], 15, NOW)


class DailyNewsScheduleTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        cache_patch = patch.object(news, "NEWS_CACHE_PATH", Path(temporary.name) / "daily_news.json")
        cache_patch.start()
        self.addCleanup(cache_patch.stop)
        clock_patch = patch.object(news, "news_now", return_value=NOW)
        clock_patch.start()
        self.addCleanup(clock_patch.stop)

    async def test_manual_trigger_uses_registry_and_worker_in_group_and_private(self):
        import toogle.index as registry
        from adapter import worker
        from toogle import adapter

        built = registry._RegistryBuild()
        report = registry.PluginLoadReport()
        with patch.dict(plugin.config, {"DISABLED_MODULE": []}):
            registry._collect_module_plugins(plugin, built, report, set())
        self.assertFalse(report.failed)
        self.assertEqual(len(built.normal), 1)
        self.assertEqual(len(built.scheduled), 2)
        self.assertFalse(plugin.DailyNews().is_trigger("昨天的每日新闻"))
        self.assertFalse(plugin.DailyNews().is_trigger(".news extra"))

        for message_type, command in [("group", "每日新闻"), ("private", ".news")]:
            news.NEWS_CACHE_PATH.unlink(missing_ok=True)
            source = MessagePack(
                id=1, message=MessageChain.plain(command),
                group=Group(123, "fixture"), member=Member(456, "fixture"),
                quote=None, message_type=message_type,
            )
            with patch.dict(plugin.config, {"CHAT_GROUP_LIST": [], "ONLY_READ": [],
                                           "BLACK_LIST": [], "ADMIN_LIST": []}), \
                    patch.object(worker, "get_export_plugins", return_value=built.normal), \
                    patch.object(adapter, "get_block", return_value=False), \
                    patch.object(adapter, "is_traffic_free", return_value=True), \
                    patch.object(adapter, "print_call"), \
                    patch.object(plugin, "build_digest", return_value="manual fixture") as fetch, \
                    patch.object(plugin, "bot_send_message") as broadcast, \
                    patch.object(adapter, "bot_send_message", return_value=True) as reply:
                await worker.process_message(source, 0)
                self.assertIsNotNone(fetch.call_args.args[2].tzinfo)
                broadcast.assert_not_called()
                reply.assert_called_once()
                self.assertEqual(reply.call_args.args[0].message_type, message_type)
                self.assertIn("manual fixture", reply.call_args.args[1].asDisplay())

    async def test_manual_empty_and_failure_return_visible_free_response(self):
        source = MessagePack(id=1, message=MessageChain.plain("每日新闻"),
                             group=Group(123, "fixture"), member=Member(456, "fixture"),
                             quote=None, message_type="group")
        for result, expected in [(None, "暂无符合筛选标准"), (RuntimeError("secret error"), "新闻源获取失败"),
                                 (news.NewsAIError("AI新闻筛选超时，请稍后重试。"), "AI新闻筛选超时")]:
            kwargs = {"side_effect": result} if isinstance(result, Exception) else {"return_value": result}
            with patch.object(plugin, "build_digest", **kwargs), \
                    patch.object(plugin, "bot_send_message") as send:
                response = await plugin.DailyNews().ret(source)
                send.assert_not_called()
                self.assertIn(expected, response.asDisplay())
                self.assertNotIn("secret error", response.asDisplay())
                self.assertTrue(response.no_charge)
                self.assertTrue(response.no_interval)

    async def test_daily_cron_and_idempotent_registration(self):
        module = plugin.DailyNews()
        try:
            module.register()
            job = module.register()
            self.assertEqual(str(job.trigger), "cron[hour='10', minute='0', second='0']")
            next_run = job.trigger.get_next_fire_time(None, NOW.astimezone(scheduler.SCHEDULER_TIMEZONE))
            self.assertEqual(next_run.hour, 10)
            self.assertEqual(sum(j.id == module.job_id for j in scheduler.native_scheduler.get_jobs()), 1)
        finally:
            scheduler.native_scheduler.remove_job(module.job_id)

    async def test_groups_receive_once_and_io_runs_off_loop(self):
        import threading
        loop_thread = threading.get_ident()

        def build(*args):
            self.assertNotEqual(threading.get_ident(), loop_thread)
            return "fixture digest"

        with patch.dict(plugin.config, {"CHAT_GROUP_LIST": [123, "123", 456]}), \
                patch.object(plugin, "build_digest", side_effect=build) as fetch, \
                patch.object(plugin, "bot_send_message", return_value=True) as send:
            await plugin.DailyNews().ret(None)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual([call.args[0] for call in send.call_args_list], [123, 456])
        self.assertIn("生成时间：2026-09-17 10:02:00", send.call_args.args[1].asDisplay())
        self.assertTrue(send.call_args.args[1].asDisplay().endswith("fixture digest"))

    async def test_empty_groups_and_no_news_do_not_send(self):
        with patch.dict(plugin.config, {"CHAT_GROUP_LIST": []}), \
                patch.object(plugin, "build_digest") as fetch:
            await plugin.DailyNews().ret(None)
            fetch.assert_not_called()
        with patch.dict(plugin.config, {"CHAT_GROUP_LIST": [123]}), \
                patch.object(plugin, "build_digest", return_value=None), \
                patch.object(plugin, "bot_send_message") as send:
            await plugin.DailyNews().ret(None)
            send.assert_not_called()

    async def test_send_failure_does_not_skip_other_groups(self):
        with patch.dict(plugin.config, {"CHAT_GROUP_LIST": [123, 456]}), \
                patch.object(plugin, "build_digest", return_value="fixture"), \
                patch.object(plugin, "bot_send_message", side_effect=[False, True]) as send:
            with self.assertRaisesRegex(RuntimeError, "1 groups"):
                await plugin.DailyNews().ret(None)
            self.assertEqual(send.call_count, 2)


class DailyNewsCacheTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        cache_patch = patch.object(news, "NEWS_CACHE_PATH", Path(temporary.name) / "daily_news.json")
        cache_patch.start()
        self.addCleanup(cache_patch.stop)
        clock_patch = patch.object(news, "news_now", return_value=NOW)
        self.clock = clock_patch.start()
        self.addCleanup(clock_patch.stop)

    def test_same_day_concurrent_calls_generate_once_and_reuse_disk(self):
        with patch.object(news, "build_digest", return_value="1. Title\nSummary") as build:
            with ThreadPoolExecutor(max_workers=8) as pool:
                outputs = list(pool.map(lambda _: news.get_daily_digest(), range(8)))
            build.assert_called_once()
        self.assertEqual(len(set(outputs)), 1)
        self.assertIn("生成时间：2026-09-17 10:02:00", outputs[0])
        self.clock.return_value = NOW.replace(hour=20)
        with patch.object(news, "build_digest", side_effect=AssertionError("must use disk cache")):
            self.assertEqual(news.get_daily_digest(), outputs[0])

    def test_next_day_cleanup_and_regeneration(self):
        with patch.object(news, "build_digest", return_value="old"):
            news.get_daily_digest()
        self.clock.return_value = NOW.replace(day=18, hour=0, minute=0)
        news.clear_expired_news_cache()
        self.assertFalse(news.NEWS_CACHE_PATH.exists())
        with patch.object(news, "build_digest", return_value="new") as build:
            result = news.get_daily_digest()
            build.assert_called_once()
        self.assertIn("2026-09-18 00:00:00", result)
        self.assertTrue(result.endswith("new"))

    def test_request_expires_cache_even_if_midnight_job_was_missed(self):
        with patch.object(news, "build_digest", return_value="old"):
            news.get_daily_digest()
        self.clock.return_value = NOW.replace(day=18)
        with patch.object(news, "build_digest", return_value="new") as build:
            self.assertTrue(news.get_daily_digest().endswith("new"))
            build.assert_called_once()

    def test_errors_and_empty_results_are_not_cached(self):
        with patch.object(news, "build_digest", side_effect=news.NewsAIError("failure")):
            with self.assertRaises(news.NewsAIError):
                news.get_daily_digest()
        self.assertFalse(news.NEWS_CACHE_PATH.exists())
        with patch.object(news, "build_digest", return_value=None):
            self.assertIsNone(news.get_daily_digest())
        self.assertFalse(news.NEWS_CACHE_PATH.exists())

    def test_generation_crossing_midnight_belongs_to_completion_day(self):
        self.clock.side_effect = [NOW.replace(hour=23, minute=59), NOW.replace(day=18, hour=0)]
        with patch.object(news, "build_digest", return_value="body"):
            result = news.get_daily_digest()
        self.assertIn("2026-09-18", result)
        self.clock.side_effect = None
        self.clock.return_value = NOW.replace(day=18, hour=1)
        news.clear_expired_news_cache()
        self.assertTrue(news.NEWS_CACHE_PATH.exists())

    def test_corrupt_cache_is_rebuilt_and_midnight_job_only_cleans(self):
        news.NEWS_CACHE_PATH.write_text("invalid", encoding="utf-8")
        with patch.object(news, "build_digest", return_value="body") as build:
            news.get_daily_digest()
            build.assert_called_once()
        with patch.object(news, "build_digest") as build:
            news.clear_expired_news_cache()
            build.assert_not_called()
        module = news.DailyNewsCacheCleanup()
        try:
            job = module.register()
            self.assertEqual(str(job.trigger), "cron[hour='0', minute='0', second='0']")
        finally:
            scheduler.native_scheduler.remove_job(module.job_id)
