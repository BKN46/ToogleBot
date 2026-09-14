import unittest
from unittest.mock import Mock, patch

import requests

from plugins.others.weibo import WeiboAuthenticationError, get_web_page, parse_jsonp


class WeiboTest(unittest.TestCase):
    def test_parse_jsonp_requires_expected_callback(self):
        payload = parse_jsonp(
            'callback && callback({"data":{"tid":"fixture"}});',
            "callback && callback(",
        )
        self.assertEqual(payload["data"]["tid"], "fixture")
        with self.assertRaisesRegex(ValueError, "unexpected JSONP"):
            parse_jsonp('other({"data":{}});', "callback(")

    def test_timeline_login_redirect_is_an_authentication_error(self):
        response = Mock()
        response.url = "https://login.sina.com.cn/sso/login.php"
        response.status_code = 200
        response.headers = {"content-type": "text/html"}

        with patch("plugins.others.weibo.get_cookie", return_value=("sub", "subp")), patch(
            "plugins.others.weibo.requests.get", return_value=response
        ):
            with self.assertRaises(WeiboAuthenticationError):
                get_web_page(1855501681)

    def test_timeline_non_login_json_decode_error_is_preserved(self):
        response = Mock()
        response.url = "https://weibo.com/ajax/statuses/mymblog"
        response.status_code = 200
        response.headers = {"content-type": "application/json"}
        response.json.side_effect = requests.exceptions.JSONDecodeError("bad json", "x", 0)

        with patch("plugins.others.weibo.get_cookie", return_value=("sub", "subp")), patch(
            "plugins.others.weibo.requests.get", return_value=response
        ):
            with self.assertRaises(requests.exceptions.JSONDecodeError):
                get_web_page(1855501681)


if __name__ == "__main__":
    unittest.main()
