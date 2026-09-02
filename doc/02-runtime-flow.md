# 02 运行链路

本文描述当前 NapCat 迁移实现的真实执行顺序。2026-07-17 已完成 plugin registry、
WebSocket JSON 边界、基础 action 路由和单 event loop worker 的第一轮修复。

## 启动阶段

入口为 `bot.py`：

1. `msg_queue.reset_queues()` 为当前 event loop 创建有界收发队列。
2. `load_plugins(strict_core=True)` 构建 plugin registry；`meta` / `basic` 失败会阻止启动。
3. `register_schedules()` 幂等注册代码型和手动任务。
4. `worker_start()` 显式创建 asyncio worker；默认一个，可通过 `WORKER_NUM` 调整。
5. `scheduler_start()` 启动 APScheduler。
6. 并发运行 NapCat WebSocket lifecycle 和 message dispatch loop。
7. 退出时取消 runtime task、关闭 scheduler、停止 worker，最后保存消息历史。

`toogle.index` 和 `adapter.worker` 已没有“import 即扫描插件/启动线程”的副作用。插件模块
本身仍可能在 import 时读取数据、加载模型或创建目录，这部分要继续按插件域收敛。
Flask API 不并入 `bot.py` 的 asyncio 生命周期，由独立 `tooglebot-api.service` 启动并依赖
机器人服务；API 的监听和关闭不代表 NapCat/worker 健康。

## 插件加载链路

```text
bot.main()
  -> toogle.index.load_plugins()
     -> Path-based sorted discovery of plugins/*.py
     -> import each module once
     -> only inspect classes defined by that module
     -> construct temporary normal / active / scheduled registries
     -> collect loaded / disabled / failed report
     -> reject core failure, otherwise publish registry snapshot
  -> worker_start()
```

当前 registry：

- `export_plugins`：普通插件，以及有非空 trigger 的定时插件 wrapper。
- `active_plugins`：每条群消息后处理阶段检查的主动插件。
- `schedule_plugins`：注册到 APScheduler 的代码型任务。

loader 现在具备：

- 候选路径与 cwd 解耦、稳定排序，每次 build 重新发现文件。
- `module + qualname` 身份，只注册 `candidate.__module__ == module.__name__` 的类。
- 模块 import 和插件构造独立错误边界，输出结构化 `PluginLoadReport`。
- 先完整构建临时 registry，再一次发布；worker 每条消息读取 tuple snapshot。
- 首次 load 不重复执行模块；显式 reload 才调用 `importlib.reload()`。
- 帮助插件运行时读取 registry provider，不再保存会被 reload 清空的全局列表。

当前重新提供管理员命令 `.reload`。命令精确匹配且同时受 `admin_only` 和 `ADMIN_LIST`
校验；执行顺序为原位刷新 `.env` 配置、在线程中重新导入全部顶层插件并原子发布 registry、
回到 event loop 对代码型 scheduler job 做 reconcile。worker 通过 provider 读取新快照，
主动插件列表则原位更新，因此不需要重启进程。代码型定时任务以新 registry 为准替换或
删除，手动任务保留；
回复只给出各类数量、失败模块名和耗时，不回显配置值或异常正文。核心插件刷新失败时旧
registry 不发布；非核心模块失败仍按当前 loader 契约发布其余健康插件并在回复中标明。
并发 load/reload 由 registry 内部锁串行化，避免多个 build/publish 交错。

2026-08-17 本地 venv 实测公开 registry reload 为 90 个普通、2 个主动、3 个定时插件，加载失败为 0；
帮助页 smoke 可生成 `ForwardMessage`。缺少 `libtorrent`、`mysql-connector`、
`python-a2s`、百度 Cookie 或 DND 数据时，对应功能返回可诊断提示，不再拖垮整个聚合模块。

剩余 loader 工作：建立版本化预期插件 manifest/健康策略；继续移除业务模块 import 时的
重型 I/O；`.reload` 和 `reload_designated_export_module()` 当前都为了正确性重建全部
registry，尚未优化成真正的单模块事务 reload。

## 收帧和分类

```text
NapCat WebSocket frame
  -> decode_frame(): bytes/text -> JSON object
  -> action response? -> action_router.resolve_response(echo)
  -> event? -> msg_queue.push_event(event)
  -> message event -> parse_event() -> recv_queue
```

非法 JSON、非 object frame 和单事件转换异常会记录脱敏上下文并继续收帧，不再永久结束
连接。`push_event()` 当前策略：

- `message`：过滤 `user_id == self_id`，规范化后进入有界队列。
- `notice`：已恢复 group/friend recall 写入 `RECALL_HISTORY`；其他 notice 记录未实现类型。
- `meta_event`：不进入插件队列。
- `request`：记录 request type，尚未实现审批业务。
- action response：在进入事件分支前按 echo 路由，不会再静默混入消息处理。

reply 只用 `data.id` 查询本地 `MESSAGE_HISTORY`，收帧路径不再同步调用 NapCat HTTP。
缓存未命中时保留引用占位。forward 有内联节点时可解析；仅有 forward id 时不在收帧
协程补网络数据。

## MessagePack 规范化

`adapter/msg_queue.py::parse_event()` 生成：

- `id`：OneBot `message_id`。
- `message`：text、at、at-all、image、forward 和未知段的内部 `MessageChain`。
- `group`：群聊使用真实 group id；私聊固定 group 0。
- `member`：`sender.user_id` 及群名片/昵称。
- `quote`：独立于正文的本地引用对象。
- `message_type`：严格限制为 `group` / `private`。
- `time`：优先保留 OneBot event time。

未知消息段降级成不含原始正文的诊断占位，不再导致整条消息消失。私聊历史使用
`private_<user_id>` key，避免所有私聊混在 group 0。

## 分发与插件执行

```text
recv_queue
  -> process_loop()
     -> ONLY_READ group? drop before all functionality
     -> history / active plugin / economy post-process
     -> WORK_QUEUE
  -> worker_loop()
     -> registry snapshot
     -> plugin.is_trigger() using re.search
     -> PluginWrapper.prepare() policy checks + derived message view
     -> plugin.ret()
     -> cooldown / charge / send / audit
```

当前默认只有一个 asyncio worker，不再创建 10 个线程和 10 个 event loop，也不再共享
跨 loop 的插件实例。队列和 worker 都由 lifecycle 显式创建/停止，同进程再次启动不会
复用绑定到旧 loop 的 queue。

`PluginWrapper.prepare()` 不修改原始 `MessagePack`。需要引用原文的插件收到浅派生消息链，
因此多插件命中不会重复追加 quote，也不会污染 history/active plugin 看到的消息。
当前明确保留“一条消息允许多个插件命中”的语义，匹配统一使用 `re.search()`。

群聊消息会先检查 `.env` 的 `ONLY_READ` 列表；命中时不写 history、不运行 active plugin、
economy/audit 或普通插件，也不进入 `WORK_QUEUE`。`process_message()` 同样保留该检查，避免
scheduler programmable 等直接投递的虚拟群消息绕过策略；私聊不受影响。该策略只限制
消息触发，不拦截管理员、scheduler 或 API 的主动发送。

未命中时，后处理按 history -> active -> economy/audit 顺序完成后才投递普通 worker。
三个阶段有错误隔离，私聊不会执行群主动插件；单个后处理错误不会终止 dispatch loop。

`ActivePathProbe` 默认关闭，只在 `NAPCAT_ACTIVE_PROBE_ENABLED` 开启，且消息发送者、群、
文本同时匹配验证配置时返回配置响应。2026-07-17 已用双账号真实验证
event -> history -> active registry -> `ret_wrapper()` -> outbound queue -> NapCat -> 群历史；
这条探针不访问外部模型，也不会在其他群或其他发送者消息上随机触发。

主要剩余风险是大量插件的 `async ret()` 内仍直接调用同步 requests、SQLite、模型推理和
图片渲染。默认单 worker 保证正确性，但这些调用仍可能阻塞 WebSocket event loop；需要按
插件标注执行类型并逐步改为 async client 或受控 `asyncio.to_thread()`。豆包图片/视频的
生成轮询、下载、GIF 转换和群文件上传已在 2026-07-17 offload；禁言/撤回的自动后处理和
投票插件调用已在 2026-08-10 offload；这不代表其他插件已完成。

## 发消息链路

```text
plugin result / bot_send_message()
  -> preserve group/private target
  -> adapter.msg_queue.send_message()
  -> OneBot action dict + UUID echo
  -> bounded send_queue
  -> json.dumps()
  -> WebSocket text frame
  -> action response routed by echo
```

`bot_send_message()` 不再为每次发送创建未跟踪线程；跨线程调用通过 transport loop 的
`call_soon_threadsafe()` 入队。私聊回复使用原消息 `member.id`，不会再向 group 0 发送。
text/image/reply/at/at-all/markdown/json 已生成标准段；其中 JSON/Ark 卡片已完成独立账号
真实投递，Markdown 需嵌在双层合并转发，不能直接发送。`ForwardMessage` 现在改用
`send_group_forward_msg`/`send_private_forward_msg`，将每个节点编码为 `type=node`，并递归
转换节点正文；顶层转发不能与普通消息段混发。当前已有脱敏 fixture 单测，真实账号投递
和嵌套 Markdown 仍待独立观察账号验收。

群文件不是普通消息段。豆包视频当前走另一条 action 链路：

```text
plugin bytes
  -> temporary local file
  -> toogle.adapter.bot_upload_group_file()
  -> adapter.http_request.upload_group_file()
  -> POST /upload_group_file
  -> status/retcode validation
  -> remove temporary file
```

`bot.py` 在启动时注册 uploader、关闭时注销。当前只适用于 NapCat 与机器人共享本机文件
系统的本地进程阶段；未来容器化时必须改为共享 volume 或流式上传，不能假定容器可读
宿主机 `/tmp`。

`adapter.action_router.call_action()` 提供带 timeout 的 action/response 关联。2026-07-17
已用本地 NapCat 4.15.4，并在更新到 4.18.9 后对 `get_status`、`get_login_info`、
`get_group_list` 完成只读往返；当前 4.18.9/NTQQ 3.2.28-48517 又通过
`nc_get_packet_status`，账号按配置严格匹配。同日先完成 `.help ping` 普通插件往返，
随后发送配置主动探针文本；
主账号在 `message_post_process()` 命中主动插件并经正常 outbound queue 回复，发送端群历史
确认新回复来自配置主账号。具体账号、群和 message id 只记录在 10 的本机验收结果中。

## 连接与关闭

连接支持 `WS_URL`，或由 `WS_HOST`、`WS_PORT`、`WS_PATH` 组合；token 只在边界拼入 query。
当前 `/` 默认 path 已在本地 NapCat 验证。

server lifecycle 已具备：

- `connection_ready` 状态。
- 收发 task 任一结束时取消并回收另一侧。
- 断线后 1 到 30 秒指数退避重连。
- 断线时让全部 pending action 明确失败。
- 未发送 action 在发送失败时尝试重新入队。
- 进程启动通知只在首次成功连接时执行，避免每次重连刷管理员。

真实联调确认取消连接不会遗留 `napcat-recv` / `napcat-send` task。完整运行健康检查、
shutdown signal、发送队列溢出和长时间断网仍需进程级测试。

## 调度

代码型和手动任务由 `bot.py` 显式 start/stop。代码任务使用类路径 job id；手动任务使用
不含消息正文的 UUID，旧数据迁移为稳定 hash。创建时先由 APScheduler 校验 cron，再原子
写入 JSON；直接发送和 programmable worker queue 两条路径都有测试。单次任务只在成功
入队/执行后删除，失败时保留任务；删除索引限定在创建者自己的任务列表。

时区来自 `BOT_TIMEZONE`（默认 `Asia/Shanghai`），统一 `coalesce=True`、
`max_instances=1`、`misfire_grace_time=300`。3 个代码任务的 cron、重复注册、start/stop、
日报/会员/监测边界、手动普通/可触发/单次/异常/删除均有自动测试；监测和会员同步 I/O
已 offload，不阻塞 WebSocket event loop。监测任务先读取订阅，只调用至少被一个群订阅
的数据源；空订阅不访问网络。外部站点失败会隔离并等待下一轮，不等于站点本身永久可用。
