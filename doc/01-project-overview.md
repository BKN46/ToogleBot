# 01 项目总览

ToogleBot 是一个以 QQ 群聊为主要场景的多功能机器人。业务层拥有自己的消息模型、
插件基类、经济系统、调度和持久化，因此接入框架可以替换。目前仓库正在从
Mirai + NoneBot2 迁移到 NapCat + OneBot 11，并用原生 WebSocket/HTTP 接入。

## 分层

```text
NapCat / OneBot 11
        |
        v
adapter/                 协议和运行时边界
        |
        v
toogle/                  内部消息、插件策略、调度、经济和数据服务
        |
        v
plugins/                 业务命令、主动插件、定时插件
        |
        +--> plugins/*/  业务辅助库和静态资源
        +--> tools/      通用图像识别与字体
```

核心设计目标是让 `plugins/` 只处理 `MessagePack` / `MessageChain`，不感知
OneBot payload。迁移是否成功，应以这个隔离边界和端到端行为是否恢复为准。

## 根目录入口

| 路径 | 当前职责 | 状态提示 |
| --- | --- | --- |
| `bot.py` | 显式加载 registry/queue/worker/scheduler，并发运行 WebSocket 与消息分发，统一关闭。 | 基础生命周期已接通；API 和进程健康检查待补。 |
| `configs.py` | 从 `.env` 载入连接和业务配置。 | 解析方式及旧 key 仍待迁移。 |
| `pyproject.toml` / `uv.lock` | Python 3.12 非打包应用及依赖。 | uv 根包发现已修复；直接/可选依赖清单尚未闭合。 |
| `Dockerfile` / `entrypoint.sh` | 目标是在同一容器中启动 Linux QQ、NapCat 和 ToogleBot。 | 配置生成、构建上下文和健康检查待补；当前阶段不运行 Docker。 |
| `docker-compose.yml` | 目标是暴露 NapCat WebUI/HTTP/WS，挂载配置和运行数据。 | 端口与 `.env` 契约需统一，代码迁移完成后再验收。 |
| `sqlite.sql` | `qq_user`、`qq_user_membership` 等数据库结构参考。 | 运行代码默认使用 `data/toogle.db`。 |
| `TODO.md` | 迁移任务、优先级和验收条件。 | 迁移工作的唯一清单。 |

## 代码目录

| 路径 | 职责 |
| --- | --- |
| `adapter/` | WebSocket/HTTP 接入、OneBot 转换、消息队列、worker、后处理和调度注册。 |
| `api/` | Flask webhook 和受密钥保护的主动发送接口；当前未从 `bot.py` 启动。 |
| `toogle/` | 框架无关的消息模型、插件策略、加载器、调度、经济、会员、SQL、日志和工具。 |
| `plugins/` | 动态发现的顶层业务插件，以及 `compose/`、`others/`、`dnd/`、`remake/`、`thunderskill/`、`waifu_utils/` 辅助模块。 |
| `tools/` | 图片识别和字体文件。 |
| `statistics/` | 离线调用统计和词云脚本；旧 Mirai 聊天日志分析器已删除。 |
| `documents/` | 旧的简短插件说明，仅作历史参考。 |
| `doc/` | 当前渐进式 AI 开发文档。 |
| `data/` | 本地运行状态、缓存、素材和数据库；整体被 `.gitignore` 忽略。 |
| `log/`、`logs/` | 旧日志与新 logger 输出；尚未统一。 |

## 插件发现模型

`bot.py` 显式调用 `toogle.index.load_plugins()`，按稳定顺序读取 `plugins/` 顶层 `.py`：

1. 首次 load 只 import 一次；显式 reload 才重新执行已加载模块。
2. 只收集定义在当前顶层模块的 `MessageHandler` 子类，包装成 `PluginWrapper`。
3. 找到 `ActiveHandler` 子类，实例化后加入主动插件列表。
4. 找到 `ScheduleModule` 子类，加入调度列表；同时有 `trigger` 时也可手动触发。
5. 按 `config["DISABLED_MODULE"]` 中的类名跳过插件。
6. 核心失败阻止发布；成功后一次替换 registry snapshot。

子目录不会被递归扫描，导入到顶层模块的外部类也不会注册。可发现插件类必须直接定义
在 `plugins/*.py`；子目录只承载辅助实现。

## 归档分支的正确用途

`origin/archived-mirai2-version` 保存完整 Mirai/NoneBot2 实现。只读取其中的代码和提交
差异核对旧业务行为；该分支文档属于另一套架构，不作为迁移事实来源，也不迁入当前文档。
它适合回答：

- 旧事件怎样转换成 `MessagePack`。
- 旧发送函数怎样处理群聊、私聊、图片、引用和转发。
- 旧生命周期何时加载插件、启动调度、保存历史。
- 某插件迁移前使用了什么配置和数据路径。

它不应成为新依赖。迁移代码必须保留业务语义，同时以 OneBot 11/NapCat 的实际
事件和 action 格式重新实现接入。

## 当前完成度

已完成的结构性工作：

- `bot.py` 已去除 NoneBot 启动入口。
- 业务插件从 `toogle/plugins/` 上移到 `plugins/`，多数 import 已同步调整。
- 新增 `adapter/` WebSocket/HTTP 骨架、内部 logger、根配置和 uv 锁文件。
- Mirai 可执行文件、启动脚本、扩展 API 和 NoneBot adapter 已从工作树移除。
- 字体和图片识别工具已移动到根 `tools/`。
- 2026-07-17 本地 NapCat 4.15.4 已使用测试号 `3888217194` 完成首次扫码和无扫码
  重启登录；同日更新到 4.18.9 后两个配置账号均无扫码恢复，HTTP 基础 action 与正向
  WebSocket action 可达。当前本地运行基线已更新为 NTQQ 3.2.28-48517；两个账号继续
  无扫码快速登录，Native PacketBackend 状态检查通过，升级过程未启动 Docker。
- 正向 WebSocket 已完成 JSON 收发、echo action 路由、退避重连和有界队列；只读真实
  action 往返通过。
- plugin registry 连续 load/reload 为 79/2/3 且失败为 0；worker 已改为单 event loop，
  event -> MessagePack -> plugin -> group action 的 mock 闭环通过。
- 本机配置发送账号已在配置群完成普通帮助插件和主动链路探针两条真实往返；具体资源
  ID 只保留在 10 的验收记录中。
- scheduler 已显式 start/stop，3 个代码任务和手动 direct/program/single/error/delete
  主路径已修复并测试。
- `toogle.adapter` 已增加平台无关的群文件上传门面，`bot.py` 在本地 NapCat 生命周期中
  注册 HTTP uploader；豆包视频以临时文件调用该门面并保证清理。

尚不能宣称完成的部分见 `TODO.md`。当前仍缺 clean 构建、版本化 SQLite migration、媒体和
合并转发、完整 notice/request、同步插件 I/O 治理、API 与更多插件域业务冒烟。
