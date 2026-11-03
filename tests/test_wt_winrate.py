import io
import datetime
import json
import tempfile
import threading
import unittest
from contextlib import chdir
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from PIL import Image as PILImage

from plugins import wt
from plugins.thunderskill import get_winrate as winrate
from toogle.message import Group, Image, Member, MessageChain
from toogle.message_handler import MessagePack


FIXTURE = Path(__file__).parent / "fixtures" / "wt_winrate.csv"


def response(raw):
    result = Mock()
    result.iter_content.side_effect = lambda *args: iter([raw.encode("utf-8")])
    return result


class WinRateDataTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.cache = Path(self.tempdir.name)
        self.path_patch = patch.object(winrate, "save_path", self.cache)
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)
        self.raw = FIXTURE.read_text(encoding="utf-8")
        self.metadata = response(json.dumps([{"date": "2026-10-25"}, {"date": "2026-10-26"}]))
        self.data = response(self.raw)

    def test_fetches_upstream_with_timeout_and_reuses_valid_cache(self):
        old_cache = self.cache / "wt_winrate_n_2026-10-25"
        old_cache.write_text("existing data", encoding="utf-8")
        with patch.object(winrate.requests, "get", side_effect=[self.metadata, self.data, self.metadata]) as get:
            first = winrate.get_winrate_n()
            second = winrate.get_winrate_n()
        self.assertEqual(first, (self.raw, "2026-10-26"))
        self.assertEqual(first, second)
        self.assertEqual(get.call_count, 3)
        self.assertEqual(get.call_args_list[1].args, (winrate.SOURCE_ROOTS[0] + "/rb_ranks_1.csv",))
        for request in get.call_args_list:
            self.assertTrue(request.args[0].startswith(winrate.SOURCE_ROOTS[0]))
            self.assertEqual(request.kwargs["timeout"], (5, 15))
            self.assertTrue(request.kwargs["stream"])
        self.metadata.raise_for_status.assert_called()
        self.data.raise_for_status.assert_called_once()
        self.assertEqual(old_cache.read_text(encoding="utf-8"), "existing data")
        self.assertFalse(list(self.cache.glob("*.tmp")))

    def test_bad_response_does_not_replace_existing_cache(self):
        path = self.cache / "wt_winrate_n_2026-10-26"
        path.write_text("bad cache", encoding="utf-8")
        for data in (response("<html>error</html>"), response(self.raw.replace("2026-10-26", "2026-10-25"))):
            with self.subTest(data=data), patch.object(winrate.requests, "get", side_effect=[self.metadata] + [data] * len(winrate.SOURCE_ROOTS)):
                with self.assertRaises(winrate.WinRateDataError):
                    winrate.get_winrate_n()
            self.assertEqual(path.read_text(encoding="utf-8"), "bad cache")
        with patch.object(winrate.requests, "get", side_effect=[self.metadata, self.data]):
            self.assertEqual(winrate.get_winrate_n()[0], self.raw)

    def test_http_errors_and_invalid_metadata_are_reported(self):
        self.data.raise_for_status.side_effect = requests.HTTPError("503")
        with patch.object(winrate.requests, "get", side_effect=[self.metadata] + [self.data] * len(winrate.SOURCE_ROOTS)):
            with self.assertRaises(winrate.WinRateDataError):
                winrate.get_winrate_n()
        self.assertFalse(list(self.cache.iterdir()))
        for metadata in ([], {}, [{"date": "../../invalid"}]):
            with self.subTest(metadata=metadata), patch.object(winrate.requests, "get", return_value=response(json.dumps(metadata))):
                with self.assertRaises(winrate.WinRateDataError):
                    winrate.get_winrate_n()

    def test_mirror_timeout_and_error_page_fall_back_to_direct_source(self):
        bad_page = response("<html>proxy error</html>")
        with patch.object(winrate.requests, "get", side_effect=[
            requests.ReadTimeout(), bad_page, self.metadata,
            bad_page, requests.ConnectionError(), self.data,
        ]) as get:
            self.assertEqual(winrate.get_winrate_n(), (self.raw, "2026-10-26"))
        self.assertEqual(get.call_count, 6)
        self.assertEqual(get.call_args_list[2].args[0], winrate.SOURCE_ROOT + "/metadata.json")
        self.assertEqual(get.call_args_list[5].args[0], winrate.full_data_url)
        bad_page.close.assert_called()
        self.data.close.assert_called_once()

    def test_recent_cache_is_used_offline_but_old_or_invalid_cache_is_rejected(self):
        today = datetime.date.today()
        recent = (today - datetime.timedelta(days=1)).isoformat()
        old = (today - datetime.timedelta(days=8)).isoformat()
        recent_raw = self.raw.replace("2026-10-26", recent)
        recent_path = self.cache / f"wt_winrate_n_{recent}"
        recent_path.write_text(recent_raw, encoding="utf-8")
        (self.cache / f"wt_winrate_n_{old}").write_text(self.raw.replace("2026-10-26", old), encoding="utf-8")
        with patch.object(winrate.requests, "get", side_effect=requests.ReadTimeout()):
            self.assertEqual(winrate.get_winrate_n(), (recent_raw, recent))
            recent_path.write_text("invalid CSV", encoding="utf-8")
            with self.assertRaises(winrate.WinRateDataError):
                winrate.get_winrate_n()

    def test_slow_and_oversized_downloads_close_response_and_try_next_source(self):
        for limit in ("DOWNLOAD_DEADLINE_SECONDS", "MAX_DOWNLOAD_BYTES"):
            with self.subTest(limit=limit), patch.object(winrate, limit, -1), patch.object(
                winrate.requests, "get", return_value=self.data
            ) as get:
                with self.assertRaises(winrate.WinRateDataError):
                    winrate._fetch_text("rb_ranks_1.csv", lambda raw: None)
            self.assertEqual(get.call_count, len(winrate.SOURCE_ROOTS))
        self.assertEqual(self.data.close.call_count, 2 * len(winrate.SOURCE_ROOTS))

    def test_parser_selects_latest_ground_rows_and_rejects_invalid_values(self):
        result = winrate._parse_winrate_n(self.raw, "2026-10-26")
        self.assertEqual(result["Germany"]["1.0"], {"num": "734.0", "wr": "55.69"})
        self.assertEqual(result["USA"]["1.0"]["wr"], "48.25")
        self.assertEqual(len(result["Germany"]), 2)
        for value in ("nan", "inf", "101", ""):
            with self.subTest(value=value), self.assertRaises(winrate.WinRateDataError):
                winrate._parse_winrate_n(self.raw.replace("55.69", value), "2026-10-26")

    def test_fixture_renders_image_from_any_working_directory(self):
        with chdir(self.tempdir.name), patch.object(winrate, "get_winrate_n", return_value=(self.raw, "2026-10-26")):
            image_bytes = winrate.draw_winrate_n()
        with PILImage.open(io.BytesIO(image_bytes)) as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.size, (470, 210))
            self.assertGreater(len(image.getcolors(image.width * image.height)), 1)
        self.assertTrue(Path(winrate.font_path).is_absolute())
        self.assertTrue(winrate.save_path.is_absolute())


class WinRatePluginTest(unittest.IsolatedAsyncioTestCase):
    async def test_group_and_private_commands_offload_work_and_report_failure(self):
        event_loop_thread = threading.get_ident()
        for message_type, command in (("group", "战雷胜率"), ("private", ".wtwr")):
            message = MessagePack(
                id=1, message=MessageChain.plain(command),
                group=Group(100 if message_type == "group" else 0, "fixture"),
                member=Member(200, "tester"), quote=None, message_type=message_type,
            )
            plugin = wt.WTWinRate()
            self.assertTrue(plugin.is_trigger(message))

            def render():
                self.assertNotEqual(threading.get_ident(), event_loop_thread)
                return b"fixture image"

            with patch.object(wt, "draw_winrate_n", side_effect=render):
                result = await plugin.ret(message)
            self.assertEqual(result.get(Image)[0].getBytes(), b"fixture image")
            for error in (requests.ConnectTimeout(), winrate.WinRateDataError("bad CSV")):
                with patch.object(wt, "draw_winrate_n", side_effect=error), patch.object(wt.logger, "exception"):
                    result = await plugin.ret(message)
                self.assertIn("数据源暂时不可用", result.asDisplay())
                self.assertTrue(result.no_charge)
                self.assertTrue(result.no_interval)


if __name__ == "__main__":
    unittest.main()
