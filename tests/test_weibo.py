import unittest

from plugins.others.weibo import parse_jsonp


class WeiboTest(unittest.TestCase):
    def test_parse_jsonp_requires_expected_callback(self):
        payload = parse_jsonp(
            'callback && callback({"data":{"tid":"fixture"}});',
            "callback && callback(",
        )
        self.assertEqual(payload["data"]["tid"], "fixture")
        with self.assertRaisesRegex(ValueError, "unexpected JSONP"):
            parse_jsonp('other({"data":{}});', "callback(")


if __name__ == "__main__":
    unittest.main()
