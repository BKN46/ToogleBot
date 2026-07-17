# 03 消息与插件契约

大多数业务开发都围绕这一组本地契约进行：插件继承 `MessageHandler`，接收 `MessagePack`，返回 `MessageChain`。

## 最小插件模板

```python
from typing import Optional

from toogle.message import MessageChain
from toogle.message_handler import MessageHandler, MessagePack


class HelloPlugin(MessageHandler):
    name = "示例插件"
    trigger = r"^hello$"
    readme = "发送 hello 时回复 world"

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        return MessageChain.plain("world", quote=message.as_quote())
```

放在 `toogle/plugins/<name>.py` 顶层即可被 `toogle/index.py` 扫描。子目录中的类不会自动扫描，除非被顶层插件导入并暴露为模块成员。

## MessagePack

定义在 `toogle/message_handler.py`。

字段：

| 字段 | 含义 |
| --- | --- |
| `id` | Mirai 消息 ID，用于引用、撤回等。 |
| `message` | `toogle.message.MessageChain`。 |
| `group` | `Group(id, name)`，私聊时 `id == 0`。 |
| `member` | `Member(id, name)`，构造时会用 `data/user_info.json` 中昵称覆盖。 |
| `quote` | 可选 `Quote`。 |
| `time` | 本地接收时间戳。 |

常用方法：

- `message.as_quote()`：生成当前消息的引用对象，常用于回复。
- `message.to_dict()`：调试/持久化用。

## MessageChain

定义在 `toogle/message.py`，表示一条项目内部消息。

常用创建方式：

```python
MessageChain.plain("文本")
MessageChain.plain("文本", quote=message.as_quote())
MessageChain.create([Plain("文本"), At(target=qq), Image(path="data/a.png")])
ForwardMessage.get_quick_forward_message([MessageChain.plain("第一条")])
```

常用方法：

- `asDisplay()`：把消息链转为可用于正则/日志/LLM 的文本显示。
- `get(Plain)`、`get(Image)`、`get(At)`：提取指定元素。
- `get_quote()`：从消息链中取 Quote ID。
- `to_mirai()`：转为 Mirai API 结构，主要给扩展函数使用。

控制字段：

- `no_interval=True`：返回后不记录插件冷却。
- `no_charge=True`：返回后不扣余额。

示例：

```python
return MessageChain.plain("余额不足", quote=message.as_quote(), no_charge=True, no_interval=True)
```

## 消息元素

定义在 `toogle/message.py`。

| 元素 | 用途 |
| --- | --- |
| `Plain(text)` | 文本。 |
| `At(target)` | @ 单个 QQ。 |
| `AtAll()` | @ 全体。 |
| `Image(path=...)` | 本地图片。 |
| `Image(url=...)` | 网络图片 URL。 |
| `Image(bytes=...)` | 图片字节，内部转 base64。 |
| `Image(image=PIL.Image.Image)` | PIL 图片对象。 |
| `Quote(...)` | 引用消息。 |
| `ForwardMessage(...)` | 合并转发。 |
| `Xml(xml)` | Mirai XML 消息。 |

图片注意事项：

- `Image.getBytes()` 会读取本地文件或请求 URL。
- `Image.getBase64()` 会缓存 base64。
- `Image.compress()` 可压缩图片再返回新的 `Image`。
- 发送本地图片时常用 `Image.fromLocalFile(path)`。

## MessageHandler 类属性

定义在 `toogle/message_handler.py`。

| 属性 | 默认值 | 作用 |
| --- | --- | --- |
| `name` | `"BKN的聊天机器人组件"` | 插件展示名、日志名、帮助名。 |
| `trigger` | `r""` | NoneBot `on_regex` 和二次校验使用的正则。 |
| `readme` | 默认说明 | 帮助文本。 |
| `admin_only` | `False` | 仅管理员可触发。 |
| `interval` | `0` | 用户级冷却秒数，成功返回且未 `no_interval` 时生效。 |
| `price` | `0` | gb 价格，成功返回且未 `no_charge` 时扣费。 |
| `to_me_trigger` | `False` | 是否额外注册 @ 机器人触发。 |
| `ignore_quote` | `False` | 是否忽略引用消息拼接。 |
| `white_list` | `False` | 历史属性，当前核心分发未完整使用。 |
| `thread_limit` | `False` | 历史属性/自描述，当前 worker 队列未按此属性限流。 |

## ret 返回值约定

`ret(self, message)` 应为 async 方法，返回：

- `MessageChain`：发送给用户。
- `None`：静默，不发送，不扣费，不记录调用成功。
- 空 `MessageChain([])`：worker 里 `res.root` 为空时不发送，但仍可能已通过“返回非空对象”进入冷却/扣费逻辑；通常不建议用于静默。

建议：

- 不触发或输入不完整时返回 `None`。
- 用户可见错误返回 `MessageChain.plain(..., no_charge=True, no_interval=True)`。
- 成功业务返回普通 `MessageChain`。
- 需要引用原消息时使用 `quote=message.as_quote()`。

## 引用消息拼接

`PluginWrapper.ret()` 中有一个前置行为：

```python
if message_pack.quote and not self.plugin.ignore_quote:
    message_pack.message += message_pack.quote.message
```

这意味着用户“回复一条消息再触发插件”时，插件看到的 `message.message.asDisplay()` 可能是当前命令文本 + 被引用消息文本。

如果插件需要严格解析当前消息，设置：

```python
ignore_quote = True
```

或在 `ret()` 中显式读取 `message.quote`。

## 余额和冷却

余额逻辑：

- `price > 0` 且群号在 `config["ECO_GROUP"]` 时，执行前检查余额。
- 插件成功返回且未设置 `no_charge` 时扣费。
- 管理员不受余额限制。

冷却逻辑：

- `interval > 0` 时执行前检查 `interval_limiter.user_interval()`。
- 插件成功返回且未设置 `no_interval` 时记录冷却。
- 管理员和管理员群可绕过冷却检查。

## 权限和封禁

管理员：

- `toogle.utils.is_admin()` 读取 `config["ADMIN_LIST"]`。
- `admin_only = True` 会在框架层拦截非管理员。
- 插件中仍常见二次 `is_admin()` 检查，这是项目现有风格。

黑名单/禁用：

- `config["BLACK_LIST"]` 会全局拦截成员。
- `toogle.nonebot2_adapter.MUTE_LIST` 支持临时禁用某用户或某功能。
- `data/traffic_control.py` 如果存在，可按插件名和群号分时段禁用。

## 主动插件 ActiveHandler

`ActiveHandler` 适合在普通消息后处理里随机插话。

加载位置：

- `toogle/index.py` 扫描 `ActiveHandler` 子类并加入 `active_plugins`。
- `plugins/toogle.py` 的 `message_post_process` 在 `config["CHAT_GROUP_LIST"]` 群中调用。

关键属性：

- `trigger_rate`：随机触发概率。
- `is_trigger_random()`：可重写实现更复杂触发。
- `ret_wrapper()`：捕获异常并记录日志。

当前 `ActiveAIConversation.is_trigger_random()` 开头直接 `return False`，所以实际禁用。

## 定时插件 ScheduleModule

定义在 `toogle/scheduler.py`。

用于 cron 式任务，类属性映射 APScheduler cron 参数：

- `year`
- `month`
- `week`
- `day_of_week`
- `day`
- `hour`
- `minute`
- `second`

实现：

```python
class MyJob(ScheduleModule):
    name = "示例定时任务"
    hour = 9
    minute = 0

    async def ret(self, message_pack):
        bot_send_message(123456, "早上好")
```

如果 `ScheduleModule` 同时定义 `trigger`，它也会被包装成普通消息插件，适合“定时自动执行 + 手动查询”双模式。

## 等待用户后续输入

`WaitCommandHandler` 会轮询 `MESSAGE_HISTORY`，等待同群同用户发出匹配正则的新消息。

典型用法见 `AnimeDownloadSearch`：

```python
waiter = WaitCommandHandler(message.group.id, message.member.id, r"^翻页|^下载", timeout=120)
res = await waiter.run()
```

注意：

- 它依赖 `plugins/toogle.py` 的 postprocessor 把消息写入 `MESSAGE_HISTORY`。
- 它是轮询，不是 matcher 级会话状态。
- 多个并发等待同一用户同一正则时可能互相影响。

