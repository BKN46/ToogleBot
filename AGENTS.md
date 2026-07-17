# ToogleBot AI 开发约定

本文件作用于整个仓库。目标是让 AI 在 Mirai/NoneBot2 向 NapCat/OneBot 11
迁移期间，能够先确认事实、再做局部修改，并且不破坏运行数据或他人的未提交工作。

## 开始前必须做

1. 运行 `git status --short --branch`，当前工作树经常包含迁移中的未提交改动。
2. 按任务范围阅读：
   - 全局入口：`doc/README.md`
   - 迁移任务：`TODO.md`、`doc/09-migration-guide.md`
   - 消息接入：`doc/02-runtime-flow.md`、`doc/03-napcat-adapter.md`
   - 插件开发：`doc/04-message-plugin-contract.md`、`doc/05-plugin-map.md`
   - 配置或数据：`doc/06-config-data-persistence.md`
   - NapCat 登录/部署验收：`doc/10-napcat-login-test.md`
3. 将当前工作树视为 NapCat 主线的事实来源。`origin/archived-mirai2-version`
   只用于核对旧行为，不用于恢复 NoneBot、Mirai 类型或旧目录结构。
4. 不读取、输出或提交 `.env` 的真实密钥，不修改 `data/`、`log/`、`logs/`、
   `guild1.db*` 等运行数据，除非任务明确要求。

## 当前架构边界

```text
bot.py
  -> adapter/server.py       NapCat WebSocket 生命周期
  -> adapter/msg_queue.py    OneBot 事件/消息转换和收发队列
  -> adapter/worker.py       插件匹配、执行、扣费、冷却、异常处理
  -> adapter/post_process.py 历史、主动插件、聊天收益

plugins/*.py                 可自动发现的业务插件
toogle/                      与 QQ 框架无关的领域核心和共享服务
api/                         外部 HTTP API（当前尚未接入主生命周期）
tools/                       独立工具与字体资源
statistics/                  离线统计脚本
```

职责约束：

- OneBot JSON、NapCat action、WebSocket/HTTP 细节只能进入 `adapter/`。
- `toogle/message.py` 和 `toogle/message_handler.py` 是内部稳定契约，不应依赖
  NapCat、NoneBot 或 Mirai 类型。
- 业务命令放在根 `plugins/`；子目录只作为辅助库，`toogle/index.py` 只扫描
  `plugins/*.py`。
- 通用能力优先放 `toogle/` 或 `tools/`，不要让一个业务插件反向承担适配层职责。
- 新代码不得新增 `nonebot`、`mirai`、`MIRAI_*`、`toogle.plugins.*` 或
  `toogle.tools.*` 依赖。

## 迁移期事实

当前代码能通过 Python 3.12 语法编译，但尚不能视为可运行完成态。已知阻断项
记录在 `TODO.md`。2026-07-17 已完成正向 WebSocket JSON/action 基础闭环、显式 plugin
registry、有界 asyncio queue、单 event loop worker 和 scheduler 生命周期；剩余重点是
依赖分层、同步插件 I/O、媒体/转发、完整事件、资源数据和 API。在这些项目完成前：

- 文档必须使用“当前实现”与“目标行为”区分事实，不能声称端到端已可用。
- 修复接入层时先用脱敏的 OneBot fixture 做转换测试，再连接真实 NapCat。
- 不为了让 import 成功而吞掉异常；插件加载失败必须保留插件名和异常上下文。
- 每完成一个迁移项，应同时更新 `TODO.md` 的状态与相应 `doc/` 文档。
- 当前迁移阶段只使用本地 NapCat/QQ 进程做真实协议验收，不启动或重建 Docker；
  Docker 构建、容器登录和 volume 验收要等代码迁移完成，除非用户明确改变该约束。

核对旧实现时使用只读命令，例如：

```bash
git show origin/archived-mirai2-version:toogle/nonebot2_adapter.py
git diff origin/archived-mirai2-version -- <path>
```

不要 checkout 归档分支文件覆盖当前工作树。

## 文档动态更新契约

文档是代码变更的一部分，不是迁移完成后再补的附件。每次 AI 任务结束前必须运行
`git status --short` 和 `git diff --name-only`（前者覆盖未跟踪文件），按下表检查并同步
相应文档；即使用户没有单独要求更新文档，只要行为、配置、模块边界、验证命令或
迁移状态发生变化，就必须更新。

| 代码/行为变化 | 必须检查并按需更新 |
| --- | --- |
| `bot.py`、`adapter/server.py`、队列或连接生命周期 | `doc/01-project-overview.md`、`doc/02-runtime-flow.md`、`doc/03-napcat-adapter.md`、`doc/09-migration-guide.md`、`TODO.md` |
| OneBot action、事件或消息段 | `doc/03-napcat-adapter.md`、`doc/04-message-plugin-contract.md`、对应 fixture 说明、`TODO.md` |
| `toogle/message*.py`、PluginWrapper、worker、插件发现 | `doc/02-runtime-flow.md`、`doc/04-message-plugin-contract.md`、`doc/07-shared-services.md` |
| 新增、删除、改名或移动插件/辅助模块 | `doc/05-plugin-map.md`；配置或数据变化时同时更新 06 |
| `.env` key、配置解析、静态资源、数据库、运行数据 | `doc/06-config-data-persistence.md`、`.env.example`（存在后）、`TODO.md` |
| scheduler、Flask API、共享工具和日志 | `doc/07-shared-services.md`，必要时同步 02、06 |
| 依赖、Docker、CI、测试命令或验收流程 | `doc/08-development-playbook.md`、`doc/09-migration-guide.md`、`doc/10-napcat-login-test.md`、`README.md` |
| P0/P1/P2 项完成、阻断变化或实测结果 | `TODO.md`、相关模块文档；里程碑变化时同步 `README.md` |

更新规则：

- 文档必须区分“当前实现”“目标契约”“已验证日期/环境”，不能把计划写成已完成。
- 新文档要加入 `doc/README.md` 的渐进式路径和任务索引；移动/删除文档要修全部链接。
- 完成 TODO 项时同时写入验收证据（命令、fixture 或测试层级）；发现新阻断要立即登记。
- 外部协议或 API 可能变化时，在实现任务中重新核对官方文档，并更新“最后核对日期”。
- 纯内部重构若确认不改变任何文档事实，可以不修改正文，但最终说明中要明确
  “已核对对应文档，无行为变化”。

## 插件契约

普通插件继承 `MessageHandler`，至少定义 `name`、`trigger`、`readme`，并实现
`async def ret(self, message: MessagePack)`。返回 `MessageChain` 表示响应，返回
`None` 表示静默。

```python
from typing import Optional

from toogle.message import MessageChain
from toogle.message_handler import MessageHandler, MessagePack


class Example(MessageHandler):
    name = "示例"
    trigger = r"^示例$"
    readme = "返回示例文本"
    interval = 10

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        return MessageChain.plain("ok", quote=message.as_quote())
```

修改插件时必须检查：

- `trigger` 是否兼容分发器实际采用的正则语义。
- 错误响应是否应设置 `no_charge=True`、`no_interval=True`。
- 群聊和私聊的 `group.id`、`member.id`、`message_type` 是否都合理。
- 是否依赖配置 key、外部 API、Cookie、字体或 `data/` 下的非仓库资源。
- 主动发送是否仍通过 `toogle.adapter.bot_send_message()`，而非调用 NapCat。

## OneBot/NapCat 规则

- NapCat action、请求字段和响应 schema 优先参考官方自动生成的
  [NapCat Apifox 接口文档](https://napcat.apifox.cn/)，不得只凭旧 Mirai 代码或记忆实现。
  Apifox 不覆盖的 transport URL/path 必须结合部署配置和脱敏实测帧确认。
- WebSocket 帧必须在边界处 `json.loads` / `json.dumps`；内部队列传字典对象。
- 区分事件帧、action 响应和 echo，不要把 action 响应当作消息事件。
- 消息段名称和字段以 OneBot 11/NapCat 实际 payload fixture 为准；转换应覆盖
  text、at、reply、image、forward，未知段必须可降级且不能让整条消息丢失。
- 每个 action 应有唯一 `echo`，需要结果的调用必须能关联响应。
- 异步循环中不得直接执行带超时的同步 `queue.get()` 或无超时 `requests`。
- WebSocket 断开应可重连；启动、连接、调度和关闭钩子只能执行约定次数。

## 配置与数据

- 新配置集中在根 `configs.py`，命名按 `WS_*`、`HTTP_*`、`API_*` 和业务域分组。
- 不新增 `eval()` 配置解析；配置重构优先使用 `os.environ`、安全的 JSON 或
  `ast.literal_eval`，并对必需项做显式校验。
- 路径使用 `pathlib.Path(__file__)` 或统一的项目根，不依赖调用者当前目录。
- 仓库内静态资源放在模块附近或 `tools/`；运行状态放 `data/`，日志放 `logs/`
  （迁移完成前兼容现有 `log/`）。
- 数据格式变化要考虑旧 JSON、pickle、SQLite 的兼容或迁移，禁止无提示清空。

## 修改与验证

- 保持改动局部；不要顺手格式化大型插件文件或回退不相关改动。
- 手工修改使用 `apply_patch`；默认 ASCII，已有中文文档和用户文案可继续中文。
- 新增适配行为必须配 fixture 单测；修复共享契约至少覆盖一次收消息和发消息。
- 不在测试中连接真实群、禁言、撤回、退群、发送文件或调用付费 API。
- NapCat 真实验收的主账号、发送账号和测试群必须分别来自 `NAPCAT_MAIN_ACCOUNT`、
  `NAPCAT_SENDER_ACCOUNT`、`NAPCAT_TEST_GROUP`；禁止在 Python、Shell 或 JSON 模板写死。
  当前本机使用的具体测试资源只作为 10 的实测记录，不是代码默认值。
- 首次扫码允许人工介入，后续重启登录必须自动化。任何真实消息发送前必须依次校验
  两端 online/good、登录账号和目标群，并要求显式确认；默认探针不得发送消息。
- 当前阶段按照 `doc/10-napcat-login-test.md` 的本地阶段 A/B/D 验收；不得为了登录测试
  运行 `docker compose up/build/restart`。
- 登录 token、WebUI token、二维码、登录凭证和 QQ 持久化目录不得进入 git 或测试日志。

当前可用的最低静态验证：

```bash
uv sync --frozen
uv run python -m compileall -q bot.py configs.py adapter api toogle plugins tools
uv run python -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'
```

仓库是直接运行源码的非打包应用，`pyproject.toml` 以
`[tool.uv] package = false` 固化该事实；不要重新引入只为绕过包发现的空包目录。

结束前再次查看 `git diff --check` 和 `git status --short`，只汇报本次实际修改，
并明确哪些测试因 NapCat、密钥或外部数据不可用而未执行。
