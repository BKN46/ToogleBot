# 01 项目总览

ToogleBot 是一个基于 Mirai + NoneBot2 的 QQ 机器人项目。项目在 NoneBot2 之上实现了自己的轻量业务插件框架，让大多数业务功能通过继承 `MessageHandler`、返回 `MessageChain` 来开发，而不用直接操作 NoneBot matcher。

## 核心定位

- 接入层：Mirai API HTTP + `nonebot-adapter-mirai2`。
- 应用层：根目录 `plugins/` 中的 NoneBot 插件负责装载、帮助、事件后处理和 HTTP API。
- 业务层：`toogle/plugins/` 中的业务插件类负责具体功能。
- 抽象层：`toogle/message.py`、`toogle/message_handler.py`、`toogle/nonebot2_adapter.py` 把 NoneBot/Mirai 消息转换为项目自有对象。

## 关键目录

| 路径 | 作用 |
| --- | --- |
| `bot.py` | NoneBot ASGI 入口，注册 Mirai adapter，加载根目录 `plugins/` 和 `pyproject.toml` 中的插件配置。 |
| `plugins/` | NoneBot 插件入口层。`load.py` 动态注册业务插件 matcher，`toogle.py` 处理帮助、事件后处理和启动/关闭钩子，`schedule.py` 注册定时任务，`api.py` 暴露 FastAPI 接口。 |
| `toogle/` | 项目自有框架与业务主体。包括消息抽象、插件加载、适配器、配置、数据库、调度、工具函数。 |
| `toogle/plugins/` | 业务插件主目录。顶层 `.py` 会被 `toogle/index.py` 动态扫描并导入。 |
| `toogle/plugins/compose/` | 图片/图文渲染、股票、塔罗、AI 作图等辅助组合函数。 |
| `toogle/plugins/others/` | 外部垂直领域辅助库，如 CSGO、塔科夫、天气、微博、硬件、Minecraft。 |
| `toogle/plugins/dnd/` | DND 5E 查询、DPR 计算相关库。 |
| `toogle/plugins/thunderskill/` | 战雷/ThunderSkill 数据查询辅助库。 |
| `toogle/plugins/waifu_utils/` | 随机 ACG 角色、卡牌、战斗等辅助库。 |
| `data/` | 运行时状态、缓存、图片素材、JSON 数据、SQLite 数据库等。 |
| `log/` | 项目自身日志，如调用、错误、慢调用、API、撤回等。 |
| `mirai/` | Mirai Console、插件、日志和配置。 |
| `statistics/` | 离线统计脚本，读取 Mirai 日志或项目调用日志生成词频/调用统计。 |
| `test/` | 实验脚本、外部服务探针、图片/视频样例，不是标准自动化测试套件。 |
| `documents/` | 旧版简短开发说明。 |
| `doc/` | 当前 AI 辅助开发文档。 |

## 启动方式

README 中的常规路径：

1. 在 `mirai/` 下启动 Mirai Console：`./mcl`。
2. 启动 NoneBot：`venv/bin/python -m nb_cli run` 或 `./start.sh`。

当前仓库实际环境特征：

- 系统 `python3` 可能较旧，本工作区检测到是 Python 3.6.8。
- 项目虚拟环境 `./venv/bin/python` 是 Python 3.9.16。
- 源码使用了 Python 3.8+ 语法，例如海象运算符；Dockerfile 也使用 Python 3.9。
- 因此开发和验证优先使用 `./venv/bin/python`，不要默认使用系统 `python3`。

## 插件装载模型

项目有两层插件：

1. 根目录 `plugins/` 是 NoneBot 插件，负责把系统接到 NoneBot。
2. `toogle/plugins/` 是业务插件，负责用户功能。

业务插件加载过程：

1. `toogle/index.py` 扫描 `toogle/plugins/` 下的顶层 `.py` 文件。
2. 动态 import 后寻找 `MessageHandler`、`ActiveHandler`、`ScheduleModule` 子类。
3. 将普通消息插件包装为 `PluginWrapper` 放进 `export_plugins`。
4. 根目录 `plugins/load.py` 根据 `export_plugins` 为每个业务插件注册 NoneBot `on_regex` matcher。
5. 根目录 `plugins/toogle.py` 在 import 时调用 `load_plugins()`，并注册帮助和事件后处理。
6. 根目录 `plugins/schedule.py` 把 `schedule_plugins` 注册进 APScheduler。

注意：`toogle/plugins/` 下的子目录不会被 `toogle/index.py` 直接扫描成业务插件，通常作为顶层业务插件的辅助库使用。

## 项目状态提示

- `pyproject.toml` 中的 `plugin_dirs = ["src/plugins"]` 与当前目录结构不完全一致；实际入口靠 `bot.py` 里的 `nonebot.load_plugins("plugins")`。
- `pyproject.toml` 声明 Python `^3.7.3`，但源码实际需要 Python 3.8+，推荐按 Python 3.9 处理。
- `requirements.txt` 是实际依赖清单，含 `nonebot2==2.0.0rc1`、`nonebot-adapter-mirai2==0.0.22`、`APScheduler`、`Pillow`、`tensorflow/opennsfw2` 等。
- 大量功能依赖外部网站、Cookie、API Key、Mirai HTTP API、数据缓存，不能只靠单元测试判断全部可用。

