#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
QQ_BIN="${NAPCAT_QQ_BIN:-/root/Napcat/opt/QQ/qq}"

dotenv_value() {
    local key="$1"
    local line value
    [[ -f "$ROOT_DIR/.env" ]] || return 0
    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ "$line" == "$key="* ]] || continue
        value="${line#*=}"
        value="${value#\"}"
        value="${value%\"}"
        value="${value#\'}"
        value="${value%\'}"
        printf '%s' "$value"
        return 0
    done < "$ROOT_DIR/.env"
}

from_dotenv_or_default() {
    local variable="$1"
    local key="$2"
    local default="$3"
    local value="${!variable:-}"
    if [[ -z "$value" ]]; then
        value="$(dotenv_value "$key")"
    fi
    printf '%s' "${value:-$default}"
}

ACCOUNT="$(from_dotenv_or_default NAPCAT_MAIN_ACCOUNT NAPCAT_MAIN_ACCOUNT '')"
if [[ ! "$ACCOUNT" =~ ^[1-9][0-9]+$ ]]; then
    printf 'error: NAPCAT_MAIN_ACCOUNT must be configured as a positive integer\n' >&2
    exit 1
fi

NAPCAT_HTTP_HOST="$(from_dotenv_or_default NAPCAT_HTTP_HOST HTTP_HOST 127.0.0.1)"
NAPCAT_HTTP_PORT="$(from_dotenv_or_default NAPCAT_HTTP_PORT HTTP_PORT 6543)"
NAPCAT_HTTP_TOKEN="$(from_dotenv_or_default NAPCAT_HTTP_TOKEN HTTP_TOKEN '')"
NAPCAT_WS_HOST="$(from_dotenv_or_default NAPCAT_WS_HOST WS_HOST 127.0.0.1)"
NAPCAT_WS_PORT="$(from_dotenv_or_default NAPCAT_WS_PORT WS_PORT 3456)"
NAPCAT_WS_TOKEN="$(from_dotenv_or_default NAPCAT_WS_TOKEN WS_TOKEN '')"

for host in "$NAPCAT_HTTP_HOST" "$NAPCAT_WS_HOST"; do
    case "$host" in
        127.0.0.1|localhost|::1) ;;
        *)
            printf 'error: NapCat host must be loopback, got %s\n' "$host" >&2
            exit 1
            ;;
    esac
done

is_port() {
    [[ "$1" =~ ^[1-9][0-9]{0,4}$ ]] && ((10#$1 <= 65535))
}
if ! is_port "$NAPCAT_HTTP_PORT" || ! is_port "$NAPCAT_WS_PORT"; then
    printf 'error: NapCat ports must be integers in the range 1..65535\n' >&2
    exit 1
fi

WORK_DIR="${NAPCAT_MAIN_WORKDIR:-${XDG_STATE_HOME:-$HOME/.local/state}/tooglebot/napcat-main-$ACCOUNT}"
QQ_DATA_DIR="${NAPCAT_MAIN_QQ_DATA_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/QQ-ToogleBot-Main-$ACCOUNT}"

if [[ ! -x "$QQ_BIN" ]]; then
    printf 'error: NapCat QQ binary is not executable: %s\n' "$QQ_BIN" >&2
    exit 1
fi
if ! command -v xvfb-run >/dev/null 2>&1; then
    printf 'error: xvfb-run is required\n' >&2
    exit 1
fi

install -d -m 700 "$WORK_DIR/config" "$WORK_DIR/cache" "$QQ_DATA_DIR"
if command -v flock >/dev/null 2>&1; then
    exec 9>"$WORK_DIR/main.lock"
    if ! flock -n 9; then
        printf 'error: the NapCat main launcher is already active\n' >&2
        exit 1
    fi
fi

if command -v ss >/dev/null 2>&1; then
    for port in "$NAPCAT_HTTP_PORT" "$NAPCAT_WS_PORT"; do
        if ss -ltnH "sport = :$port" | grep -q .; then
            printf 'error: NapCat port %s is already in use\n' "$port" >&2
            exit 1
        fi
    done
fi

export NAPCAT_MAIN_ACCOUNT="$ACCOUNT"
export NAPCAT_HTTP_HOST NAPCAT_HTTP_PORT NAPCAT_HTTP_TOKEN
export NAPCAT_WS_HOST NAPCAT_WS_PORT NAPCAT_WS_TOKEN
export NAPCAT_WORKDIR="$WORK_DIR"

python3 - "$WORK_DIR/config" "$ACCOUNT" <<'PY'
import json
import os
import stat
import sys
from pathlib import Path

config_dir = Path(sys.argv[1])
account = sys.argv[2]

http_server = {
    "enable": True,
    "name": "ToogleBotHTTP",
    "host": os.environ["NAPCAT_HTTP_HOST"],
    "port": int(os.environ["NAPCAT_HTTP_PORT"]),
    "enableCors": False,
    "enableWebsocket": False,
    "messagePostFormat": "array",
    "token": os.environ["NAPCAT_HTTP_TOKEN"],
    "debug": False,
}
websocket_server = {
    "enable": True,
    "name": "ToogleBot",
    "host": os.environ["NAPCAT_WS_HOST"],
    "port": int(os.environ["NAPCAT_WS_PORT"]),
    "reportSelfMessage": True,
    "enableForcePushEvent": True,
    "messagePostFormat": "array",
    "token": os.environ["NAPCAT_WS_TOKEN"],
    "debug": False,
    "heartInterval": 30000,
}
onebot = {
    "network": {
        "httpServers": [http_server],
        "httpSseServers": [],
        "httpClients": [],
        "websocketServers": [websocket_server],
        "websocketClients": [],
        "plugins": [],
    },
    "musicSignUrl": "",
    "enableLocalFile2Url": False,
    "parseMultMsg": False,
    "imageDownloadProxy": "",
}
files = {
    f"napcat_{account}.json": {
        "fileLog": False,
        "consoleLog": False,
        "fileLogLevel": "info",
        "consoleLogLevel": "info",
        "packetBackend": "auto",
        "packetServer": "",
        "o3HookMode": 1,
    },
    f"napcat_protocol_{account}.json": {
        "enable": False,
        "network": {
            "httpServers": [],
            "websocketServers": [],
            "websocketClients": [],
        },
    },
    f"onebot11_{account}.json": onebot,
    "webui.json": {
        "host": "127.0.0.1",
        "port": 6099,
        "token": "",
        "disableWebUI": True,
    },
}
for name, payload in files.items():
    path = config_dir / name
    if path.exists():
        continue
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
PY

printf 'Starting NapCat main account %s\n' "$ACCOUNT"
printf 'NapCat work directory: %s\n' "$WORK_DIR"
printf 'QR code path: %s/cache/qrcode.png\n' "$WORK_DIR"

exec xvfb-run -a "$QQ_BIN" \
    --no-sandbox \
    "--user-data-dir=$QQ_DATA_DIR" \
    -q "$ACCOUNT"
