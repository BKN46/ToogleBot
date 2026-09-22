# 大黄狗

NapCat + 原生 WebSocket 实现的 QQ Bot

[![在爱发电支持我](https://afdian.moeci.com/1/badge.svg)](https://afdian.com/a/ToogleBot)

## 架构

```
NapCat (OneBot 11 WebSocket) ←→ adapter/server.py (原生 WS 客户端)
                                       ↓
                               adapter/worker.py (消息处理)
                                       ↓
                                plugins/* (插件系统)
```

- **NapCat**：基于 NTQQ 的 OneBot 11 协议实现，提供 WebSocket 接口
- **adapter**：原生 `websockets` 库连接 NapCat，收发消息队列调度
- **toogle**：插件加载、消息匹配、经济系统、定时任务等核心逻辑

## 文档与迁移状态

当前仓库正在从 Mirai/NoneBot2 迁移到 NapCat/OneBot 11。基础 WebSocket JSON/action
闭环、plugin registry、asyncio worker、基础 SQLite bootstrap 和 scheduler 主路径已完成
第一轮修复；双测试账号的普通插件与主动插件真实群消息往返均已通过。但构建、媒体/
转发、完整事件、其余同步插件 I/O 和 API 仍未闭合，暂不能声明端到端迁移完成。

合并转发的出站适配已使用 NapCat 的 `send_*_forward_msg` action 和 `node` 节点结构，
并支持递归节点正文；真实账号投递（包括 Markdown 双层转发）仍需独立观察账号验收。

- [渐进式开发文档](./doc/README.md)
- [迁移 TODO](./TODO.md)
- [AI 开发约定](./AGENTS.md)

旧实现保存在 `origin/archived-mirai2-version`，仅用于核对行为。

当前迁移阶段使用本地 NapCat/QQ 进程调试；Docker 构建和容器登录验收等代码迁移
完成后再启用。

## 环境要求

本机 2026-09-10 已验证 NapCat Shell 4.18.19 与 QQ 3.2.28-48517 的登录及只读接口；
升级与回滚记录见 [NapCat 验收文档](./doc/10-napcat-login-test.md)。

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) (包管理)
- NapCat（可 Docker 部署或独立安装）

## 安装

### 1. 安装依赖

```bash
# 安装 uv（如未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装 Python 依赖
uv sync --frozen
```

锁定依赖包含图片 NSFW 检测所需的 ONNX Runtime；首次部署运行
`uv run python -m tools.nsfw_check download --endpoint https://huggingface.co` 下载并校验模型。
旧 OpenNSFW2/TensorFlow 仅在 `nsfw-baseline` 依赖组中用于对比。修改 `pyproject.toml` 后先运行
`uv lock` 再重新同步。

磁链截图还使用锁文件中的 PyAV（`av`）读取索引并按需下载分片；更新后需重新
`uv sync --frozen`。下载粒度、限额和验证范围见 [业务插件地图](./doc/05-plugin-map.md)。

### 2. 配置 NapCat

安装并启动 NapCat，确保开启 OneBot 11 WebSocket 服务。action 和数据模型参考
[NapCat Apifox 接口文档](https://napcat.apifox.cn/)，本项目登录验收见
[NapCat 登录自动化方案](./doc/10-napcat-login-test.md)。

### 3. 配置 `.env`

```ini
WS_HOST=127.0.0.1              # NapCat WebSocket 地址
WS_PORT=3456                   # NapCat WebSocket 端口
WS_PATH=/                      # NapCat 正向 WebSocket path；也可改用 WS_URL
WS_TOKEN=your_token            # NapCat access_token
HTTP_HOST=127.0.0.1            # HTTP API 地址
HTTP_PORT=6543                 # HTTP API 端口
HTTP_TOKEN=your_http_token     # HTTP API token
API_HOST=127.0.0.1             # ToogleBot Flask API 内部监听地址
API_PORT=36002                 # Flask 内部端口（nginx 对外代理 36001）
API_PUBLIC_PORT=36001          # 对外 API 端口
WORKER_NUM=1                   # 同一 event loop 的插件 worker 数

SUPERUSERS=[]                  # 管理员QQ号列表
ADMIN_LIST=["123456789"]       # 管理员列表
CONCURRENCY=true               # 是否并行模式

NAPCAT_MAIN_ACCOUNT=123456789
NAPCAT_SENDER_ACCOUNT=234567890
NAPCAT_TEST_GROUP=345678901
NAPCAT_ACTIVE_PROBE_ENABLED=false
NAPCAT_ACTIVE_PROBE_TRIGGER=local_active_probe_nonce
NAPCAT_ACTIVE_PROBE_REPLY=local_active_probe_reply
NAPCAT_ACTIVE_PROBE_EXPECT=["local_active_probe_reply"]
BOT_TIMEZONE=Asia/Shanghai

# 其他插件配置见各插件说明
```

## 运行

### 直接运行

“查一下”使用独立配置 `KIMI_SEARCH_MODEL`（默认 `kimi-k2.7-code`）和Kimi官方
Formula搜索工具；不改变 `.gpt` 或每日新闻的模型。失败仍免扣费/冷却。
Kimi不可用时自动回退 `deepseek-flash` 和现有本地搜索方案；两条链路都失败才返回错误。

每日新闻：每天 10 点（`BOT_TIMEZONE`，默认北京时间）向 `CHAT_GROUP_LIST` 推送
首次生成时刻前24小时的新闻，经AI精选默认15条，顶部显示生成时间，正文只有标题和简述。
当天首次成功生成后落盘缓存，后续手动查询和定时推送复用；次日零点清理，重启后也会检查日期。
免费中新网 RSS 提供候选，AI 独立使用 `deepseek-flash` 非思考模式和已有DeepSeek密钥；
排除官话宣传，优先国内外重大事件及民生实际变化，合格条目不足15条时不凑数。
`NEWS_RSS_URLS`、`NEWS_MAX_ITEMS` 可调整新闻源和条数，模型调用可能产生费用。
发送 `每日新闻` 或 `.news` 可手动查看截至当前的过去24小时新闻，仅回复当前群或私聊，不触发全群推送。
RSS 保留条数有限，不保证全量覆盖；源失败不回退旧闻。详见 [调度说明](doc/07-shared-services.md#每日新闻)。

```bash
./run.sh
```

`run.sh` 只启动本地 ToogleBot 进程，不调用 Docker。它会优先选择 `.venv`、回退 `venv` 中的
Python、检查 `.env` 和 NapCat WebSocket，并阻止重复启动。调试选项：

```bash
RUN_DRY_RUN=1 ./run.sh              # 只执行启动前检查
RUN_SKIP_NAPCAT_CHECK=1 ./run.sh    # 跳过 NapCat TCP 探测
PYTHON_BIN=/path/to/python ./run.sh # 指定解释器
```

### systemd 正式运行

本地正式 QQ/NapCat 使用仓库内的 systemd unit，账号、HTTP/WS token 和路径仍由本机
`.env` 提供：

```bash
sudo tools/install_systemd_services.sh
sudo systemctl start tooglebot-napcat.service
# 首次运行打开启动器输出的 NAPCAT_MAIN_WORKDIR/cache/qrcode.png 完成 QQ 授权
uv run python tools/napcat_login_check.py --account "$NAPCAT_MAIN_ACCOUNT" --check-group-list
sudo systemctl start tooglebot.service
sudo systemctl start tooglebot-api.service
```

状态、日志和重启：

`sudo bash restart.sh` 同时重启 NapCat 和 worker（不包含 API）；QQ 登录状态仍需单独检查。

```bash
systemctl status tooglebot-napcat.service tooglebot.service
systemctl status tooglebot-api.service nginx.service
journalctl -u tooglebot-napcat.service -u tooglebot.service -f
sudo systemctl restart tooglebot-napcat.service
```

NapCat 使用独立 QQ 数据目录和回环 HTTP/WS 监听；两个 unit 使用控制组停止并支持异常
重启。首次扫码后重启 NapCat 应按登录验收流程无扫码恢复，不能只以 systemd 进程存在
判断账号已登录。

双账号真实群文本验证从 `.env` 读取账号、群和探针文本，完整流程见
[NapCat 登录与双账号验收](./doc/10-napcat-login-test.md)。检查工具默认只读，只有
`--confirm-send` 才发送所选场景的配置文本：

```bash
uv run python tools/napcat_dual_account_check.py --scenario active
uv run python tools/napcat_dual_account_check.py \
  --scenario active --confirm-send
```

Markdown 段默认只探测主账号和项目序列化，不发送消息。显式发送时必须先启动第二
NapCat 实例；工具只在第二账号的群历史确实收到新 Markdown 段后判定投递成功：

```bash
venv/bin/python -m tools.napcat_markdown_check
venv/bin/python -m tools.napcat_markdown_check --confirm-send
```

### Docker 部署（迁移完成后启用）

当前阶段不要执行本节命令。下面仅保留目标部署入口，待 `TODO.md` 的核心收发和构建
阻断清零后再验证。

```bash
# 设置 QQ 账号和 WebUI 密码
export QQ_ACCOUNT=123456789
export WEBUI_TOKEN=napcat

docker compose up -d
```

容器包含 NapCat + ToogleBot，启动后：
- NapCat WebUI: `http://<host>:6099/webui`
- 首次登录需扫码，之后可快速登录

### Docker 数据持久化

| 路径 | 说明 |
|------|------|
| `napcat_config` | NapCat 配置文件 |
| `qq_data` | QQ 登录数据 |
| `./data` | ToogleBot 数据 |
| `./.env` | ToogleBot 配置 |

## 功能

```
货币转换 / 骰子 / 科学remake / Python解释器
AI画图 / Midjourney / 随机ACG老婆
余额 / 大黄狗赞助
A股详情查询 / 动漫下载搜索 / 当季新番
百度指数 / 日期计算器 / 影视下载搜索
全国降水天气预告图 / 健康计算器 / PC硬件对比
禁用成员 / 模拟棒球比赛
CSGO Buff饰品查询 / CSGO开箱
磁链内容解析 / Minecraft RCON / 模拟赛马
随机专辑 / 塔科夫查询
OpenAI对话 / 大黄狗有问必答
趣图 / 黑历史 / 随机龙图 / 反转GIF / 塔罗牌
战雷拆包数据查询 / 战雷开线资源查询 / 战雷胜率查询
每日运势 / 判断色图
DND5E DPR计算器 / DND5E查询 / 自定义骰表
创建定时 / 每日色图排行
计算器 / 勾股计算 / 单位转换 / Wolfram Alpha / 数学绘图
吃什么 / 随机选择 / 抽奖 / 世界时间 / 反撤回 / 投票
```
<!-- Runtime recovery update 2026-09-11 -->
2026-09-11 当前恢复机制：正常运行 `run.sh` 不再因 NapCat 端口未就绪退出，
由适配层退避重连；`RUN_DRY_RUN=1` 仍执行端口预检查。
普通插件和消息后处理受 `PLUGIN_TIMEOUT_SECONDS`（默认 300 秒）限制；
worker 关闭超时覆盖满队列投递退出标记的等待。
事件循环连续阻塞超过 `EVENT_LOOP_TIMEOUT_SECONDS`（默认 600 秒，最小 10 秒）
时，独立线程令进程异常退出，由 systemd 重启。此兜底会丢失内存队列及未保存状态，
不能替代同步插件 I/O 迁移，也不能保证外部操作恰好执行一次。
验证覆盖：`test_worker_flow.py` 的超时恢复与满队列关闭、`test_watchdog.py` 的子进程阻塞退出。
2026-09-11 二维码访问权限修复：`tools/start_napcat_main.sh` 仅在首次创建 cache
时设置 700，重启保留已有权限及 ACL，避免单图片 Nginx 映射因 ACL mask 被清零而 403。
config 和 QQ 专用目录仍设置 700；新部署的二维码映射及最小权限 ACL 由管理员配置。
回归测试：`test_napcat_cache_permissions.py` 使用临时目录和假 QQ 程序，验证首次权限、
两次启动后的 ACL 保留，不连接真实 QQ。
