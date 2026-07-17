# 09 Mirai 到 NapCat 迁移指南

## 迁移原则

迁移目标不是逐行翻译 Mirai API，而是保持 ToogleBot 内部业务契约，并为 OneBot 11
重新实现 transport：

```text
旧：Mirai event -> nonebot adapter -> Toogle objects -> plugins
新：OneBot JSON -> adapter/           -> Toogle objects -> plugins
```

`toogle/message.py`、`MessagePack`、插件基类、经济和大多数业务代码是要保留的核心；
NoneBot matcher、Mirai event class、sessionKey 和 Mirai HTTP API 都不应进入新实现。

## 对照表

| Mirai/NoneBot 时代 | NapCat 目标 | 迁移说明 |
| --- | --- | --- |
| `bot.py` NoneBot driver | `bot.py` asyncio lifecycle | 显式管理连接、worker、scheduler、API 和关闭。 |
| `toogle/nonebot2_adapter.py` | `toogle/adapter.py` + `adapter/*` | 平台无关策略与 OneBot transport 分离。 |
| `plugins/load.py` matcher | `adapter/worker.py` 正则分发 | 必须明确 search/match 和多插件触发语义。 |
| `plugins/toogle.py` hooks | `adapter/post_process.py` | 恢复历史、事件、启动/关闭行为。 |
| `plugins/schedule.py` NoneBot 注册层 | `adapter/schedule.py` | APScheduler 需要显式 start/stop。 |
| `toogle/mirai_extend.py` | `adapter/http_request.py` | action 字段、错误模型和 timeout 按 OneBot 重做。 |
| Mirai `MessageChain` | OneBot message segments | 都转换到内部 `toogle.message.MessageChain`。 |
| `VERIFY_KEY`、`MIRAI_*` | `WS_*`、`HTTP_*`、bot self id | self id 最好来自 lifecycle，不复活旧 key。 |
| `mirai/logs` | 结构化应用日志/消息审计 | 统计脚本需要新输入契约。 |

## 不要机械映射的部分

- Mirai `At.target` 不等于 OneBot `data.qq` 的字段名。
- Mirai `AtAll` 是独立类型，OneBot 通常是 `at` + `qq=all`。
- Mirai forward segment 可直接带 nodeList，OneBot 发送合并转发常需要专门 action。
- Mirai quote origin 与 OneBot reply id 的补全方式不同。
- NoneBot matcher 的正则行为和当前 `re.match()` 不等价。
- NoneBot 的 scheduler、startup/shutdown hooks 不会因 import APScheduler 自动出现。
- NoneBot `Bot.send()` 隐藏了群/私聊目标和响应，原生 transport 必须显式处理。

## 推荐迁移阶段

### 阶段 0：可重复构建

- clean 环境能 `uv sync --frozen`。
- 所有直接 import 依赖有声明，重型/可选插件有明确 extra 或禁用策略。
- `.env.example` 和配置 schema 不含 Mirai key。
- 先准备 `.dockerignore` 和显式 build context 规则，确保未来 Docker build 不包含密钥
  和运行数据；当前阶段不实际构建或启动容器。

状态（2026-07-17）：项目已用 `[tool.uv] package = false` 明确为非打包应用，消除
Hatchling 根包发现失败；直接依赖审计、可选依赖分层和 `.env.example` 仍未完成。

### 阶段 1：transport 闭环

- mock WebSocket 可收/发 JSON。
- action 有 echo 和 response 路由。
- async loop 无同步 queue 阻塞。
- 连接断开可重连，关闭可取消所有 task。

状态（2026-07-17）：以上基础实现与 mock 事件到群 action 闭环已完成；本地 NapCat
`get_status` / `get_login_info` 只读 action 往返通过。反向 WS、长时间断网和进程级
健康检查仍未验收。

### 阶段 2：消息和事件兼容

- 群聊、私聊、文本、图片、@、引用、转发 round-trip。
- recall、poke、成员变更、好友/群邀请按业务需要映射。
- 未支持事件有明确日志和降级，不静默伪装完成。

状态：群/私聊目标、文本、@、@全体、本地引用和 recall notice 已有单测；图片媒体、
合并转发出站及其他 notice/request 仍未完成。2026-07-17 已由独立发送账号通过真实群
消息触发主账号帮助插件并确认回复，基础群文本完成一次 L3 往返。

### 阶段 3：核心服务恢复

- 插件加载报告完整，帮助能列出实际加载插件。
- 权限、余额、冷却、主动插件和消息历史工作。
- scheduler start，programmable 任务走正常分发。
- API 按选定部署模式启动并安全关闭。

状态：registry 可重复 load/reload，当前本地加载 79/2/3 且失败为 0；worker 和 scheduler
已显式 start/stop。主动插件完成双账号 L3 往返；scheduler 的代码/手动主路径、时区、
misfire、单实例和持久化已有测试与 smoke。其他插件同步 I/O 和 Flask API 仍待处理。

### 阶段 4：插件兼容

- 修复上移目录后的 import 和静态路径。
- 按插件域做冒烟；缺可选依赖/数据时可诊断地禁用。
- 替换 Mirai 日志统计和残留命名。

### 阶段 5：部署验收

- 使用 `.env`/runner secret 配置的专用测试账号；当前本机账号的首次扫码和无扫码重启
  已于 2026-07-17 完成，具体值仅记录在 10。
- 代码迁移完成后，按 10 再执行 Docker 自动重启和重建登录，不复用生产数据。
- data/NapCat/QQ volume 重启后持久化。
- healthcheck 能区分进程、NapCat 登录、WS 连接和 worker 健康。
- 日志不含 token/Cookie/webhook 私密数据。

具体任务和优先级只维护在 [TODO.md](../TODO.md)。
登录验收步骤和 CI 安全边界维护在
[10 NapCat 登录自动化验收](./10-napcat-login-test.md)。

当前部署约束：迁移期间只使用本地 NapCat/QQ 进程。Docker 文件可以静态修订，但不得
启动构建、容器或容器登录验收，直到代码迁移完成或用户明确解除约束。

## 使用归档分支

查看旧行为：

```bash
git show origin/archived-mirai2-version:toogle/nonebot2_adapter.py
git show origin/archived-mirai2-version:plugins/toogle.py
git show origin/archived-mirai2-version:toogle/mirai_extend.py
git show origin/archived-mirai2-version:plugins/schedule.py
```

比较单个已迁移文件：

```bash
git diff origin/archived-mirai2-version -- toogle/message.py
git diff origin/archived-mirai2-version -- toogle/scheduler.py
```

业务插件当前从 `toogle/plugins/foo.py` 移到 `plugins/foo.py`。比较时需分别读取两个路径，
不能只对同一路径 diff 后把删除误当成功能删除。

## 完成定义

只有同时满足以下条件，才可在 README 中把迁移标记为完成：

- clean 环境和 Docker 均能启动。
- fixture 和 mock transport 自动测试通过。
- 隔离 NapCat 测试覆盖核心消息/事件矩阵。
- 普通、主动、定时、API 主动发送四条链路均验证。
- 所有顶层插件有加载清单，失败插件有明确原因。
- 源码不再运行时引用 NoneBot/Mirai、旧插件路径或 Mirai 日志。
- 配置、静态资源和运行数据有可重复的 bootstrap/持久化方案。
- `TODO.md` 的 P0/P1 全部关闭，剩余 P2 不影响声明的功能范围。
