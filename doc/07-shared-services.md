# 07 调度、API 与共享服务

## `toogle/` 模块地图

| 文件 | 职责 | 修改风险 |
| --- | --- | --- |
| `message.py` | 内部消息元素、链、图片/转发构造、外部 API JSON 转消息。 | 影响所有输入输出。 |
| `message_handler.py` | MessagePack、历史、插件基类、交互等待、用户昵称。 | 影响所有插件。 |
| `adapter.py` | PluginWrapper 前置策略、发送门面、限流/计费导出。 | 影响权限、扣费和所有回复。 |
| `index.py` | 扫描、导入、分类、重载业务插件。 | import 副作用和插件缺失风险高。 |
| `scheduler.py` | APScheduler、代码型/手动任务、可触发任务。 | 时间和虚拟消息契约高风险。 |
| `msg_proc.py` | 聊天收益、NSFW/图片治理、延迟撤回。 | 群管理副作用。 |
| `economy.py` | 余额查询、增减和上下文计费。 | 真实用户资产。 |
| `membership.py` | 爱发电订单、会员等级和补余额。 | webhook、余额和隐私。 |
| `sql.py` | SQLite wrapper 和用户 JSON data。 | 数据一致性和注入。 |
| `utils.py` | JSON 文件、图片/视频、权限、日志、旧聊天日志、冷却。 | 被大量插件 import。 |
| `logger.py` | 标准 logging 和按日轮转。 | 应成为日志唯一入口。 |
| `exceptions.py` | 用户可见和通用业务异常。 | 低风险，但需保持异常语义。 |

## 插件加载

`toogle/index.py` 的全局列表：

- `export_plugins: list[PluginWrapper]`
- `active_plugins: list[ActiveHandler]`
- `schedule_plugins: list[ScheduleModule]`

`load_plugins()` / `reload_plugins()` 每次按模块路径重新发现并排序顶层文件，只注册当前
模块定义的类。模块/构造错误进入 `PluginLoadReport`，核心模块失败会保留上一版 registry
并阻止启动；成功 build 后才发布列表快照。loader import 本身不扫描插件或启动 worker。

帮助插件通过只读 provider 获取快照，旧 `copied_plugin_list` 已删除。完整实现和剩余
import I/O 风险见 02、05。

## 前置策略和发送门面

`toogle/adapter.py` 应保持平台无关：

- `PluginWrapper.prepare()`：余额、冷却、权限、黑名单、分时控制和引用派生视图。
- `bot_send_message()`：把目标和内部消息交给注册的 `BOT_SEND` transport。
- `bot_upload_group_file()`：把群号、文件名和本地路径交给注册的上传 transport；业务插件
  不直接 import NapCat HTTP client。
- `send_admins()`：私聊群发管理员。

`BOT_SEND` 当前由 `adapter/msg_queue.py` 注册，发送不会新建线程；群文件 uploader 由
`bot.py` 在进程生命周期内注册 NapCat HTTP action。transport 未 ready
会返回可观察失败，跨线程生产者使用绑定 loop 的 thread-safe callback。后续可进一步
把注册动作移到 `bot.py`，完全消除模块赋值。

## 调度系统

`ScheduleModule.register()` 将 cron 字段注册到 `native_scheduler`。代码型任务来自
`plugins/schedule.py`，手动任务来自 `data/schedule.json`。

手动任务结构：

```json
{
  "id": "generated-uuid",
  "text": "要发送或触发的文本",
  "program": false,
  "single_time": false,
  "group_id": 123,
  "creator_id": 456,
  "time": {"hour": "9", "minute": "0", "second": "0"}
}
```

- `program=false`：到时直接发文本。
- `program=true`：构造虚拟 `MessagePack`，投递到普通插件队列。
- `single_time=true`：执行后移除 job 和 JSON 记录。

scheduler 已由 `bot.py` 显式 start/stop；programmable 分支使用 `Group` / `Member` 并
投递 asyncio worker。代码 job id 使用类路径，手动 job id 使用 UUID，不再把消息正文
写进 ID/日志。cron 在持久化前校验，JSON 原子替换；单次任务仅在成功后删除，失败保留。
删除索引先按创建者过滤。时区、coalesce、misfire grace 和 max instances 已统一配置，
代码任务、直接发送、可触发、单次、异常和生命周期均有测试。

`ScheduledMonitor` 每五分钟检查一次，但会先读取 `data/monitor_send.json`，仅并发拉取
实际被订阅的 `earth_quake` / `save_old_otaku` 数据源；没有订阅时不会访问外部网络。
单个数据源异常只记录该源并等待下一轮，不影响 scheduler 或其他源。

地震源在 2026-07-17 按中国地震台网当前页面核对为
`https://www.ceic.ac.cn/data/data.json`，使用 `magnitude/time/location` 字段并保持 TLS
校验；旧 `news.ceic.ac.cn/speedsearch.html` 已返回 405，不得恢复。解析有 mock schema
测试，官方 JSON 另做只读实时 smoke；实时站点可用性不由单元测试保证。

## 后处理

`adapter/post_process.py` 在每条消息进入 worker 时：

1. 写入 `MESSAGE_HISTORY`。
2. 在 `CHAT_GROUP_LIST` 中尝试主动插件。
3. 调用 `chat_earn()`。

当前顺序固定为后处理完成后再投递普通 worker，每一步有错误隔离。quote 通过派生消息
视图传给插件，不再修改 history 中的原始对象。主动链路探针已完成真实双账号往返。
SQLite 基础 schema 会自动 bootstrap；其他图片下载、模型推理和同步 HTTP 仍可能阻塞
WebSocket 主 event loop，是下一轮性能与稳定性重点。

`toogle/msg_proc.py` 还保留图片检测、撤回、禁言和延迟合并转发。部分检测调用当前被
注释，不应从代码存在推断功能已启用。group/friend recall notice 已写入撤回历史，其余
notice/request 尚未迁移。

## 外部 Flask API

`api/api.py` 定义：

- `GET /api`：健康示例。
- `POST /api`：记录 body。
- `POST /afdian`：处理爱发电订单。
- `POST /send`：按 `data/send_api.json` 的 secret、目标群和 qpm 主动发送。

`start_api()` 使用 `API_HOST`/`API_PORT`，由独立的 `tooglebot-api.service` 调用，不从
`bot.py` 的 asyncio 生命周期启动。当前 Flask 只监听回环 `127.0.0.1:36002`，nginx 在
`0.0.0.0:36001` 代理 `/api`、`/send` 和 `/afdian`；API unit 依赖
`tooglebot.service` 后再启动。systemd API active 只表示 Flask 进程存在，不代表 NapCat
或 worker 健康。Flask async view 仍不能直接当作 asyncio server task 使用而不做服务封装。
代理片段由安装脚本放到 `/etc/nginx/conf.d/tooglebot-api-locations.conf`，修改后必须先
执行 `nginx -t` 再 reload；该路径满足当前主机 SELinux 策略。

API 安全要求：

- webhook 验签，不能只相信 payload。
- secret 使用恒定时间比较或成熟认证组件，日志脱敏。
- qpm 边界、并发更新和错误响应有测试。
- `/send` 只接受受支持的 `json_to_msg()` 类型和合法目标。
- 发送失败不能仍返回 success。

## 图片、视频和识别

`toogle/utils.py` 提供 `text2img()`、`list2img()`、`draw_rich_text()`、
`draw_pic_text()`、缩放和 MP4/GIF 转换。字体统一从 `tools/fonts/` 读取。

`tools/pic_recognition.py` 使用 BloomFilter、imagehash 和 `opennsfw2`。平均哈希为空时
注册和查询都会直接返回，避免污染 BloomFilter 或把损坏图片误判为命中。首次模型 import
或推理很慢，不应阻塞 WebSocket loop；模型冒烟应单独标记。

`draw_rich_text()` 对富文本参数使用 `eval()`，解释器插件也执行用户代码；这两处是
独立安全债务，迁移完成后应优先隔离或替换，不要暴露到新增 HTTP 接口。

## 日志和可观测性

新代码使用 `toogle.logger.logger`，不要再直接 `print` 正常运行日志。推荐统一字段：

- connection state / reconnect count
- event type / message type（不记录敏感正文）
- plugin class / elapsed / outcome
- action / echo / retcode / elapsed
- queue size / dropped count
- scheduler job / next run / outcome

插件 import 失败应汇总成启动报告。只打印 error 后继续启动会形成“进程在线但大量功能
消失”的假健康状态。
