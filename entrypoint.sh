#!/bin/bash
set -e
trap "" SIGPIPE

# ========== NapCat 配置 ==========

# 确保 NapCat 配置完整
if [ ! -f "/app/napcat/config/napcat.json" ]; then
    echo "[entrypoint] 初始化 NapCat 默认配置..."
    mkdir -p /app/napcat/config
fi

# 配置 WebUI Token
CONFIG_PATH=/app/napcat/config/webui.json
if [ ! -f "${CONFIG_PATH}" ] && [ -n "${WEBUI_TOKEN}" ]; then
    echo "[entrypoint] 配置 WebUI Token..."
    cat > "${CONFIG_PATH}" << EOF
{
    "host": "0.0.0.0",
    "port": 6099,
    "token": "${WEBUI_TOKEN}",
    "loginRate": 3
}
EOF
fi

# 配置 OneBot 模板
if [ -n "${MODE}" ] && [ -f "/app/templates/${MODE}.json" ]; then
    cp /app/templates/${MODE}.json /app/napcat/config/onebot11.json
fi

# ========== 用户权限 ==========

: ${NAPCAT_GID:=0}
: ${NAPCAT_UID:=0}
usermod -o -u ${NAPCAT_UID} napcat 2>/dev/null || true
groupmod -o -g ${NAPCAT_GID} napcat 2>/dev/null || true
usermod -g ${NAPCAT_GID} napcat 2>/dev/null || true
chown -R ${NAPCAT_UID}:${NAPCAT_GID} /app

# ========== 启动 Xvfb ==========

rm -rf /tmp/.X1-lock
gosu napcat Xvfb :1 -screen 0 1080x760x16 +extension GLX +render > /dev/null 2>&1 &
sleep 2

export DISPLAY=:1
export FFMPEG_PATH=/usr/bin/ffmpeg

# ========== 启动 NapCat ==========

echo "[entrypoint] 启动 NapCat..."
cd /app/napcat
if [ -n "${ACCOUNT}" ]; then
    gosu napcat /opt/QQ/qq --no-sandbox -q "${ACCOUNT}" &
else
    gosu napcat /opt/QQ/qq --no-sandbox &
fi
NAPCAT_PID=$!

# 等待 NapCat WebSocket 就绪
echo "[entrypoint] 等待 NapCat 启动..."
sleep 10

# ========== 启动 ToogleBot ==========

echo "[entrypoint] 启动 ToogleBot..."
cd /bot
exec uv run python bot.py
