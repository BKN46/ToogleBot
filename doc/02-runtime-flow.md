# 02 运行链路

本文解释一条群消息从 Mirai 进入 ToogleBot，到业务插件执行并发送回复的完整路径。

## 启动阶段

入口：`bot.py`

1. `nonebot.init()` 初始化 NoneBot。
2. `nonebot.get_asgi()` 暴露 ASGI app。
3. `driver.register_adapter(MiraiAdapter)` 注册 Mirai2 adapter。
4. `nonebot.load_plugins("plugins")` 加载根目录 NoneBot 插件：
   - `plugins/load.py`
   - `plugins/toogle.py`
   - `plugins/schedule.py`
   - `plugins/api.py`
5. `nonebot.load_from_toml("pyproject.toml")` 按 TOML 额外加载插件配置。

关键副作用：

- import `toogle.index` 时会执行 `reload_plugins()`，扫描并导入 `toogle/plugins/*.py`。
- import `toogle.nonebot2_adapter` 时会启动 worker 线程池：`worker_start()`。
- import `plugins/toogle.py` 时会调用 `load_plugins()` 注册业务插件 matcher。
- import `plugins/schedule.py` 时会注册定时任务并加载 `data/schedule.json` 中的手动定时任务。

## 插件加载阶段

核心文件：`toogle/index.py`

加载逻辑：

1. 读取 `toogle/plugins/` 顶层文件列表。
2. 对每个 `.py` 文件执行 `importlib.import_module()` 和 `importlib.reload()`。
3. 遍历模块成员：
   - `MessageHandler` 子类进入 `export_plugins`。
   - `ActiveHandler` 子类实例化后进入 `active_plugins`。
   - `ScheduleModule` 子类实例化后进入 `schedule_plugins`；如果它也声明了 `trigger`，会同时包装为普通可触发插件。
4. 跳过 `config["DISABLED_MODULE"]` 中列出的类名。

业务插件被包装为 `toogle.nonebot2_adapter.PluginWrapper`，其中 `plugin_class` 是类，`plugin` 是实例。

## 收消息与 matcher 匹配

核心文件：`plugins/load.py`

1. `load_plugins()` 遍历 `export_plugins`。
2. 对每个插件执行 `on_regex(plugin.plugin.trigger)`。
3. 把 `PluginWrapper.ret` 注册为 handler。
4. 如果插件设置 `to_me_trigger = True`，额外注册一个 `on_message(rule=to_me())` matcher。

此阶段只做正则层面的粗匹配，真正的权限、计费、限流和消息转换在 `PluginWrapper.ret()` 中完成。

## 消息转换

核心文件：

- `toogle/nonebot2_adapter.py`
- `toogle/message.py`
- `toogle/message_handler.py`

`PluginWrapper.get_message_pack(event, message)` 将 NoneBot/Mirai 消息转为项目自有对象：

- 群聊事件：`Group(event.sender.group.id, event.sender.group.name)` + `Member(event.sender.id, event.sender.name)`。
- 私聊事件：`Group(0, "私聊")` + `Member(event.sender.id, event.sender.nickname)`。
- 引用消息：优先从 `MESSAGE_HISTORY` 找原消息，找不到则转换 `event.quote.origin`。
- 消息内容：`nb2toogle()` 转换为 `toogle.message.MessageChain`。

转换后得到 `MessagePack`：

- `id`：Mirai 消息 source id。
- `message`：`MessageChain`。
- `group`：群信息，私聊时 `group.id == 0`。
- `member`：发送者。
- `quote`：可选引用消息。
- `time`：本地接收时间。

## 插件前置检查

核心方法：`PluginWrapper.ret()`

执行顺序大致如下：

1. 转换 `MessagePack`，空消息直接跳过。
2. 再次用插件正则校验，防止 matcher 误入。
3. 如果 `plugin.price > 0` 且群在 `config["ECO_GROUP"]`，检查用户余额。
4. 如果设置 `plugin.interval`，用 `interval_limiter` 做用户级冷却。
5. 如果 `plugin.admin_only`，非管理员直接返回。
6. `get_block()` 检查黑名单和临时禁用。
7. `is_traffic_free()` 检查 `data/traffic_control.py` 中的分时禁用。
8. 如果消息引用了其他消息，且插件没有 `ignore_quote = True`，把引用原文拼到当前消息后面。
9. 调用 `plugin_run()`。

注意：`white_list`、`thread_limit` 当前主要是历史属性或插件自描述，核心分发里没有完整使用它们实现隔离。

## 插件执行队列

核心文件：`toogle/nonebot2_adapter.py`

`plugin_run(plugin, message_pack)` 并不直接 await 插件，而是调用 `thread_put_job()` 放入 `WORK_QUEUE`。

worker 模型：

- 默认 `THREAD_NUM = 10`。
- `worker_start()` 创建多个线程，每个线程内部用 `asyncio.run(thread_worker(i))` 跑一个异步循环。
- `thread_worker()` 从 `WORK_QUEUE` 取 `(plugin, message_pack, kill)`。
- 执行 `await plugin.ret(message_pack)`。

插件返回处理：

1. 如果返回 `None` 或空值，不发送消息。
2. 如果返回 `MessageChain`：
   - 若插件有 `interval` 且返回链没有 `no_interval`，强制记录冷却。
   - 若插件有 `price` 且返回链没有 `no_charge`，扣余额。
   - 若 `res.root` 非空，调用 `bot_send_message()` 发送。
   - 调用 `print_call()` 写入 `log/call.log`。
3. 网络类异常会向用户发送“爬虫网络连接错误，请稍后尝试”。
4. `VisibleException` 会把异常文本发给用户。
5. 其他异常会写 `log/err.log` 并私聊管理员。

## 发送消息

核心方法：`bot_send_message(target, message, friend=False)`

支持的 target：

- `MessagePack`：自动判断群聊或私聊。
- `int`：目标群或好友 ID，由 `friend` 控制发送类型。

支持的 message：

- 项目自有 `toogle.message.MessageChain`。
- NoneBot/Mirai `MessageChain`。
- `str`。

发送流程：

1. 获取全局 `BOT`，必要时 `nonebot.get_bot()`。
2. 构造一个伪事件对象，群聊使用 `get_event()`，私聊使用 `FriendMessage`。
3. `toogle2nb()` 将项目消息链转为 Mirai message segment。
4. 开一个新线程执行 `asyncio.run(BOT.send(...))`。

这个设计让业务插件可以在 worker 线程中同步触发发送，但也意味着发送不是严格顺序同步完成。

## 事件后处理

核心文件：`plugins/toogle.py`

`message_post_process` 是 NoneBot event postprocessor：

1. 将所有消息加入 `MESSAGE_HISTORY`。
2. 遍历 `active_plugins`，在 `config["CHAT_GROUP_LIST"]` 群中按随机触发逻辑执行主动插件。
3. 调用 `chat_earn()`，处理聊天获得 gb、延迟撤回记录等后处理。

`all_event_handler` 处理非普通消息事件：

- `GroupRecallEvent`：从 `MESSAGE_HISTORY` 找被撤回消息，加入 `RECALL_HISTORY`。
- `BotInvitedJoinGroupRequestEvent`：私聊管理员 `.accept_invite ...` 命令。
- 其他事件目前多为占位。

启动/关闭钩子：

- `on_startup`：从 `config["HISTORY_SAVE_PATH"]` 加载历史消息。
- `on_shutdown`：保存 `MESSAGE_HISTORY`。
- `on_bot_connect`：私聊管理员“已启动”。

## 调度链路

核心文件：

- `toogle/scheduler.py`
- `plugins/schedule.py`
- `toogle/plugins/schedule.py`

两类定时任务：

1. 代码声明的 `ScheduleModule` 子类，例如每日排行、会员任务、监控任务。
2. 用户创建的手动任务，保存在 `data/schedule.json`，由 `reload_manual_schedular()` 加载。

如果手动任务 `program = true`，调度执行时会构造一条虚拟消息，通过 `copied_plugin_list` 找可触发业务插件并调用 `plugin_run()`。

