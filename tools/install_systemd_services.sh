#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="/etc/systemd/system"

if (( EUID != 0 )); then
    printf 'error: install_systemd_services.sh must run as root\n' >&2
    exit 1
fi
if [[ ! -f "$ROOT_DIR/.env" ]]; then
    printf 'error: %s/.env does not exist\n' "$ROOT_DIR" >&2
    exit 1
fi

install -m 0644 "$ROOT_DIR/deploy/systemd/tooglebot-napcat.service" \
    "$UNIT_DIR/tooglebot-napcat.service"
install -m 0644 "$ROOT_DIR/deploy/systemd/tooglebot.service" \
    "$UNIT_DIR/tooglebot.service"
install -m 0644 "$ROOT_DIR/deploy/systemd/tooglebot-api.service" \
    "$UNIT_DIR/tooglebot-api.service"
if [[ -d /etc/nginx/conf.d ]]; then
    install -m 0644 "$ROOT_DIR/deploy/nginx/tooglebot-api-locations.conf" \
        /etc/nginx/conf.d/tooglebot-api-locations.conf
    if grep -Fq 'include /etc/nginx/conf.d/tooglebot-api-locations.conf;' /etc/nginx/nginx.conf; then
        nginx -t
        systemctl reload nginx
    else
        printf 'warning: add the tooglebot-api-locations.conf include to the nginx server on port 36001\n' >&2
    fi
fi
systemctl daemon-reload
systemctl enable tooglebot-napcat.service tooglebot.service tooglebot-api.service

if [[ "${1:-}" == "--start" ]]; then
    systemctl start tooglebot-napcat.service
    systemctl start tooglebot.service
    systemctl start tooglebot-api.service
fi

printf 'Installed tooglebot-napcat.service, tooglebot.service and tooglebot-api.service\n'
printf 'Use systemctl start tooglebot-napcat.service to authorize QQ if needed\n'
printf 'Use systemctl start tooglebot.service after NapCat reports online/good\n'
printf 'Use systemctl start tooglebot-api.service for the HTTP API\n'
