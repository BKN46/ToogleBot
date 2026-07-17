#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
    printf 'error: %s/.env does not exist\n' "$ROOT_DIR" >&2
    exit 1
fi

if [[ -n "${PYTHON_BIN:-}" ]]; then
    PYTHON="$PYTHON_BIN"
elif [[ -x "$ROOT_DIR/venv/bin/python" ]]; then
    PYTHON="$ROOT_DIR/venv/bin/python"
elif [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    PYTHON="$ROOT_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="$(command -v python3)"
else
    printf 'error: no Python interpreter found\n' >&2
    exit 1
fi

if ! "$PYTHON" -c 'import sys; raise SystemExit(sys.version_info < (3, 12))'; then
    printf 'error: Python 3.12 or newer is required: %s\n' "$PYTHON" >&2
    exit 1
fi

if command -v flock >/dev/null 2>&1; then
    LOCK_FILE="${TMPDIR:-/tmp}/tooglebot-${UID}.lock"
    exec 9>"$LOCK_FILE"
    if ! flock -n 9; then
        printf 'error: another ToogleBot run.sh process is already active\n' >&2
        exit 1
    fi
fi

if [[ "${RUN_SKIP_NAPCAT_CHECK:-0}" != "1" ]]; then
    "$PYTHON" - <<'PY'
import socket
from pathlib import Path
from urllib.parse import urlparse

values = {}
for raw_line in Path(".env").read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    values[key.strip()] = value.strip().strip("\"'")

ws_url = values.get("WS_URL", "")
if ws_url:
    parsed = urlparse(ws_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 3456
else:
    host = values.get("WS_HOST", "127.0.0.1")
    port = int(values.get("WS_PORT", "3456"))

if host in {"0.0.0.0", "::", "[::]"}:
    host = "127.0.0.1"

try:
    with socket.create_connection((host, port), timeout=2):
        pass
except OSError as exc:
    raise SystemExit(
        f"error: NapCat WebSocket is unavailable at {host}:{port}: {exc}"
    ) from exc

print(f"NapCat WebSocket reachable at {host}:{port}")
PY
fi

if [[ "${RUN_DRY_RUN:-0}" == "1" ]]; then
    printf 'Preflight checks passed with %s\n' "$PYTHON"
    exit 0
fi

printf 'Starting ToogleBot with %s\n' "$PYTHON"
export PYTHONUNBUFFERED=1
export PYTHONFAULTHANDLER=1
exec "$PYTHON" bot.py "$@"
