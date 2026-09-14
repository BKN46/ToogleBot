#!/usr/bin/env python3
"""Restart NapCat after repeated confirmed offline status."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.napcat_login_check import request_action


def env_value(key: str, fallback: str = "") -> str:
    value = os.getenv(key)
    if value:
        return value
    env = Path(".env")
    if not env.exists():
        return fallback
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip("\"'") or fallback
    return fallback


def main() -> int:
    base = f"http://{env_value('HTTP_HOST', '127.0.0.1')}:{env_value('HTTP_PORT', '6543')}"
    token = env_value("HTTP_TOKEN")
    failures = int(os.getenv("NAPCAT_PROBE_FAILURES", "2"))
    delay = float(os.getenv("NAPCAT_PROBE_RESTART_DELAY", "2"))
    offline = 0
    try:
        payload = request_action(base, token, "get_status", 5)
        data = payload.get("data") or {}
        if data.get("online") is True and data.get("good") is True:
            Path(os.getenv("NAPCAT_PROBE_STATE", "/run/tooglebot-napcat-probe")).unlink(missing_ok=True)
            return 0
        offline = 1
        print(f"NapCat unhealthy: online={data.get('online')!r} good={data.get('good')!r}")
    except Exception as exc:
        print(f"NapCat health probe failed: {type(exc).__name__}", file=sys.stderr)
        offline = 1

    # A single failed poll is not enough to restart the account.
    state = Path(os.getenv("NAPCAT_PROBE_STATE", "/run/tooglebot-napcat-probe"))
    previous = int(state.read_text() or "0") if state.exists() else 0
    current = previous + offline
    if current < failures:
        state.write_text(str(current))
        return 0
    state.unlink(missing_ok=True)
    print("NapCat offline threshold reached; restarting service", file=sys.stderr)
    time.sleep(delay)
    subprocess.run(["systemctl", "restart", "tooglebot-napcat.service"], check=False)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
