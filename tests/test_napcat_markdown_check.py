import argparse
import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from tools import napcat_markdown_check
from tools.napcat_markdown_check import (
    build_markdown_message,
    find_new_markdown,
    history_has_markdown,
)
from tools.napcat_dual_account_check import VerificationError


class NapCatMarkdownCheckTest(unittest.TestCase):
    def test_build_markdown_message_uses_project_converter(self):
        self.assertEqual(
            build_markdown_message("**fixture**"),
            [
                {
                    "type": "markdown",
                    "data": {"content": "**fixture**"},
                }
            ],
        )

    def test_build_markdown_message_rejects_empty_content(self):
        with self.assertRaises(VerificationError):
            build_markdown_message("  ")

    def test_history_requires_matching_id_type_and_content(self):
        messages = [
            {
                "message_id": 42,
                "message": [
                    {
                        "type": "markdown",
                        "data": {"content": "**fixture**"},
                    }
                ],
            }
        ]

        self.assertTrue(history_has_markdown(messages, "42", "**fixture**"))
        self.assertFalse(history_has_markdown(messages, "43", "**fixture**"))
        self.assertFalse(history_has_markdown(messages, "42", "other"))

    def test_find_new_markdown_checks_baseline_sender_and_content(self):
        messages = [
            {
                "message_id": 42,
                "user_id": 100,
                "message": [
                    {
                        "type": "markdown",
                        "data": {"content": "**fixture**"},
                    }
                ],
            },
            {
                "message_id": 43,
                "user_id": 200,
                "message": [
                    {
                        "type": "markdown",
                        "data": {"content": "**fixture**"},
                    }
                ],
            },
            {
                "message_id": 44,
                "user_id": 100,
                "message": [
                    {
                        "type": "markdown",
                        "data": {"content": "**fixture**"},
                    }
                ],
            },
        ]

        self.assertEqual(
            find_new_markdown(messages, {"42"}, 100, "**fixture**"),
            "44",
        )

    def test_find_new_markdown_needs_message_in_observer_history(self):
        self.assertIsNone(
            find_new_markdown([], set(), 100, "**fixture**"),
        )

    def test_transport_timeout_still_checks_independent_observer(self):
        args = argparse.Namespace(
            env_file=".env",
            account=None,
            observer_account=None,
            group_id=None,
            base_url=None,
            observer_base_url=None,
            content="**fixture**",
            request_timeout=1.0,
            timeout=0.0,
            interval=0.0,
            confirm_send=True,
        )
        dotenv = {
            "NAPCAT_MAIN_ACCOUNT": "100",
            "NAPCAT_SENDER_ACCOUNT": "200",
            "NAPCAT_TEST_GROUP": "300",
        }

        with (
            patch.object(napcat_markdown_check, "parse_args", return_value=args),
            patch.object(
                napcat_markdown_check,
                "read_dotenv",
                return_value=dotenv,
            ),
            patch.object(
                napcat_markdown_check,
                "probe_endpoint",
                side_effect=({"user_id": 100}, {"user_id": 200}),
            ),
            patch.object(
                napcat_markdown_check,
                "get_group_history",
                return_value=[],
            ) as get_history,
            patch.object(
                napcat_markdown_check,
                "request_action",
                side_effect=VerificationError("send_group_msg request failed: timed out"),
            ),
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()) as stderr,
        ):
            result = napcat_markdown_check.main()

        self.assertEqual(result, 1)
        self.assertEqual(get_history.call_count, 2)
        self.assertIn("independent observer", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
