# 06 共享服务与工具

本文整理跨插件复用的基础设施和工具函数。修改这些文件的影响范围通常大于单个业务插件。

## NoneBot/Mirai 适配器

文件：`toogle/nonebot2_adapter.py`

核心职责：

- `PluginWrapper`：把业务 `MessageHandler` 包装成 NoneBot handler。
- `nb2toogle()`：Mirai/NoneBot 消息转项目 `MessageChain`。
- `toogle2nb()`：项目 `MessageChain` 转 Mirai/NoneBot 消息。
- `bot_send_message()`：同步风格发送消息。
- worker 队列：`WORK_QUEUE`、`thread_worker()`、`worker_start()`。
- 权限/冷却/计费/分时流量控制前置检查。

高影响点：

- 改 `nb2toogle()` 会影响所有插件的输入。
- 改 `toogle2nb()` 会影响所有插件的输出。
- 改 `thread_worker()` 会影响扣费、冷却、异常处理、日志。
- 改 `bot_send_message()` 会影响主动发送、定时任务、HTTP API。

## 消息模型

文件：`toogle/message.py`

重要类：

- `Element`
- `Group`
- `Member`
- `Quote`
- `At`
- `AtAll`
- `Plain`
- `Image`
- `ForwardMessage`
- `Xml`
- `MessageChain`

常见扩展任务：

- 支持新的 Mirai 消息类型：同时改 `nb2toogle()` 和 `toogle2nb()`。
- 增加内部元素：继承 `Element`，实现 `asDisplay()` 和转换逻辑。
- 优化图片缓存：关注 `Image.getBytes()`、`Image.getBase64()`、`Image.buffered_url_pic()`。

## 插件基类和历史消息

文件：`toogle/message_handler.py`

核心：

- `MessageHistory`
- `MESSAGE_HISTORY`
- `RECALL_HISTORY`
- `MessagePack`
- `MessageHandler`
- `ActiveHandler`
- `WaitCommandHandler`
- `USER_INFO`

注意：

- `MessageHistory.history` 的 key 在多数情况下是群号 int，但也有 `"setu_<group>"`、`"censor_<group>"` 这类字符串 key。
- `MessageHistory.search()` 可按群、消息 ID 或文本搜索。
- `MessagePack.__init__()` 会调用 `get_user_name()` 覆盖 `member.name`。
- `WaitCommandHandler` 依赖 postprocessor 写入历史消息，不能用于启动早期或未记录的消息。

## 插件动态加载

文件：`toogle/index.py`

重要全局：

- `export_plugins`
- `active_plugins`
- `schedule_plugins`
- `copied_plugin_list`

相关函数：

- `reload_plugins()`
- `reload_designated_export_module(plugin_name, module_name="")`

注意：

- `plugin_list = os.listdir("toogle/plugins/")` 在模块 import 时计算，运行中新增文件后只调用 `reload_plugins()` 可能不会刷新这个列表，除非重新 import 或手动更新。
- 只扫描顶层 `.py`。
- `DISABLED_MODULE` 按类名过滤。
- 用类名去重，避免重复导出。

## 调度系统

文件：`toogle/scheduler.py`

核心：

- `ScheduleModule`
- `reload_manual_schedular()`
- `load_manual_schedular(item)`
- `remove_job(name)`
- `all_schedule()`

手动任务结构大致如下：

```json
{
  "group_id": 123,
  "creator_id": 456,
  "single_time": false,
  "text": "要发送或触发的内容",
  "program": false,
  "time": {
    "hour": 9,
    "minute": 0
  }
}
```

`program = true` 时，会构造虚拟消息并走业务插件触发链。

## 配置和限流

文件：`toogle/configs.py`

核心：

- `config`
- `reload_config()`
- `proxies`
- `interval_limiter`
- `IntervalLimiter`

注意：

- `interval_limiter` 是进程内状态，重启丢失。
- `force_user_interval()` 手动 acquire/release，没有 `try/finally`，异常时有死锁风险；当前传入数据简单，通常不会触发。
- 新增配置 key 时，可加入 `key_check` 让启动时提示缺失。

## Mirai HTTP 扩展

文件：`toogle/mirai_extend.py`

提供直接调用 Mirai API HTTP 的函数：

- `get_http_session()`
- `bind_http_session()`
- `release_http_session()`
- `with_temp_verify()`
- `send_group_file()`
- `send_group_msg()`
- `recall_msg()`
- `accept_group_invite()`
- `quit_group_chat()`
- `mute_member()`

使用场景：

- 文件上传。
- 撤回。
- 接受邀请。
- 退群。
- 禁言。

注意：

- 直接读取 `config["VERIFY_KEY"]`、`MIRAI_HOST`、`MIRAI_HTTP_PORT`。
- 这些函数有真实外部副作用，测试时避免对真实群误操作。

## 工具函数

文件：`toogle/utils.py`

常用函数：

| 函数 | 用途 |
| --- | --- |
| `modify_json_file(name)` | 安全读写 `data/<name>.json`。 |
| `create_path(path)` | 确保目录存在。 |
| `text2img()` | 文本转 PNG bytes。 |
| `list2img()` | 字符串/图片 bytes 列表纵向拼图。 |
| `draw_rich_text()` | 带简单富文本参数的绘制。 |
| `draw_pic_text()` | 图片 + 文本组合图。 |
| `pic_max_resize()` | 图片缩放。 |
| `convert_mp4_to_gif()` | MP4 bytes 转 GIF bytes。 |
| `convert_gif_to_h264()` | GIF bytes 转 MP4/H264 bytes。 |
| `is_admin()` | 判断管理员。 |
| `is_admin_group()` | 判断管理员群。 |
| `print_err()` | 写错误日志并返回文本。 |
| `print_call()` | 写调用日志。 |
| `read_chat_log()` | 读取 Mirai 日志中的聊天记录。 |

高风险点：

- `modify_json_file()` 只在进程内加锁，多进程部署时不能保证一致性。
- 视频转换依赖 POSIX 和 OpenCV。
- 字体路径默认依赖 `toogle/plugins/compose/fonts/Arial Unicode MS Font.ttf`。
- `draw_rich_text()` 内部对富文本参数使用 `eval()`。

## 图片识别

文件：`toogle/tools/pic_recognition.py`

核心：

- `detect_pic_nsfw(pic, output_repeat=False)`
- `get_pic_average_hash(pic_bytes, size=512, hash_size=16)`
- `regist_shit_pic(pic_bytes)`
- `is_shit_pic(pic_bytes)`

状态：

- `data/pic_bloom`
- `data/sfw_bloom`
- `data/shit_bloom`

注意：

- `detect_pic_nsfw()` 在函数内部 import `opennsfw2`，首次调用可能较慢。
- 大图或不可识别图片会返回 `-1` 或 false。
- `regist_shit_pic()` 和 `is_shit_pic()` 对大于 5MB 图片直接跳过。

## 数据库接口

文件：`toogle/sql.py`

核心类：

- `DatetimeUtils`
- `SQLConnection`

常用方法：

- `search(table, data, order="", limit=None)`
- `insert(table, data)`
- `update(table, data, search)`
- `delete(table, data)`
- `get_user(id)`
- `insert_user(id)`
- `update_user(id, content)`
- `get_user_data(id)`
- `update_user_data(id, data)`

注意：

- SQL 拼接比较直接，新增面向用户输入的查询时要格外谨慎。
- `data_str_proc()` 会去掉单引号和过滤 emoji，但不是完整 SQL 注入防护。
- SQLite 文件固定为 `data/toogle.db`。

## 后处理与内容风控

文件：`toogle/msg_proc.py`

核心：

- `chat_earn(message_pack)`：聊天获得 gb、图片后处理入口。
- `setu_detect(message_pack, pics)`：NSFW 图片检测、记录、可能撤回。
- `shit_pic_detect(message_pack, pics)`：图片哈希命中后禁言撤回。
- `chat_cencor(message_pack)`：群聊天政治内容审查，当前需要显式调用才会执行。
- `DelayedRecall`：延迟撤回和合并转发。

注意：

- `chat_earn()` 中图片检测相关调用当前多为注释状态。
- `DelayedRecall.recall()` 会在独立线程中 sleep、撤回、发送转发消息。
- `POST_PROC_LOCK` 用于色图记录写入。

## 根目录 NoneBot 插件

### `plugins/load.py`

职责：

- 把 `export_plugins` 注册成 NoneBot matcher。
- 管理 `MATCHERS`，重新加载时把旧 matcher 过期。

### `plugins/toogle.py`

职责：

- ping 测试 `22222`。
- 调用 `load_plugins()`。
- `/help`、`.help`、`#help#`。
- 消息 postprocessor。
- 撤回/邀请等事件 postprocessor。
- 启动/关闭/连接钩子。

### `plugins/schedule.py`

职责：

- 注册 `schedule_plugins`。
- 加载 `data/schedule.json` 中的手动调度。

### `plugins/api.py`

职责：

- FastAPI `/api`、`/afdian`、`/send`。
- 通过 `json_to_msg()` 支持外部推送消息。

## 离线统计

目录：`statistics/`

| 文件 | 功能 |
| --- | --- |
| `chat_analysis.py` | 读取 `mirai/logs`，用 `thulac` 分词统计群聊天词频。 |
| `word_cloud.py` | 根据词频 JSON 生成词云图。 |
| `call_analysis.py` | 读取 `log/call.log` 统计插件调用。 |

注意：

- 这些脚本多为手动运行，不是线上服务路径。
- 输出在 `statistics/res/`。
- `chat_analysis.py` 中时间范围目前写死在源码里。

## 实验测试目录

目录：`test/`

特点：

- 包含很多手动脚本、外部服务实验、图片/视频样本、浏览器驱动。
- 不是 pytest/unittest 风格的统一测试套件。
- 修改业务功能时通常用 `py_compile` 和针对性函数调用验证，而不是全量跑 `test/`。

