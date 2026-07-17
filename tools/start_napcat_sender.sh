#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE_DIR="$ROOT_DIR/tools/napcat_sender_config"
QQ_BIN="${NAPCAT_QQ_BIN:-/root/Napcat/opt/QQ/qq}"

dotenv_value() {
    local key="$1"
    local value=""
    if [[ -f "$ROOT_DIR/.env" ]]; then
        value="$(sed -n "s/^${key}=//p" "$ROOT_DIR/.env" | tail -n 1)"
        value="${value#\"}"
        value="${value%\"}"
        value="${value#\'}"
        value="${value%\'}"
    fi
    printf '%s' "$value"
}

SENDER_ACCOUNT="${NAPCAT_SENDER_ACCOUNT:-$(dotenv_value NAPCAT_SENDER_ACCOUNT)}"
if [[ ! "$SENDER_ACCOUNT" =~ ^[1-9][0-9]+$ ]]; then
    printf 'error: NAPCAT_SENDER_ACCOUNT must be configured as a positive integer\n' >&2
    exit 1
fi

WORK_DIR="${NAPCAT_SENDER_WORKDIR:-${XDG_STATE_HOME:-$HOME/.local/state}/tooglebot/napcat-sender-$SENDER_ACCOUNT}"
QQ_DATA_DIR="${NAPCAT_SENDER_QQ_DATA_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/QQ-ToogleBot-Sender-$SENDER_ACCOUNT}"

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
    exec 9>"$WORK_DIR/sender.lock"
    if ! flock -n 9; then
        printf 'error: the NapCat sender launcher is already active\n' >&2
        exit 1
    fi
fi
if command -v ss >/dev/null 2>&1 && ss -ltnH "sport = :6544" | grep -q .; then
    printf 'error: sender HTTP port 6544 is already in use\n' >&2
    exit 1
fi

declare -A CONFIG_TARGETS=(
    [napcat.json]="napcat_${SENDER_ACCOUNT}.json"
    [onebot11.json]="onebot11_${SENDER_ACCOUNT}.json"
    [webui.json]="webui.json"
)
for template_name in "${!CONFIG_TARGETS[@]}"; do
    target="$WORK_DIR/config/${CONFIG_TARGETS[$template_name]}"
    if [[ ! -e "$target" ]]; then
        cp -- "$TEMPLATE_DIR/$template_name" "$target"
        chmod 600 "$target"
    fi
done

printf 'Starting NapCat sender account %s\n' "$SENDER_ACCOUNT"
printf 'NapCat work directory: %s\n' "$WORK_DIR"
printf 'QR code path: %s/cache/qrcode.png\n' "$WORK_DIR"

export NAPCAT_WORKDIR="$WORK_DIR"
exec xvfb-run -a "$QQ_BIN" \
    --no-sandbox \
    "--user-data-dir=$QQ_DATA_DIR" \
    -q "$SENDER_ACCOUNT"
