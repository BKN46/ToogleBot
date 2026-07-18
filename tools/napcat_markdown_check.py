#!/usr/bin/env python3
"""Probe and optionally verify Markdown delivery through configured NapCat."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from adapter.msg_queue import toogle2nb
from toogle.message import Markdown, MessageChain
from tools.napcat_dual_account_check import (
    VerificationError,
    _configured_value,
    _positive_int,
    get_group_history,
    probe_endpoint,
    read_dotenv,
    request_action,
    require_success,
)

DEFAULT_CONTENT = """# ToogleBot Markdown 测试

**粗体** 与 `inline code`

- NapCat
- OneBot 11

> OB11MessageMarkdown"""


def build_markdown_message(content: str) -> list[dict]:
    if not content.strip():
        raise VerificationError("Markdown content must not be empty")
    return toogle2nb(MessageChain([Markdown(content)]))


def history_has_markdown(
    messages: list[dict],
    message_id: str,
    content: str,
) -> bool:
    for message in messages:
        if str(message.get("message_id")) != message_id:
            continue
        segments = message.get("message")
        if not isinstance(segments, list):
            return False
        return any(
            isinstance(segment, dict)
            and segment.get("type") == "markdown"
            and segment.get("data", {}).get("content") == content
            for segment in segments
        )
    return False


def find_new_markdown(
    messages: list[dict],
    baseline_ids: set[str],
    account: int,
    content: str,
) -> str | None:
    for message in messages:
        message_id = str(message.get("message_id", ""))
        if not message_id or message_id in baseline_ids:
            continue
        if str(message.get("user_id")) != str(account):
            continue
        if history_has_markdown([message], message_id, content):
            return message_id
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe or send a Markdown segment to the configured test group."
    )
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--account", type=int)
    parser.add_argument("--observer-account", type=int)
    parser.add_argument("--group-id", type=int)
    parser.add_argument("--base-url")
    parser.add_argument("--observer-base-url")
    parser.add_argument("--content", default=DEFAULT_CONTENT)
    parser.add_argument("--request-timeout", type=float, default=10.0)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument(
        "--confirm-send",
        action="store_true",
        help="send one Markdown message after the read-only checks pass",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dotenv = read_dotenv(Path(args.env_file))
    try:
        account = _positive_int(
            args.account or _configured_value("NAPCAT_MAIN_ACCOUNT", dotenv),
            "NAPCAT_MAIN_ACCOUNT",
        )
        group_id = _positive_int(
            args.group_id or _configured_value("NAPCAT_TEST_GROUP", dotenv),
            "NAPCAT_TEST_GROUP",
        )
        base_url = args.base_url or _configured_value(
            "NAPCAT_MAIN_HTTP_URL",
            dotenv,
            "http://127.0.0.1:6543",
        )
        token = os.getenv("NAPCAT_MAIN_HTTP_TOKEN") or dotenv.get(
            "NAPCAT_MAIN_HTTP_TOKEN",
            dotenv.get("HTTP_TOKEN", ""),
        )
        login = probe_endpoint(
            "main",
            base_url,
            token,
            account,
            group_id,
            args.request_timeout,
        )
        message = build_markdown_message(args.content)
        print(
            "Markdown probe passed: "
            f"account={int(login['user_id'])}, group={group_id}, "
            f"segment_type={message[0]['type']}"
        )
        if not args.confirm_send:
            print("Probe-only mode: no message was sent.")
            return 0

        observer_account = _positive_int(
            args.observer_account
            or _configured_value("NAPCAT_SENDER_ACCOUNT", dotenv),
            "NAPCAT_SENDER_ACCOUNT",
        )
        if observer_account == account:
            raise VerificationError("main and observer accounts must be different")
        observer_base_url = args.observer_base_url or _configured_value(
            "NAPCAT_SENDER_HTTP_URL",
            dotenv,
            "http://127.0.0.1:6544",
        )
        observer_token = _configured_value(
            "NAPCAT_SENDER_HTTP_TOKEN",
            dotenv,
        )
        observer_login = probe_endpoint(
            "observer",
            observer_base_url,
            observer_token,
            observer_account,
            group_id,
            args.request_timeout,
        )
        print(
            "Independent observer passed: "
            f"account={int(observer_login['user_id'])}, group={group_id}"
        )

        before = get_group_history(
            observer_base_url,
            observer_token,
            group_id,
            args.request_timeout,
        )
        baseline_ids = {
            str(item.get("message_id"))
            for item in before
            if item.get("message_id") is not None
        }
        response_error = None
        response_message_id = None
        try:
            send_response = request_action(
                base_url,
                token,
                "send_group_msg",
                {"group_id": group_id, "message": message},
                args.request_timeout,
            )
            data = require_success(send_response, "send_group_msg")
        except VerificationError as exc:
            response_error = exc
        else:
            if isinstance(data, dict) and data.get("message_id") is not None:
                response_message_id = str(data["message_id"])

        deadline = time.monotonic() + args.timeout
        observed_id = None
        while True:
            history = get_group_history(
                observer_base_url,
                observer_token,
                group_id,
                args.request_timeout,
            )
            if response_message_id and history_has_markdown(
                history,
                response_message_id,
                args.content,
            ):
                observed_id = response_message_id
                break
            observed_id = find_new_markdown(
                history,
                baseline_ids,
                account,
                args.content,
            )
            if observed_id:
                break
            if time.monotonic() >= deadline:
                if response_error is not None:
                    raise VerificationError(
                        f"{response_error}; no matching new Markdown segment "
                        "was received by the independent observer"
                    ) from response_error
                raise VerificationError(
                    "the independent observer did not receive the sent message "
                    f"as a Markdown segment within {args.timeout:g} seconds"
                )
            time.sleep(args.interval)
    except VerificationError as exc:
        print(f"Markdown verification failed: {exc}", file=sys.stderr)
        return 1

    suffix = " (action failure independently confirmed by observer)" if response_error else ""
    print(f"Markdown delivery passed: message_id={observed_id}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
