# 04 配置数据与持久化

本项目大量状态存在 `.env`、`data/`、SQLite、Mirai 日志和项目日志中。开发时要先确认目标功能读写了哪些状态，避免误删或误改运行数据。

## 配置读取

核心文件：`toogle/configs.py`

`reload_config()` 直接读取 `.env`：

```python
config = {
    line.split("=")[0]: ini_parse(line.split("=")[1].replace("\n", ""))
    for line in open(".env", "r").readlines()
    if len(line) > 1
}
```

解析特点：

- 值以 `[` 开头且以 `]` 结尾时使用 `eval()` 转为 Python 对象。
- 其他值保持字符串。
- 没有跳过注释或复杂转义的逻辑。
- 值中如果包含额外 `=`，当前实现会被 `split("=")[1]` 截断。

常见配置项：

| 配置 | 用途 |
| --- | --- |
| `VERIFY_KEY` | Mirai API HTTP session key。 |
| `MIRAI_HOST`、`MIRAI_HTTP_PORT`、`MIRAI_PORT` | Mirai API HTTP 地址。 |
| `MIRAI_QQ` | 登录机器人 QQ 列表。 |
| `ADMIN_LIST` | 管理员 QQ 列表。 |
| `ADMIN_GROUP_LIST` | 管理员群。 |
| `BLACK_LIST` | 黑名单成员。 |
| `DISABLED_MODULE` | 按类名禁用业务插件。 |
| `ECO_GROUP` | 启用 gb 计费的群。 |
| `CHAT_GROUP_LIST` | 主动聊天插件可运行的群。 |
| `GROUP_LIST` | 每日新闻/主群等功能用群列表。 |
| `HISTORY_SAVE_PATH` | `MESSAGE_HISTORY` 持久化路径。 |
| `GPTSecret`、`GPTModel`、`GPTModelLarge`、`GPTUrl` | GPT 类功能。 |
| `NovelAISecret` | NovelAI 作图。 |
| `REQUEST_PROXY_HTTP`、`REQUEST_PROXY_HTTPS` | 部分请求代理。 |
| `WT_DATAMINE_GIT` | 战雷拆包数据路径/仓库。 |
| `SCRIPING_ANT_TOKEN` | ScrapingAnt 反 Cloudflare 功能。 |

安全提醒：

- 不要把 `.env` 内容复制进文档或提交。
- 新增配置时要考虑 `configs.py` 的简单 parser 限制。
- 新增 list 配置建议保持形如 `KEY=["1","2"]`。

## SQLite

核心文件：

- `toogle/sql.py`
- `sqlite.sql`
- 默认数据库：`data/toogle.db`

主要表：

| 表 | 作用 |
| --- | --- |
| `qq_user` | 用户基础数据、权限、余额、最后运势、remake 时间、waifu、JSON 扩展字段。 |
| `qq_waifu` | ACG 对象系统。 |
| `remake_data` | 科学 remake 历史排行。 |

`SQLConnection` 是轻量包装，特点：

- 每次操作新建 SQLite 连接。
- 大量 SQL 用 f-string 拼接。
- `insert_user()` 会在查询用户不存在时创建用户。
- `get_user_data()` / `update_user_data()` 把 `qq_user.data` 当 JSON 扩展字段使用。

开发建议：

- 不要把未校验用户输入拼进 `SQLConnection.update_user(id, content)`。
- 优先复用已有 `SQLConnection.search/insert/update/delete`。
- 对新字段或新表先更新 `sqlite.sql`，再写迁移/兼容逻辑。
- `get_user()` 返回 tuple，现有代码大量按索引访问，例如 `user[3]` 是 credit。

## gb 余额系统

核心文件：

- `toogle/economy.py`
- `toogle/nonebot2_adapter.py`
- `toogle/plugins/economy.py`

规则：

- 用户正常聊天时，`chat_earn()` 对余额低于 15 且文本长度 >= 10 的消息给 1 gb。
- 插件设置 `price > 0` 后，框架会在 `ECO_GROUP` 群中检查并扣费。
- `MessageChain(no_charge=True)` 可避免扣费。
- `/balance`、`/give_balance`、`/take_balance` 在 `toogle/plugins/economy.py`，其中管理操作需要管理员。

## JSON 状态文件

通用工具：`toogle.utils.modify_json_file(name)`

行为：

- 自动读写 `data/<name>.json`。
- 用进程内 `threading.Lock` 按 name 加锁。
- 不自动创建中间目录；调用前确保目录存在。
- 如果文件不存在，初始为 `{}`。

常见 JSON/状态文件：

| 路径 | 用途 |
| --- | --- |
| `data/user_info.json` | 群用户昵称覆盖，`MessagePack` 构造时读取。 |
| `data/schedule.json` | 用户创建的手动定时任务。 |
| `data/setu_record.json` | 色图记录与排行。 |
| `data/afdian.json` | 爱发电会员状态。 |
| `data/stock.json` | 用户自选股。 |
| `data/vote/<group>.json` | 投票状态。 |
| `data/baseball_players.json` | 棒球玩家数据。 |
| `data/send_api.json` | `/send` HTTP API secret 到群和 qpm 的映射。 |
| `data/buff_cookie` | BUFF Cookie。 |
| `data/baidu_cookie` | 百度指数 Cookie。 |
| `data/pic_bloom`、`data/sfw_bloom`、`data/shit_bloom` | 图片识别 BloomFilter 文件。 |

## 图片和素材目录

| 路径 | 用途 |
| --- | --- |
| `data/qutu/` | 趣图素材。 |
| `data/long_img/` | 龙图素材。 |
| `data/history_img/<group>/` | 群黑历史图片。 |
| `data/buffer/` | 图片 URL 缓存。 |
| `data/anime/` | 当季新番 HTML/图片缓存。 |
| `data/dice_table/` | 自定义骰表。 |
| `data/dnd5e/` | DND 5E 数据。 |
| `data/tarkov/` | 塔科夫数据。 |
| `data/gf2_mcc_data/` | 少前2数据。 |
| `data/laws/` | 法律文本数据。 |
| `data/milkywayidle/` | 银河奶牛数据。 |
| `data/wt/` | 战雷相关数据。 |

这些目录可能包含运行中积累的真实数据，不要在无明确要求时清理。

## 日志

项目日志：

| 路径 | 写入方 | 用途 |
| --- | --- | --- |
| `log/call.log` | `toogle.utils.print_call()` | 插件成功调用记录。 |
| `log/err.log` | `toogle.utils.print_err()` | 插件异常堆栈。 |
| `log/slow.tsv` | worker | 慢调用记录。 |
| `log/api.log` | `plugins/api.py` | HTTP API 请求日志。 |
| `log/afdian.log` | `plugins/api.py` | 爱发电 webhook 日志。 |
| `log/recall.log` | `DelayedRecall` | 延迟撤回统计。 |
| `log/openai.log` | `gpt_censor()` | GPT 审查调用成本。 |
| `log/schedule_err.log` | `ScheduleModule.ret_wrapper()` | 定时任务异常。 |

Mirai 日志：

- 路径：`mirai/logs/`
- `statistics/` 和 `AIConclude` 会读取这些日志做聊天分析或总结。

## HTTP API

核心文件：`plugins/api.py`

接口：

- `GET /api`：健康测试，返回 `{"message": "Hello, world!"}`。
- `POST /api`：记录请求体到 `log/api.log`。
- `POST /afdian`：爱发电 webhook，调用 `recv_afdian_msg()`。
- `POST /send`：按 `data/send_api.json` 中 secret 发送消息到指定群。

`/send` body：

```json
{
  "secret": "your_secret",
  "message": "文本或消息 JSON"
}
```

消息 JSON 由 `toogle.message.json_to_msg()` 转为 `MessageChain`，支持：

- `text`
- `image`
- `image_url`
- `forward`
- `at`

## 会员状态

核心文件：`toogle/membership.py`

- `recv_afdian_msg()` 处理爱发电订单，写 `data/afdian.json`。
- 会员计划名映射在 `TRADE_PLANS`。
- 成功购买后可能补足用户 gb 到会员目标余额。
- 如果能从 `MESSAGE_HISTORY` 找到用户最近发言，会在对应群发送感谢消息。

## 历史消息

核心文件：`toogle/message_handler.py`

两个全局历史：

- `MESSAGE_HISTORY`：所有近期消息，按 group id 存窗口。
- `RECALL_HISTORY`：撤回消息历史。

默认窗口：500 条。

持久化：

- 启动时从 `config["HISTORY_SAVE_PATH"]` 加载 pickle。
- 关闭时保存 pickle。
- `save_str()` 可输出 JSON 结构用于调试。

注意：`MESSAGE_HISTORY` 是进程内状态，worker/等待用户输入/引用消息恢复/会员通知等都依赖它。

