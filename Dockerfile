FROM mlikiowa/napcat-docker:latest AS napcat

FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1

# 安装 NapCat 运行时依赖 + Xvfb + ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnotify4 libsecret-1-0 libgbm1 \
    xvfb libasound2 fonts-wqy-zenhei \
    libglib2.0-0 libdbus-1-3 libgtk-3-0 \
    libxss1 libxtst6 libatspi2.0-dev libx11-xcb1 \
    ffmpeg gosu curl unzip dbus-user-session \
    gnutls-bin tzdata && \
    echo "${TZ}" > /etc/timezone && \
    ln -sf /usr/share/zoneinfo/${TZ} /etc/localtime && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/*

# 安装 Node.js 22.x (NapCat 运行需要)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 安装 Linux QQ
RUN arch=$(arch | sed s/aarch64/arm64/ | sed s/x86_64/amd64/) && \
    curl -o /tmp/linuxqq.deb \
    https://dldir1.qq.com/qqfile/qq/QQNT/94704804/linuxqq_3.2.23-44343_${arch}.deb && \
    dpkg -i --force-depends /tmp/linuxqq.deb && \
    rm /tmp/linuxqq.deb

# 从 NapCat 官方镜像复制 NapCat 文件
COPY --from=napcat /app/NapCat.Shell.zip /app/NapCat.Shell.zip
COPY --from=napcat /app/templates /app/templates

RUN cd /app && \
    mkdir -p napcat/config && \
    unzip -q NapCat.Shell.zip -d NapCat.Shell && \
    cp -rf NapCat.Shell/* napcat/ && \
    rm -rf NapCat.Shell NapCat.Shell.zip && \
    echo "(async () => {await import('file:///app/napcat/napcat.mjs');})();" \
    > /opt/QQ/resources/app/loadNapCat.js && \
    sed -i 's|"main": "[^"]*"|"main": "./loadNapCat.js"|' \
    /opt/QQ/resources/app/package.json

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 安装 ToogleBot Python 依赖
WORKDIR /bot
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 复制 ToogleBot 代码
COPY . .

# 创建 napcat 用户
RUN useradd --no-log-init -d /app napcat

EXPOSE 3000 3001 6099

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
