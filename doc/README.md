# ToogleBot 渐进式开发文档

这套文档面向后续 AI 和开发者，以当前 NapCat 迁移工作树为准。源码仍是最终事实
来源；Mirai 时代的行为可从 `origin/archived-mirai2-version` 核对。

## 阅读路径

1. [01 项目总览](./01-project-overview.md)：建立目录和架构地图。
2. [02 运行链路](./02-runtime-flow.md)：理解启动、收发、插件执行和关闭。
3. [03 NapCat 适配层](./03-napcat-adapter.md)：修改 OneBot/WebSocket 前必读。
4. [04 消息与插件契约](./04-message-plugin-contract.md)：新增或修改插件前必读。
5. [05 业务插件地图](./05-plugin-map.md)：按功能定位文件和依赖。
6. [06 配置、数据与持久化](./06-config-data-persistence.md)：修改配置或状态前必读。
7. [07 调度、API 与共享服务](./07-shared-services.md)：跨模块能力和高影响入口。
8. [08 开发与验证手册](./08-development-playbook.md)：执行任务时的操作清单。
9. [09 迁移指南](./09-migration-guide.md)：Mirai 到 NapCat 的边界和完成标准。
10. [10 NapCat 登录自动化验收](./10-napcat-login-test.md)：测试账号首次授权、自动重启登录和 CI 方案。

迁移工作的唯一任务清单是根目录 [TODO.md](../TODO.md)。文档中的风险说明用于解释
上下文，不另建一份可能失真的 TODO。

## 按任务快速进入

| 任务 | 先读 | 主要代码 |
| --- | --- | --- |
| 修启动、断线或收发消息 | 02、03、09 | `bot.py`、`adapter/` |
| 新增聊天命令 | 04、05 | `plugins/*.py` |
| 修改消息元素、图片、引用、转发 | 03、04 | `toogle/message.py`、`adapter/msg_queue.py` |
| 修改插件发现、限流、计费 | 02、04、07 | `toogle/index.py`、`toogle/adapter.py`、`adapter/worker.py` |
| 修改定时任务 | 02、07 | `toogle/scheduler.py`、`plugins/schedule.py` |
| 修改外部 HTTP API | 07 | `api/api.py` |
| 修改配置或部署 | 06、08 | `configs.py`、`pyproject.toml`、Docker 文件 |
| 验证 NapCat 登录、双账号消息和持久化 | 03、08、10 | `tools/napcat_login_check.py`、`tools/napcat_dual_account_check.py`、Docker 文件 |
| 修某个外部站点或游戏功能 | 05、06 | 对应 `plugins/` 文件和辅助目录 |

## 状态用语

- **当前实现**：源码已经存在，不代表端到端已验证。
- **目标契约**：迁移完成后必须满足的行为。
- **已验证**：有本地命令或测试结果支撑。
- **待迁移**：已在 `TODO.md` 登记，未来修改不能假设其可用。

截至 2026-07-17，源码可通过 Python 3.12 语法编译，uv 根包发现阻断已消除，基础群
文本与主动插件完成本地双账号往返；依赖分层、媒体/事件/API 和 Docker 仍有阻断项，
不能把这些局部验收等同于迁移完成。
