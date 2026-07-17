import os
import sys
import unittest
from unittest.mock import patch

from tools.napcat_login_check import (
    ProbeError,
    build_probe,
    parse_args,
    request_action,
    validate_group_list,
    validate_login_info,
    validate_status,
    validate_test_account,
    wait_for_login,
)

TEST_ACCOUNT = 10001


class NapCatLoginCheckTest(unittest.TestCase):
    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self):
            return self.payload

    def test_requires_positive_test_account(self):
        validate_test_account(TEST_ACCOUNT)
        with self.assertRaisesRegex(ProbeError, "positive integer"):
            validate_test_account(0)

    def test_defaults_to_local_napcat_http_port(self):
        with patch.dict(
            os.environ, {"NAPCAT_TEST_ACCOUNT": str(TEST_ACCOUNT)}, clear=True
        ), patch.object(
            sys, "argv", ["napcat_login_check.py"]
        ):
            args = parse_args()
        self.assertEqual(args.base_url, "http://127.0.0.1:6543")
        self.assertEqual(args.account, TEST_ACCOUNT)

    def test_accepts_expected_online_account(self):
        validate_status(
            {
                "status": "ok",
                "retcode": 0,
                "data": {"online": True, "good": True, "stat": {}},
            }
        )
        login = validate_login_info(
            {
                "status": "ok",
                "retcode": 0,
                    "data": {"user_id": TEST_ACCOUNT, "nickname": "test"},
                },
            TEST_ACCOUNT,
        )
        self.assertEqual(login["user_id"], TEST_ACCOUNT)

    def test_rejects_wrong_account(self):
        with self.assertRaisesRegex(ProbeError, "unexpected login account"):
            validate_login_info(
                {
                    "status": "ok",
                    "retcode": 0,
                    "data": {"user_id": 123456789, "nickname": "wrong"},
                },
                TEST_ACCOUNT,
            )

    def test_rejects_offline_status(self):
        with self.assertRaisesRegex(ProbeError, "not ready"):
            validate_status(
                {
                    "status": "ok",
                    "retcode": 0,
                    "data": {"online": False, "good": False},
                }
            )

    def test_wait_retries_transient_failure(self):
        attempts = iter(
            [
                ProbeError("not ready"),
                {"user_id": TEST_ACCOUNT, "nickname": "test"},
            ]
        )

        def probe():
            result = next(attempts)
            if isinstance(result, ProbeError):
                raise result
            return result

        result = wait_for_login(probe, timeout=1.0, interval=0.0)
        self.assertEqual(result["user_id"], TEST_ACCOUNT)

    def test_group_list_only_requires_a_list(self):
        validate_group_list({"status": "ok", "retcode": 0, "data": []})
        with self.assertRaisesRegex(ProbeError, "invalid data"):
            validate_group_list({"status": "ok", "retcode": 0, "data": {}})

    @patch("tools.napcat_login_check.urllib.request.urlopen")
    def test_http_action_uses_post_and_bearer_token(self, urlopen):
        urlopen.return_value = self.FakeResponse(
            b'{"status":"ok","retcode":0,"data":{}}'
        )
        payload = request_action("http://napcat:3000/", "secret", "/get_status", 5)
        request = urlopen.call_args.args[0]
        self.assertEqual(payload["retcode"], 0)
        self.assertEqual(request.full_url, "http://napcat:3000/get_status")
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")

    @patch("tools.napcat_login_check.request_action")
    def test_probe_checks_status_login_and_optional_groups(self, request):
        request.side_effect = [
            {
                "status": "ok",
                "retcode": 0,
                "data": {"online": True, "good": True},
            },
            {
                "status": "ok",
                "retcode": 0,
                "data": {"user_id": TEST_ACCOUNT, "nickname": "test"},
            },
            {"status": "ok", "retcode": 0, "data": []},
        ]
        probe = build_probe(
            "http://napcat:3000", "secret", TEST_ACCOUNT, 5, True
        )
        self.assertEqual(probe()["user_id"], TEST_ACCOUNT)
        self.assertEqual(
            [call.args[2] for call in request.call_args_list],
            ["get_status", "get_login_info", "get_group_list"],
        )


if __name__ == "__main__":
    unittest.main()
