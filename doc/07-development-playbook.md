# 07 开发任务指南

本文是给未来 AI/开发者的执行手册：收到需求后，如何定位、修改、验证，并避免破坏运行数据。

## 开始前检查

每次改代码前先做：

```bash
git status --short
```

原则：

- 不要覆盖他人未提交改动。
- 只改需求相关文件。
- 涉及运行数据时，先确认是否真要改 `data/` 或 `log/`。
- 默认不要读取或输出 `.env` 中的敏感值。

推荐 Python：

```bash
./venv/bin/python --version
```

原因：

- 系统 `python3` 可能是 3.6，无法解析当前源码中的 Python 3.8+ 语法。
- 项目虚拟环境当前是 Python 3.9，和 Dockerfile 一致。

## 常见任务定位

| 需求 | 优先读 |
| --- | --- |
| 新增普通聊天命令 | `doc/03-message-and-plugin-contract.md`，再选 `toogle/plugins/*.py`。 |
| 修改现有功能 | `doc/05-plugin-map.md` 找文件，再读具体类。 |
| 改消息收发、图片、转发、@ | `toogle/message.py`、`toogle/nonebot2_adapter.py`。 |
| 改插件加载或热重载 | `toogle/index.py`、`plugins/load.py`。 |
| 改帮助输出 | `plugins/toogle.py` 的 `handle_help()`。 |
| 改权限/计费/冷却 | `toogle/nonebot2_adapter.py`、`toogle/economy.py`、`toogle/configs.py`。 |
| 改定时任务 | `toogle/scheduler.py`、`toogle/plugins/schedule.py`、`plugins/schedule.py`。 |
| 改 HTTP API | `plugins/api.py`、`toogle/message.json_to_msg()`。 |
| 改图片识别 | `toogle/tools/pic_recognition.py`、`toogle/msg_proc.py`。 |
| 改数据库字段 | `sqlite.sql`、`toogle/sql.py`、调用方。 |
| 改外部站点解析 | 目标业务插件和 `toogle/plugins/others/` 或 `compose/` 对应辅助库。 |

## 新增普通插件流程

1. 选择合适文件：
   - 简单群互动：`toogle/plugins/basic.py`。
   - 查询工具：`toogle/plugins/tools.py`。
   - 垂直游戏/站点工具：`toogle/plugins/other.py` 或新增顶层文件。
   - 完全独立功能：新增 `toogle/plugins/<feature>.py`。
2. 写一个 `MessageHandler` 子类。
3. 设置 `name`、`trigger`、`readme`。
4. 根据需要设置 `price`、`interval`、`admin_only`、`ignore_quote`。
5. `ret()` 返回 `MessageChain` 或 `None`。
6. 用 `./venv/bin/python -m py_compile <文件>` 验证语法。

模板：

```python
from typing import Optional

from toogle.message import MessageChain
from toogle.message_handler import MessageHandler, MessagePack


class MyFeature(MessageHandler):
    name = "我的功能"
    trigger = r"^我的命令\s+(.+)$"
    readme = "说明用户怎么触发"
    interval = 10
    price = 0

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        content = message.message.asDisplay()
        # parse content here
        return MessageChain.plain("结果", quote=message.as_quote())
```

## 插件返回策略

建议：

- 输入与当前插件不匹配：`return None`。
- 用户参数错误：返回可见提示，并设置 `no_charge=True`、`no_interval=True`。
- 外部服务失败：返回简短错误，并通常设置 `no_charge=True`。
- 业务成功：返回普通 `MessageChain`。
- 需要先发处理中提示：用 `bot_send_message(message, "...")`，最后再返回结果或 `None`。

示例：

```python
if not keyword:
    return MessageChain.plain("请输入关键词", quote=message.as_quote(), no_charge=True, no_interval=True)
```

## 解析消息的建议

优先：

- 用插件 `trigger` 中的正则解析。
- 在 `ret()` 里再次 `re.match(self.trigger, message.message.asDisplay())`。
- 用 `message.message.get(Image)`、`get(At)` 等读取非文本元素。

注意：

- 如果用户引用了消息，默认会把引用消息拼到当前消息后面。
- 严格命令解析类插件应考虑 `ignore_quote = True`。
- `asDisplay()` 会把图片显示为 `[图片]`，转发显示为摘要文本。

## 发送复杂消息

文本：

```python
MessageChain.plain("hello")
```

引用回复：

```python
MessageChain.plain("hello", quote=message.as_quote())
```

图文：

```python
from toogle.message import Image, Plain

MessageChain.create([
    message.as_quote(),
    Plain("结果如下：\n"),
    Image(bytes=img_bytes),
])
```

合并转发：

```python
from toogle.message import ForwardMessage, MessageChain

return ForwardMessage.get_quick_forward_message([
    MessageChain.plain("第一段"),
    MessageChain.plain("第二段"),
])
```

主动分段发送：

```python
from toogle.nonebot2_adapter import bot_send_message

bot_send_message(message, MessageChain.plain("处理中..."))
```

## 状态存储选择

| 场景 | 推荐 |
| --- | --- |
| 用户少量偏好/插件小状态 | `modify_json_file("name")`。 |
| 用户长期结构化数据 | SQLite `qq_user.data` 或新表。 |
| 大量图片/二进制素材 | `data/<feature>/` 目录。 |
| 临时缓存 | `data/buffer/` 或插件专属目录。 |
| 只需进程内短期状态 | 模块全局 dict/list。 |

注意：

- JSON 状态适合简单结构，不适合高并发大文件。
- SQLite 当前 wrapper 不是强类型 ORM，字段索引易错。
- pickle 文件不适合跨版本结构演进和人工编辑。

## 外部 API/爬虫修改

常见文件：

- `toogle/plugins/tools.py`
- `toogle/plugins/other.py`
- `toogle/plugins/compose/stock.py`
- `toogle/plugins/others/*.py`

建议：

- 请求失败要有用户可见错误，不要让异常一路发给管理员。
- 对 HTML 解析增加空值判断。
- 保留或使用 `config.proxies`。
- 对需要 Cookie 的功能，确认更新 Cookie 的管理员命令。
- 不要在文档或日志里输出完整 Cookie/API Key。

## 调度任务修改

新增代码型定时任务：

1. 在 `toogle/plugins/schedule.py` 添加 `ScheduleModule` 子类。
2. 设置 `name` 和 cron 类属性。
3. 实现 `async def ret(self, message_pack)`。
4. 如果希望用户也能手动触发，设置 `trigger` 并兼容 `message_pack` 非空。

修改手动定时任务：

- 看 `CreateSchedule`。
- 看 `toogle/scheduler.py` 的 `load_manual_schedular()`。
- 数据在 `data/schedule.json`。

## 验证方式

最低限度语法检查：

```bash
./venv/bin/python -m py_compile path/to/file.py
```

多文件语法检查：

```bash
./venv/bin/python -m compileall toogle plugins
```

静态查找插件：

```bash
rg -n "^class .*\\((MessageHandler|ActiveHandler|ScheduleModule)\\)" toogle/plugins -g "*.py"
```

启动前快速检查：

```bash
./venv/bin/python -m nb_cli run
```

注意：

- 本项目依赖 Mirai、`.env`、外部服务和运行数据；本地启动可能因缺少服务而失败。
- 不要为了验证随意触发真实群管理操作。
- 修改外部爬虫时，必要时只运行纯解析函数或对保存的 HTML 样本测试。

## 常见坑

### 系统 Python 版本过低

不要用裸 `python3` 做语法判断。当前系统 Python 可能是 3.6，会误报海象运算符等语法错误。用：

```bash
./venv/bin/python
```

### 顶层 import 有副作用

很多模块 import 时会：

- 读取 `.env`。
- 读取 `data/` 文件。
- 创建目录或 BloomFilter 文件。
- 导入重型依赖。
- 动态加载所有插件。
- 启动 worker 线程。

因此做静态分析时优先用 `rg`、`sed`、`ast.parse`，避免随意 `import toogle.index`。

### `toogle/plugins/` 子目录不会自动注册

如果新增 `toogle/plugins/foo/bar.py`，其中的 `MessageHandler` 不会自动变成插件。要么放在顶层 `.py`，要么由顶层模块导入并暴露。

### 引用消息会改变命令文本

默认会拼接引用原文。严格正则解析时设置：

```python
ignore_quote = True
```

### 成功返回才扣费/冷却

框架在 worker 里根据返回结果处理扣费/冷却。错误提示要不要扣费由 `no_charge` 和 `no_interval` 控制。

### `MessageChain([])` 不等于最佳静默

静默最好 `return None`。空消息链仍是一个对象，可能影响冷却/扣费逻辑。

### SQL wrapper 不是安全 ORM

不要把用户输入直接拼进 SQL 片段，尤其是 `update_user(id, content)`。

### JSON 文件只进程内加锁

`modify_json_file()` 对多线程有锁，对多进程没有跨进程锁。Docker/生产配置中 `MAX_WORKERS=1` 与此相关。

### 外部请求可能阻塞 worker

worker 线程池默认 10 个。长耗时请求、长模拟、睡眠会占用 worker。需要长任务时考虑：

- 先 `bot_send_message()` 告知处理中。
- 分段发送。
- 设置合理 timeout。
- 避免无限等待。

### `thread_limit` 当前不是完整限流

不少插件设置 `thread_limit = True`，但核心 worker 队列没有按此属性做单插件串行化。不要依赖它保证互斥。

## 修改后交付说明建议

最终说明应包含：

- 改了哪些文档/代码文件。
- 用户可感知行为有什么变化。
- 运行了哪些验证命令。
- 哪些验证因为缺少 Mirai、密钥、外部服务而没有运行。

示例：

```text
已在 toogle/plugins/tools.py 中调整 AnimeDownloadSearch 的空结果处理，并补充了外部站点解析的空值保护。
验证：./venv/bin/python -m py_compile toogle/plugins/tools.py。
未实际请求 DMHY，因为当前环境不应依赖外网结果作为通过条件。
```

