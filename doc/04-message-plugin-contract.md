# 04 消息与插件契约

这组对象是接入层与业务插件之间的稳定边界。修改它们会影响几乎所有功能。

## MessagePack

定义在 `toogle/message_handler.py`，表示一次已解析的用户消息：

| 字段 | 含义 |
| --- | --- |
| `id` | 平台消息 ID，用于引用和撤回。 |
| `message` | `MessageChain` 正文。 |
| `group` | `Group(id, name)`；私聊目标约定见 03。 |
| `member` | `Member(id, name)` 发送者。 |
| `quote` | 可选 `Quote`，用于插件读取被引用原文。 |
| `time` | 本地接收时间戳。 |
| `message_type` | `group` 或 `private`。 |

构造时会调用 `get_user_name()`，优先采用 `data/user_info.json` 中用户设置的昵称。
`as_quote()` 用当前消息构造回复引用。

## MessageChain 和元素

`toogle/message.py` 的 `MessageChain` 是有序元素序列，常用元素如下：

| 元素 | 主要字段 | `asDisplay()` |
| --- | --- | --- |
| `Plain` | `text` | 原文本。 |
| `Markdown` | `content` | 原始 Markdown 内容。 |
| `JsonCard` | `data`（JSON 字符串或对象） | `[卡片消息]`。 |
| `At` | `target` | `@<QQ>`。 |
| `AtAll` | 无 | `@all`。 |
| `Image` | `id/path/url/base64/cache` | `[图片]`。 |
| `Quote` | message id、发送者、群、原消息 | 带原文的引用描述。 |
| `ForwardMessage` | 节点列表和摘要信息 | 合并节点正文摘要。 |
| `Xml` | `xml` | `[xml message]`。 |

常用构造：

```python
MessageChain.plain("hello")
MessageChain.plain("hello", quote=message.as_quote())
MessageChain.create([Plain("结果：\n"), Image(bytes=png_bytes)])
MessageChain.create([Markdown("# 标题\n\n- 列表项")])
MessageChain.create([JsonCard(ark_data)])
ForwardMessage.get_quick_forward_message([
    MessageChain.plain("第一段"),
    MessageChain.plain("第二段"),
])
```

`no_interval` 和 `no_charge` 属于返回链元数据，控制 worker 是否记录冷却和扣费。
`MessageChain.plain(..., quote=...)` 和消息链相加现在都会保留两个 flags。

未使用的 Mirai 消息序列化器已经删除。平台出站转换只允许位于
`adapter/msg_queue.py::toogle2nb()`，业务插件不得自行构造 Mirai/OneBot payload。
`Markdown` 在适配层固定映射到 `type=markdown` / `data.content`；不要把 Markdown 文本
包装成 `Plain` 来冒充富文本，也不要在插件内手写 OneBot segment。

`JsonCard` 已进入稳定契约：构造时只接受能解析为 JSON object 的字符串或可序列化对象，
对象会深拷贝，`asDisplay()` 和 `to_dict()` 不输出正文；适配层固定映射到
`type=json` / `data.data`。插件应使用 NapCat action 或可信结构化数据生成卡片，不能拼接
包含用户输入的 JSON 字符串。

NapCat 4.18.9 还公开表情、语音、视频、文件、音乐、联系人、位置、在线文件和闪传等
类型，但它们尚未进入本项目稳定契约。新增时按以下边界处理：

- `JsonCard` 不在业务层暴露 `ElementType.ARK` 等 NapCat 类型；链接分享、位置、音乐和
  小程序接收时都可能复用它。
- `Face`/`MarketFace` 保存平台 ID 和显示摘要；骰子、猜拳结果不能只压成 Plain。
- `Record`/`Video`/`File` 复用统一资源来源约定，但保留不同元素类型和媒体字段。
- `ForwardMessage` 负责 node 层级；`node` 不是插件可以单独返回的顶层元素。
- `Poke`、群签到、AI 语音属于事件或 action，不放进通用 `MessageChain`。
- `OnlineFile`/`FlashTransfer` 有独立生命周期和 action，不与普通 `File` 合并。
- 小程序 Ark 由适配层调用 `get_mini_app_ark` 生成，再转换为 `JsonCard`；插件不得直接
  依赖 packet schema。

官方兼容表说明 Markdown 不能直接发送，只能嵌在双层合并转发中。当前 `Markdown`
类型由适配层递归转换为节点正文中的标准段；插件仍只构造 `ForwardMessage`，不能自行拼
OneBot 双层 payload 绕过适配层。顶层 `ForwardMessage` 不能与普通消息段混发。

## 消息历史

`MessageHistory` 管理一个 `key -> list[MessagePack]` 映射：

- `MESSAGE_HISTORY`：常规消息、色图等后处理记录。
- `RECALL_HISTORY`：撤回消息，供“反撤回”插件查询。
- `WaitCommandHandler`：轮询最近历史，等待同群同用户的后续输入。

历史默认窗口为 500，关机保存到 `HISTORY_SAVE_PATH` 或 `data/history.pkl`。key 多数
是群号，也存在 `setu_<group>` 一类字符串命名空间。

注意：pickle 只能加载可信文件；结构变化可能使旧历史无法反序列化。当前启动钩子在
加载失败时重写历史文件，未来重构应先备份或使用可迁移格式，避免静默数据丢失。

## 三种插件类型

### MessageHandler

普通命令插件。常用类属性：

| 属性 | 默认值 | 作用 |
| --- | --- | --- |
| `name` | 通用名称 | 帮助、日志、限流和禁用使用。 |
| `trigger` | 空正则 | 命令触发条件。 |
| `readme` | 通用说明 | 帮助展示。 |
| `admin_only` | `False` | 仅管理员。 |
| `interval` | `0` | 用户级冷却秒数。 |
| `price` | `0` | 成功调用价格。 |
| `ignore_quote` | `False` | 是否不把引用原文拼入命令。 |
| `white_list`、`thread_limit`、`to_me_trigger` | `False` | 旧框架遗留属性，当前分发未完整实现。 |

### ActiveHandler

主动插件按 `trigger_rate` 对每条消息随机触发，由 `adapter/post_process.py` 在
`CHAT_GROUP_LIST` 中执行。异常只写 logger，不进入普通 worker 异常通道。

### ScheduleModule

定时插件使用类属性描述 cron，`ret(None)` 处理自动触发。若同时定义非空 `trigger`，
也会被包装成普通插件，此时 `ret(message_pack)` 必须兼容非空参数。

## Registry 契约

目标 loader 应满足：

- 每次发现都从基于 `Path(__file__)` 的顶层 `plugins/*.py` 重新生成并排序候选列表。
- 只注册定义于当前模块的类；唯一标识使用 `module + qualname`，不能只按类名去重。
- 每个模块和每个插件构造都有独立 error boundary，输出 loaded/disabled/failed 及原因。
- 构建新 registry 时不修改在线列表；完整成功后原子替换快照，worker 对一条消息始终
  使用同一版本。
- reload 必须明确是重新执行模块还是只重建实例，不能首次 import 后无条件执行第二次。
- loader 不启动线程、scheduler、网络请求或 QQ 连接；这些由 `bot.py` 生命周期显式管理。

当前 loader 已满足发现、身份、错误报告、临时 build、显式 load/reload 和无 worker
副作用这些条件。帮助插件通过只读 provider 获取当前快照。剩余工作是减少业务模块
import I/O、建立预期插件 manifest，并把指定 reload 优化成真正的单模块事务。

管理员 `.reload` 是当前运行时刷新入口：先重新读取根 `.env`，再重建普通、主动和定时
插件 registry，最后 reconcile APScheduler 中的代码型任务。它不会绕过插件加载错误边界，
也不会把配置值或异常正文发回聊天。非管理员在 `PluginWrapper` 权限层即被静默拒绝。

## 普通插件执行契约

`adapter/worker.py` 和 `toogle/adapter.py` 共同完成：

1. 群聊命中 `ONLY_READ` 时在后处理及插件分发前静默丢弃。
2. 正则粗匹配。
3. 余额检查：仅 `ECO_GROUP` 中对非管理员生效。
4. 用户冷却检查；管理员和管理员群可绕过。
5. `admin_only`、黑名单、临时禁用、分时流量控制。
6. 默认把 `message.quote.message` 追加到正文。
7. 执行 `plugin.ret()`。
8. 根据结果记录冷却、扣费、发送和日志。

第 6 步描述的是旧业务语义，不代表允许修改原对象。实现必须为当前插件构造派生
`MessagePack`/`MessageChain`；同一条引用消息命中多个插件时，每个插件最多看到一份
引用原文，历史和后处理始终保留规范化后的原始消息。

插件应返回：

- 成功：非空 `MessageChain`。
- 无需响应或实际未命中：`None`。
- 参数错误/外部失败：可见 `MessageChain`，通常设置 `no_charge=True`，按产品语义
  决定 `no_interval`。

计费插件只有在取得可用业务结果后才应扣费。当前 `.gpt` 和“查一下”在输入不合法、
上下文/能力缺失、模型超时或服务异常时均返回 `no_charge=True, no_interval=True`；worker
层测试确认这两个 flag 会分别跳过余额扣除和冷却写入。

空 `MessageChain([])` 当前会按静默处理且不扣费、不写冷却；新插件仍优先返回 `None`，
语义更明确。

## 插件模板

```python
import re
from typing import Optional

from toogle.message import MessageChain
from toogle.message_handler import MessageHandler, MessagePack


class Lookup(MessageHandler):
    name = "示例查询"
    trigger = r"^查询\s+(.+)$"
    readme = "查询 <关键词>"
    interval = 10
    price = 2
    ignore_quote = True

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        matched = re.fullmatch(self.trigger, message.message.asDisplay().strip())
        if not matched:
            return None
        keyword = matched.group(1).strip()
        if not keyword:
            return MessageChain.plain(
                "请输入关键词",
                quote=message.as_quote(),
                no_charge=True,
                no_interval=True,
            )
        return MessageChain.plain(f"结果：{keyword}", quote=message.as_quote())
```

## 迁移期注意

- worker 和 `MessageHandler.is_trigger()` 已统一使用 `re.search()`；非锚定 trigger 仍需按
  插件补业务回归。
- 当前明确保留一条消息扫描全部插件、允许多命中的语义；registry 顺序稳定但插件不应
  依赖另一个插件先执行。
- 私聊回复和 quote 派生视图已有单测；合并转发出站已覆盖 node/action fixture，真实账号
  投递及完整 notice/request 仍未完成。
- plugin registry 连续 load/reload 和帮助页 smoke 已通过；顶层网络请求或重型文件读取
  仍必须逐步迁出 import 阶段。
