#!/usr/bin/env bash
set -euo pipefail

systemctl restart tooglebot-napcat.service
systemctl restart tooglebot.service
