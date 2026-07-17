#!/usr/bin/env python3
"""Verify ToogleBot with two configured NapCat accounts."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class VerificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ValidationSettings:
    main_account: int
    sender_account: int
    group_id: int
    main_base_url: str
    sender_base_url: str
    main_token: str
    sender_token: str
    trigger_message: str
    expected_reply_parts: tuple[str, ...]
    scenario: str


def read_dotenv(path: Path = Path(".env")) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def _configured_value(
    key: str,
    dotenv: dict[str, str],
    default: str = "",
) -> str:
    return os.getenv(key) or dotenv.get(key) or default


def _positive_int(value: str | int | None, key: str) -> int:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError) as exc:
        raise VerificationError(f"{key} must be a positive integer") from exc
    if parsed <= 0:
        raise VerificationError(f"{key} must be a positive integer")
    return parsed


def _expected_parts(value: str, key: str) -> tuple[str, ...]:
    if not value:
        raise VerificationError(f"{key} is required")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = [value]
    if isinstance(parsed, str):
        parsed = [parsed]
    if not isinstance(parsed, list) or not all(
        isinstance(part, str) and part for part in parsed
    ):
        raise VerificationError(f"{key} must be a string or JSON string list")
    return tuple(parsed)


def build_settings(args: argparse.Namespace) -> ValidationSettings:
    dotenv = read_dotenv(Path(args.env_file))
    main_account = _positive_int(
        args.main_account or _configured_value("NAPCAT_MAIN_ACCOUNT", dotenv),
        "NAPCAT_MAIN_ACCOUNT",
    )
    sender_account = _positive_int(
        args.sender_account or _configured_value("NAPCAT_SENDER_ACCOUNT", dotenv),
        "NAPCAT_SENDER_ACCOUNT",
    )
    group_id = _positive_int(
        args.group_id or _configured_value("NAPCAT_TEST_GROUP", dotenv),
        "NAPCAT_TEST_GROUP",
    )
    if main_account == sender_account:
        raise VerificationError("main and sender accounts must be different")

    prefix = "NAPCAT_ACTIVE_PROBE" if args.scenario == "active" else "NAPCAT_COMMAND_PROBE"
    trigger_message = args.trigger_message or _configured_value(
        f"{prefix}_TRIGGER", dotenv
    )
    if not trigger_message:
        raise VerificationError(f"{prefix}_TRIGGER is required")
    expected_value = (
        json.dumps(args.expect, ensure_ascii=False)
        if args.expect
        else _configured_value(f"{prefix}_EXPECT", dotenv)
    )

    return ValidationSettings(
        main_account=main_account,
        sender_account=sender_account,
        group_id=group_id,
        main_base_url=args.main_base_url
        or _configured_value(
            "NAPCAT_MAIN_HTTP_URL", dotenv, "http://127.0.0.1:6543"
        ),
        sender_base_url=args.sender_base_url
        or _configured_value(
            "NAPCAT_SENDER_HTTP_URL", dotenv, "http://127.0.0.1:6544"
        ),
        main_token=_configured_value(
            "NAPCAT_MAIN_HTTP_TOKEN",
            dotenv,
            dotenv.get("HTTP_TOKEN", ""),
        ),
        sender_token=_configured_value("NAPCAT_SENDER_HTTP_TOKEN", dotenv),
        trigger_message=trigger_message,
        expected_reply_parts=_expected_parts(
            expected_value,
            f"{prefix}_EXPECT",
        ),
        scenario=args.scenario,
    )


def request_action(
    base_url: str,
    token: str,
    action: str,
    params: dict[str, Any],
    request_timeout: float,
) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/{action.lstrip('/')}",
        data=json.dumps(params).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=request_timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (
        urllib.error.URLError,
        TimeoutError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise VerificationError(f"{action} request failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise VerificationError(f"{action} returned a non-object response")
    return payload


def require_success(payload: dict[str, Any], action: str) -> Any:
    if payload.get("status") != "ok" or payload.get("retcode") != 0:
        message = payload.get("message") or payload.get("wording") or "unknown error"
        raise VerificationError(
            f"{action} failed: status={payload.get('status')!r}, "
            f"retcode={payload.get('retcode')!r}, message={message!r}"
        )
    return payload.get("data")


def probe_endpoint(
    label: str,
    base_url: str,
    token: str,
    expected_account: int,
    group_id: int,
    request_timeout: float,
) -> dict[str, Any]:
    status = require_success(
        request_action(base_url, token, "get_status", {}, request_timeout),
        "get_status",
    )
    if not isinstance(status, dict):
        raise VerificationError(f"{label} get_status returned invalid data")
    if status.get("online") is not True or status.get("good") is not True:
        raise VerificationError(
            f"{label} is not ready: online={status.get('online')!r}, "
            f"good={status.get('good')!r}"
        )

    login = require_success(
        request_action(base_url, token, "get_login_info", {}, request_timeout),
        "get_login_info",
    )
    if not isinstance(login, dict):
        raise VerificationError(f"{label} get_login_info returned invalid data")
    try:
        actual_account = int(login.get("user_id"))
    except (TypeError, ValueError) as exc:
        raise VerificationError(f"{label} returned an invalid user_id") from exc
    if actual_account != expected_account:
        raise VerificationError(
            f"{label} account mismatch: expected={expected_account}, "
            f"actual={actual_account}"
        )

    group = require_success(
        request_action(
            base_url,
            token,
            "get_group_info",
            {"group_id": group_id},
            request_timeout,
        ),
        "get_group_info",
    )
    if not isinstance(group, dict) or str(group.get("group_id")) != str(group_id):
        raise VerificationError(f"{label} is not in test group {group_id}")
    return login


def message_text(message: dict[str, Any]) -> str:
    segments = message.get("message")
    if isinstance(segments, str):
        return segments
    if isinstance(segments, list):
        return "".join(
            str(segment.get("data", {}).get("text", ""))
            for segment in segments
            if isinstance(segment, dict) and segment.get("type") == "text"
        )
    raw_message = message.get("raw_message")
    return raw_message if isinstance(raw_message, str) else ""


def message_identity(message: dict[str, Any]) -> tuple[str, str]:
    return str(message.get("user_id", "")), str(message.get("message_id", ""))


def get_group_history(
    base_url: str,
    token: str,
    group_id: int,
    request_timeout: float,
) -> list[dict[str, Any]]:
    data = require_success(
        request_action(
            base_url,
            token,
            "get_group_msg_history",
            {"group_id": group_id, "count": 50},
            request_timeout,
        ),
        "get_group_msg_history",
    )
    if not isinstance(data, dict) or not isinstance(data.get("messages"), list):
        raise VerificationError("get_group_msg_history returned invalid data")
    return [message for message in data["messages"] if isinstance(message, dict)]


def find_new_reply(
    messages: list[dict[str, Any]],
    baseline: set[tuple[str, str]],
    main_account: int,
    expected_reply_parts: tuple[str, ...],
) -> dict[str, Any] | None:
    for message in messages:
        if message_identity(message) in baseline:
            continue
        if str(message.get("user_id")) != str(main_account):
            continue
        text = message_text(message)
        if all(part in text for part in expected_reply_parts):
            return message
    return None


def run_round_trip(
    settings: ValidationSettings,
    timeout: float,
    interval: float,
    request_timeout: float,
) -> tuple[str, str]:
    before = get_group_history(
        settings.sender_base_url,
        settings.sender_token,
        settings.group_id,
        request_timeout,
    )
    baseline = {message_identity(message) for message in before}

    sent = require_success(
        request_action(
            settings.sender_base_url,
            settings.sender_token,
            "send_group_msg",
            {
                "group_id": settings.group_id,
                "message": [
                    {
                        "type": "text",
                        "data": {"text": settings.trigger_message},
                    }
                ],
            },
            request_timeout,
        ),
        "send_group_msg",
    )
    if not isinstance(sent, dict) or sent.get("message_id") is None:
        raise VerificationError("send_group_msg returned no message_id")
    sent_message_id = str(sent["message_id"])

    deadline = time.monotonic() + timeout
    while True:
        history = get_group_history(
            settings.sender_base_url,
            settings.sender_token,
            settings.group_id,
            request_timeout,
        )
        reply = find_new_reply(
            history,
            baseline,
            settings.main_account,
            settings.expected_reply_parts,
        )
        if reply is not None:
            return sent_message_id, str(reply.get("message_id"))
        if time.monotonic() >= deadline:
            raise VerificationError(
                f"no new reply from configured main account within {timeout:g} seconds"
            )
        time.sleep(interval)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe or run a configured ToogleBot dual-account check."
    )
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--main-account", type=int)
    parser.add_argument("--sender-account", type=int)
    parser.add_argument("--group-id", type=int)
    parser.add_argument("--main-base-url")
    parser.add_argument("--sender-base-url")
    parser.add_argument("--scenario", choices=("active", "command"), default="active")
    parser.add_argument("--trigger-message")
    parser.add_argument("--expect", action="append")
    parser.add_argument("--request-timeout", type=float, default=10.0)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument(
        "--confirm-send",
        action="store_true",
        help="send the configured scenario trigger to the configured test group",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        settings = build_settings(args)
        main_login = probe_endpoint(
            "main",
            settings.main_base_url,
            settings.main_token,
            settings.main_account,
            settings.group_id,
            args.request_timeout,
        )
        sender_login = probe_endpoint(
            "sender",
            settings.sender_base_url,
            settings.sender_token,
            settings.sender_account,
            settings.group_id,
            args.request_timeout,
        )
        print(
            "Dual-account probe passed: "
            f"main={int(main_login['user_id'])}, "
            f"sender={int(sender_login['user_id'])}, "
            f"group={settings.group_id}, scenario={settings.scenario}"
        )
        if not args.confirm_send:
            print("Probe-only mode: no message was sent.")
            return 0

        sent_id, reply_id = run_round_trip(
            settings,
            args.timeout,
            args.interval,
            args.request_timeout,
        )
    except VerificationError as exc:
        print(f"Dual-account verification failed: {exc}", file=sys.stderr)
        return 1

    print(
        "Dual-account round trip passed: "
        f"scenario={settings.scenario}, sent_message_id={sent_id}, "
        f"reply_message_id={reply_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
