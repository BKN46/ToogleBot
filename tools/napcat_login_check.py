#!/usr/bin/env python3
"""Poll NapCat's HTTP API until the expected test account is online."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any


class ProbeError(RuntimeError):
    pass


def validate_test_account(account: int) -> None:
    if account <= 0:
        raise ProbeError("test account must be a positive integer")


def request_action(
    base_url: str,
    token: str,
    action: str,
    request_timeout: float,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/{action.lstrip('/')}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(
        url,
        data=b"{}",
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=request_timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ProbeError(f"{action} request failed: {exc}") from exc

    if not isinstance(payload, dict):
        raise ProbeError(f"{action} returned a non-object response")
    return payload


def require_success(payload: dict[str, Any], action: str) -> dict[str, Any]:
    if payload.get("status") != "ok" or payload.get("retcode") != 0:
        message = payload.get("message") or payload.get("wording") or "unknown error"
        raise ProbeError(
            f"{action} failed: status={payload.get('status')!r}, "
            f"retcode={payload.get('retcode')!r}, message={message!r}"
        )
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ProbeError(f"{action} returned invalid data")
    return data


def validate_status(payload: dict[str, Any]) -> dict[str, Any]:
    data = require_success(payload, "get_status")
    if data.get("online") is not True or data.get("good") is not True:
        raise ProbeError(
            f"NapCat is not ready: online={data.get('online')!r}, "
            f"good={data.get('good')!r}"
        )
    return data


def validate_login_info(
    payload: dict[str, Any], expected_account: int
) -> dict[str, Any]:
    data = require_success(payload, "get_login_info")
    try:
        actual_account = int(data.get("user_id"))
    except (TypeError, ValueError) as exc:
        raise ProbeError("get_login_info returned an invalid user_id") from exc
    if actual_account != expected_account:
        raise ProbeError(
            f"unexpected login account: expected={expected_account}, actual={actual_account}"
        )
    return data


def validate_group_list(payload: dict[str, Any]) -> None:
    if payload.get("status") != "ok" or payload.get("retcode") != 0:
        raise ProbeError("get_group_list failed")
    if not isinstance(payload.get("data"), list):
        raise ProbeError("get_group_list returned invalid data")


def build_probe(
    base_url: str,
    token: str,
    expected_account: int,
    request_timeout: float,
    check_group_list: bool,
) -> Callable[[], dict[str, Any]]:
    def probe() -> dict[str, Any]:
        status = request_action(base_url, token, "get_status", request_timeout)
        validate_status(status)
        login = request_action(base_url, token, "get_login_info", request_timeout)
        login_data = validate_login_info(login, expected_account)
        if check_group_list:
            groups = request_action(base_url, token, "get_group_list", request_timeout)
            validate_group_list(groups)
        return login_data

    return probe


def wait_for_login(
    probe: Callable[[], dict[str, Any]], timeout: float, interval: float
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_error: ProbeError | None = None
    while True:
        try:
            return probe()
        except ProbeError as exc:
            last_error = exc
        if time.monotonic() >= deadline:
            raise ProbeError(f"login check timed out: {last_error}") from last_error
        time.sleep(interval)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Wait for NapCat to log in with the expected validation account."
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("NAPCAT_TEST_HTTP_URL", "http://127.0.0.1:6543"),
    )
    parser.add_argument(
        "--account",
        type=int,
        default=os.getenv("NAPCAT_TEST_ACCOUNT")
        or os.getenv("NAPCAT_MAIN_ACCOUNT"),
    )
    parser.add_argument("--token", default=os.getenv("NAPCAT_TEST_TOKEN", ""))
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--interval", type=float, default=3.0)
    parser.add_argument("--request-timeout", type=float, default=10.0)
    parser.add_argument("--check-group-list", action="store_true")
    args = parser.parse_args()
    if args.account is None:
        parser.error(
            "--account or NAPCAT_TEST_ACCOUNT/NAPCAT_MAIN_ACCOUNT is required"
        )
    args.account = int(args.account)
    return args


def main() -> int:
    args = parse_args()
    try:
        validate_test_account(args.account)
    except ProbeError as exc:
        print(f"NapCat login check refused: {exc}", file=sys.stderr)
        return 2
    probe = build_probe(
        args.base_url,
        args.token,
        args.account,
        args.request_timeout,
        args.check_group_list,
    )
    try:
        login = wait_for_login(probe, args.timeout, args.interval)
    except ProbeError as exc:
        print(f"NapCat login check failed: {exc}", file=sys.stderr)
        return 1

    print(
        "NapCat login check passed: "
        f"account={int(login['user_id'])}, nickname={login.get('nickname', '')!r}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
