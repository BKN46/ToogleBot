# ToogleBot AI 开发文档入口

本文档集用于帮助未来 AI 或人类开发者快速理解 ToogleBot。它不是替代源码的完整注释，而是把项目的运行链路、模块边界、常见修改入口和风险点整理成渐进式阅读路径。

## 推荐阅读顺序

1. [01-项目总览](./01-project-overview.md)
   先建立项目是什么、从哪里启动、核心目录如何分工的全局地图。
2. [02-运行链路](./02-runtime-flow.md)
   理解 NoneBot/Mirai 事件如何进入本地框架、如何匹配插件、如何发送回复。
3. [03-消息与插件契约](./03-message-and-plugin-contract.md)
   写新插件或改插件前必读，覆盖 `MessagePack`、`MessageChain`、`MessageHandler`、权限、计费、限流等约定。
4. [04-配置数据与持久化](./04-config-data-persistence.md)
   了解 `.env`、SQLite、`data/*.json`、日志和缓存分别由谁读写。
5. [05-业务插件地图](./05-plugin-map.md)
   按功能域定位业务插件和辅助库。
6. [06-共享服务与工具](./06-shared-services.md)
   查询通用工具、图像处理、调度、外部 API、统计脚本。
7. [07-开发任务指南](./07-development-playbook.md)
   给 AI 执行具体任务时使用的路径、验证方式和注意事项。

## 给未来 AI 的最短路径

如果只需要完成一个小改动：

1. 先读本文件和 [03-消息与插件契约](./03-message-and-plugin-contract.md)。
2. 用 [05-业务插件地图](./05-plugin-map.md) 找到目标插件文件。
3. 检查目标插件是否依赖 [04-配置数据与持久化](./04-config-data-persistence.md) 中的配置、数据文件或数据库。
4. 修改后至少运行 `./venv/bin/python -m py_compile <改动文件>`。

如果要改事件接入、消息格式、调度、发送队列或插件加载：

1. 读 [01-项目总览](./01-project-overview.md)。
2. 读 [02-运行链路](./02-runtime-flow.md)。
3. 读 [03-消息与插件契约](./03-message-and-plugin-contract.md)。
4. 再进入具体源码。

## 文档边界

- `/doc` 是新的 AI 辅助开发文档目录。
- 旧目录 `/documents` 仍保留历史性的简短插件说明。
- 文档尽量基于当前源码整理；源码仍是最终事实来源。
- 本项目当前工作区可能有未提交改动，未来 AI 修改时应先看 `git status --short`，避免覆盖他人工作。

