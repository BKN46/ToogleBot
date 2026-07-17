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

- [渐进式开发文档](./doc/README.md)
- [迁移 TODO](./TODO.md)
- [AI 开发约定](./AGENTS.md)

旧实现保存在 `origin/archived-mirai2-version`，仅用于核对行为。

当前迁移阶段使用本地 NapCat/QQ 进程调试；Docker 构建和容器登录验收等代码迁移
完成后再启用。

## 环境要求

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) (包管理)
- NapCat（可 Docker 部署或独立安装）

## 安装

### 1. 安装依赖

```bash
# 安装 uv（如未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装 Python 依赖
uv sync
```

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
API_PORT=5701                  # ToogleBot 自有 Flask API 端口（当前尚未启动）
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

```bash
./run.sh
```

`run.sh` 只启动本地 ToogleBot 进程，不调用 Docker。它会选择 `venv` / `.venv` 中的
Python、检查 `.env` 和 NapCat WebSocket，并阻止重复启动。调试选项：

```bash
RUN_DRY_RUN=1 ./run.sh              # 只执行启动前检查
RUN_SKIP_NAPCAT_CHECK=1 ./run.sh    # 跳过 NapCat TCP 探测
PYTHON_BIN=/path/to/python ./run.sh # 指定解释器
```

双账号真实群文本验证从 `.env` 读取账号、群和探针文本，完整流程见
[NapCat 登录与双账号验收](./doc/10-napcat-login-test.md)。检查工具默认只读，只有
`--confirm-send` 才发送所选场景的配置文本：

```bash
uv run python tools/napcat_dual_account_check.py --scenario active
uv run python tools/napcat_dual_account_check.py \
  --scenario active --confirm-send
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
