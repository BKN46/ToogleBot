import os
import sys
import unittest
from unittest.mock import patch

from tools.napcat_dual_account_check import (
    VerificationError,
    build_settings,
    find_new_reply,
    message_text,
    parse_args,
    probe_endpoint,
)


MAIN_ACCOUNT = 10001
SENDER_ACCOUNT = 10002
TEST_GROUP = 10003


class NapCatDualAccountCheckTest(unittest.TestCase):
    def build_args(self, scenario="active"):
        with patch.object(
            sys,
            "argv",
            ["napcat_dual_account_check.py", "--scenario", scenario],
        ):
            return parse_args()

    def test_settings_are_loaded_from_environment(self):
        environment = {
            "NAPCAT_MAIN_ACCOUNT": str(MAIN_ACCOUNT),
            "NAPCAT_SENDER_ACCOUNT": str(SENDER_ACCOUNT),
            "NAPCAT_TEST_GROUP": str(TEST_GROUP),
            "NAPCAT_ACTIVE_PROBE_TRIGGER": "active probe",
            "NAPCAT_ACTIVE_PROBE_EXPECT": '["active reply"]',
            "NAPCAT_MAIN_HTTP_TOKEN": "main-secret",
            "NAPCAT_SENDER_HTTP_TOKEN": "sender-secret",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = build_settings(self.build_args())
        self.assertEqual(settings.main_account, MAIN_ACCOUNT)
        self.assertEqual(settings.sender_account, SENDER_ACCOUNT)
        self.assertEqual(settings.group_id, TEST_GROUP)
        self.assertEqual(settings.trigger_message, "active probe")
        self.assertEqual(settings.expected_reply_parts, ("active reply",))
        self.assertEqual(settings.main_token, "main-secret")
        self.assertEqual(settings.sender_token, "sender-secret")

    def test_settings_require_distinct_configured_accounts(self):
        environment = {
            "NAPCAT_MAIN_ACCOUNT": str(MAIN_ACCOUNT),
            "NAPCAT_SENDER_ACCOUNT": str(MAIN_ACCOUNT),
            "NAPCAT_TEST_GROUP": str(TEST_GROUP),
            "NAPCAT_ACTIVE_PROBE_TRIGGER": "active probe",
            "NAPCAT_ACTIVE_PROBE_EXPECT": "active reply",
        }
        with patch.dict(os.environ, environment, clear=True), self.assertRaisesRegex(
            VerificationError, "must be different"
        ):
            build_settings(self.build_args())

    def test_message_text_reads_onebot_segments(self):
        message = {
            "message": [
                {"type": "text", "data": {"text": "active"}},
                {"type": "at", "data": {"qq": "123"}},
                {"type": "text", "data": {"text": " reply"}},
            ]
        }
        self.assertEqual(message_text(message), "active reply")

    def test_find_new_reply_rejects_baseline_and_sender_messages(self):
        old_reply = {
            "user_id": MAIN_ACCOUNT,
            "message_id": 1,
            "message": "active reply",
        }
        sender_message = {
            "user_id": SENDER_ACCOUNT,
            "message_id": 2,
            "message": "active reply",
        }
        new_reply = {
            "user_id": MAIN_ACCOUNT,
            "message_id": 3,
            "message": "active reply",
        }
        self.assertIs(
            find_new_reply(
                [old_reply, sender_message, new_reply],
                {(str(MAIN_ACCOUNT), "1")},
                MAIN_ACCOUNT,
                ("active", "reply"),
            ),
            new_reply,
        )

    @patch("tools.napcat_dual_account_check.request_action")
    def test_probe_requires_expected_account_and_group(self, request_action):
        request_action.side_effect = [
            {
                "status": "ok",
                "retcode": 0,
                "data": {"online": True, "good": True},
            },
            {
                "status": "ok",
                "retcode": 0,
                "data": {"user_id": MAIN_ACCOUNT},
            },
            {
                "status": "ok",
                "retcode": 0,
                "data": {"group_id": TEST_GROUP},
            },
        ]
        login = probe_endpoint(
            "main",
            "http://127.0.0.1:6543",
            "secret",
            MAIN_ACCOUNT,
            TEST_GROUP,
            5,
        )
        self.assertEqual(login["user_id"], MAIN_ACCOUNT)
        self.assertEqual(
            [call.args[2] for call in request_action.call_args_list],
            ["get_status", "get_login_info", "get_group_info"],
        )

    @patch("tools.napcat_dual_account_check.request_action")
    def test_probe_rejects_wrong_account_before_group_check(self, request_action):
        request_action.side_effect = [
            {
                "status": "ok",
                "retcode": 0,
                "data": {"online": True, "good": True},
            },
            {
                "status": "ok",
                "retcode": 0,
                "data": {"user_id": 99999},
            },
        ]
        with self.assertRaisesRegex(VerificationError, "account mismatch"):
            probe_endpoint(
                "sender",
                "http://127.0.0.1:6544",
                "",
                SENDER_ACCOUNT,
                TEST_GROUP,
                5,
            )


if __name__ == "__main__":
    unittest.main()
