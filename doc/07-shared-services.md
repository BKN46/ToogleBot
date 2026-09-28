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

管理员 `.reload` 会先原位刷新配置，再在线程中执行全量 `reload_plugins()`，随后回到
event loop 调用 `adapter.schedule.register_schedules()`。刷新结果会报告普通、主动、定时、
禁用和失败数量；敏感配置及异常正文不会进入聊天回复。当前仍是全量模块刷新，不是单模块
热替换。registry build/publish 使用进程内锁串行化并发刷新。

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

### 每日新闻

`plugins/daily_news.py::DailyNews` 在 scheduler 时区（`BOT_TIMEZONE`，默认北京时间）
每天 10:00:00 执行。同文件的 `build_digest` 在线程中拉取 RSS，筛选
`[实际执行时刻-24小时, 实际执行时刻)` 的发布时间，忽略无日期/无时区条目；
正常10点执行即昨天10点至今天10点，延迟执行也使用实际时刻，不固定回退到10点。
默认抓取中新网要闻、国内、国际、财经和社会五个频道，按 URL/标题去重，跨栏目轮流
构建最多80条候选，RSS description 清理后最多保留600字，AI输入只取前240字。
同文件的 `select_news` 通过 `LLMAdapter` 的 deepseek profile 调用 `NEWS_AI_MODEL`
（默认 `deepseek-flash`），复用已有 DeepSeek 密钥/地址，与全局聊天模型独立。
使用 `thinking.type=disabled`、最多3500输出token和默认45秒请求超时；新闻请求默认直连，
`NEWS_AI_USE_PROXY=1` 才使用全局代理。RSS 免费，AI 可能产生模型费用。
排除无新增事实/措施的领导讲话、例行会见调研、学习贯彻、会议宣传、表态倡议、成绩赞歌、
形象宣传及软广告；只保留国内外重大事件，或就业工资、物价税费、住房、医疗、教育、
社保、出行等对普通人有实际影响的变化。政府发布的具体政策不因主体被排除，
不按新闻正负面取舍。同一事件只选一条，最多15条；全部不合格则不推送。
简述40至90字（硬上限180字），只概括候选资料中已有的事实。
候选编号、条数、简述类型/长度及无链接输出由程序校验，标题使用所选候选的原始标题。
2026-09-18 10:00:05 定时失败日志显示候选编号校验失败（旧错误合并了无效/重复编号，
未保留模型原文，无法确认具体类型）。现兼容十进制数字字符串编号，重复编号保留首条并
连续重新编号，不为凑数保留重复新闻；布尔值、非数字和越界编号仍拒绝，并记录错误类别。
26项新闻测试覆盖该兼容和拒绝路径，未调用付费AI或向真实群补发。
模型失败或输出无效时明确报错，不退回非AI精选；符合标准的候选不足时允许少于目标条数，
不编造新闻凑数。RSS 文本作为不可信资料，提示词禁止执行其中指令及补写未提供事实。
AI 仍可能概括不准确，结构校验不能保证语义无误。
当天首次抓取和AI生成完成后，向去重的 `CHAT_GROUP_LIST` 各投递一条相同纯文本日报，
顶部为“每日新闻”和生成完成时间（含时区），正文只含编号、标题、简述，不带来源、
新闻发布时间、URL、窗口说明或故障附注。后续请求复用缓存中的同一生成时间和正文。
空群列表不请求网络，单群入队失败不阻止其他群，并交由现有 scheduler 错误机制报告。

RSS 每频道仅保留最近 30 条，日报是窗口内可获取条目的精选，不承诺覆盖该时段所有
新闻。单源失败只记日志；全部源失败走调度异常报告；无窗口内新闻时只记日志，
不推送旧闻。沿用 coalesce、max_instances=1、300 秒 misfire grace；关机跨过执行时间
不会启动即补发，也不自动重试群发送，避免重复。发送门面成功仅证明入队，不等于 QQ 送达。
成功结果原子写入 `data/daily_news.json`，字段为 `version=1`、带时区ISO时间戳
`generated_at` 和完整返回文本 `digest`。根据生成完成时间在 scheduler 时区的日期判断
是否为当天缓存，服务重启/插件重载后仍复用；失败或无合格新闻不写缓存，后续可重试。
`data/daily_news.lock` 的文件锁保护读取、生成、原子替换和清理，跨线程/进程/重载防止
同日并发重复生成；固定锁文件保留，不作为日报内容删除。临时写入路径为 `.json.tmp`。
`DailyNewsCacheCleanup` 每天00:00只清理非当天/无效缓存，不发送、不调用AI；每次访问
也会清理过期缓存，覆盖服务在零点未运行的情况。生成跨过午夜时归属完成日。
若当天10点前已手动生成，10点自动推送复用这份日报，不重新取窗口或调用AI。
可通过 `DISABLED_MODULE` 的 `DailyNews`、`DailyNewsCacheCleanup` 分别禁用推送/清理。

手动入口使用 `ScheduleModule.trigger` 原生双重注册：精确发送 `每日新闻` 或 `.news`，
普通 worker 调用 `ret(message_pack)`，返回消息链仅回复当前群/私聊，不调用群发分支，
也不要求 `CHAT_GROUP_LIST` 非空。自动执行仍调用 `ret(None)`。
未命中缓存时，手动查看和自动推送统一使用截至生成开始时刻的滚动24小时，窗口只记日志。
2026-09-17 09:54 只读复现旧手动窗口为15日10点至16日10点，而五个 RSS 最早条目
均晚于16日10点，导致全部过滤。这是窗口选择与 RSS 保留范围不匹配，不代表没有新闻。
手动请求无扣费/冷却，忽略引用历史；无新闻或获取失败
返回简短提示，异常详情只记日志。AI请求超时、连接失败、结果校验失败与新闻源获取失败
分别提示。显式 `timeout=240` 为普通 worker 整体超时，45秒只约束AI请求。
手动入口加入后，11 项新闻测试通过，包含群聊/私聊经 registry 和 worker 的 mock 回归；
未发送真实调试消息。
统一滚动窗口后，12 项新闻测试通过；2026-09-17 09:55 本机只读生成日报，
窗口为16日09:55至17日09:55，去重后可用136条、精选15条，随后重启服务加载修复。

源最后核对：2026-09-17，[中新网官方 RSS 目录](https://www.chinanews.com.cn/rss/index.shtml)。
本机只读实测五源 HTTP/XML 和带时区的 `pubDate` 可用；`tests/test_daily_news.py` 覆盖
窗口边界、UTC 换算、去重/限额、部分/全部失败、无新闻、群路由和 cron 幂等注册。
AI 改造后的16项新闻测试通过，包含摘要HTML清理、模型从完整候选池选择并决定排序、
候选编号/条数/简述/链接校验和纯标题简述输出；模型调用全部 mock，未调用付费 API。
该轮全量200项单测通过；首版使用 moonshot / kimi-k3，默认精选15条。
后续10:08日志确认本地代理拒绝连接，回退直连后发生90秒 ReadTimeout；不是RSS为空。
随后按用户要求改为 deepseek-flash 非思考模式、默认直连和45秒请求超时，缩减输入。
DeepSeek `/models` 只读请求返回200且包含 `deepseek-flash`；19项新闻测试通过，
覆盖实际请求参数、代理选择、筛选不足/全空和错误分类，未调用付费生成API做验收。
本轮全量203项单测通过，服务已重启加载DeepSeek及新的筛选标准。
随后新增每日磁盘缓存，25项新闻测试通过：使用临时目录验证时间头、8线程只生成一次、
磁盘复用、次日清理/访问时过期、跨午夜生成、损坏缓存和失败不缓存；未写生产新闻缓存，
未调用付费AI或发送真实测试消息。
缓存版本全量209项单测通过，已重启服务加载每日推送与零点缓存清理任务。
AI接口最后核对：2026-09-17，依据 [DeepSeek模型说明](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)
和 [思考模式](https://api-docs.deepseek.com/zh-cn/guides/thinking_mode/)。
没有发送真实 QQ 测试消息，不将本机抓取成功视为消息端到端验收。

2026-09-17 本机已通过 `systemctl restart tooglebot.service` 加载此任务，确认
`.venv` 解释器、每日10点 cron 注册、WebSocket connected，启动未报告插件加载失败。
本机 scheduler 时区为 `Asia/Shanghai`，目标群来自现有 `CHAT_GROUP_LIST`。
全量 193 项单测通过；按用户要求将所有新闻逻辑合入插件文件后，9 项新闻测试再次通过。
旧模块 import 仍有未关闭文件的 ResourceWarning，本次不改变这些无关模块。

### 通用任务

`ScheduleModule.register()` 将 cron 字段注册到 `native_scheduler`。代码型任务来自
`plugins/schedule.py`、`plugins/daily_news.py`，手动任务来自 `data/schedule.json`。

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

启动和 `.reload` 共用 scheduler reconcile：当前 registry 中的代码任务按稳定 job id
替换，已删除或通过 `DISABLED_MODULE` 禁用的旧代码 job 会移除；`manual:` job 不参与清理，
并从持久化文件补回缺失项。因此刷新插件不会重复注册任务，也不会误删用户手动任务。

`ScheduledMonitor` 每五分钟检查一次，但会先读取 `data/monitor_send.json`，仅并发拉取
实际被订阅的 `earth_quake` / `save_old_otaku` 数据源；没有订阅时不会访问外部网络。
单个数据源异常只记录该源并等待下一轮，不影响 scheduler 或其他源。微博接口明确返回
登录页、401/403 非 JSON 响应或本机 Cookie 缺失时，会被识别为 Cookie 失效：连续失效期
只向所有 `ADMIN_LIST` 私聊一次简短提示，不写重复 traceback；下一次微博请求成功后才允许
再次提示。其他定时任务异常的完整 traceback 仅保存在本机 `log/schedule_err.log` 和服务
日志，所有管理员只收到异常类型和任务名的摘要，避免泄露 Cookie 或响应正文。

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
`ONLY_READ` 群消息在进入本段流程之前即被 worker 丢弃，因此不会写历史、执行主动插件、
经济/审查后处理或普通插件；主动发送不受该入站策略影响。
SQLite 基础 schema 会自动 bootstrap；其他图片下载、模型推理和同步 HTTP 仍可能阻塞
WebSocket 主 event loop。禁言/撤回的自动后处理已通过 `asyncio.to_thread()` offload，
其余同步 I/O 仍是下一轮性能与稳定性重点。

`toogle/msg_proc.py` 还保留图片检测、色图延迟撤回和通用延迟合并转发。屎图不再进行
自动判定、撤回、转发或禁言；`ANTI_SHIT_LIST` 仍由 `VoteMute` 使用，三票后禁言被引用
消息的发送者。管理员“这个不屎”仍可解除图片标记。group/friend recall notice 已写入
撤回历史，其余 notice/request 尚未迁移。

“屎”三人投票禁言在 `ANTI_SHIT_LIST` 群启用，匹配允许 QQ 回复附带的前置 @ 和首尾空白；
被投票者仍由引用确定，不能由 @ 指定。引用消息若未命中本地 history，会通过
`get_group_msg_history` 尝试补取发送者，返回消息 ID 必须与引用一致；每次投票记录群、目标和票数，达到三票
后调用 `set_group_ban`。NapCat 返回“cannot ban owner/admin”等拒绝时会保留异常上下文，
这表示目标身份限制而非机器人自身未获群管理权限。

2026-09-10 只读群历史与服务日志对照确认，旧纯文本正则遗漏 `reply + at + text` 投票。
`tests.test_mute` 已覆盖 OneBot 入站、worker 和 PluginWrapper 两次过滤到第三票禁言的
mock 路径；未执行真实禁言。此前仅直接调用 `VoteMute.ret()` 的测试未覆盖触发过滤。

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

2026-09-18 “查一下”独立改用 `KIMI_SEARCH_MODEL=kimi-k2.7-code` 和
`KIMI_SEARCH_URL=https://api.moonshot.cn/v1`，凭证使用Moonshot profile。
`LLMAdapter.kimi_search()` 获取 `moonshot/web-search:latest` Formula工具声明，
模型返回标准tool call后原样提交name/arguments到fibers，验证succeeded及output/
encrypted_output再回传模型，保留完整assistant（含reasoning_content）。最多4轮模型、
3次搜索；未搜索或回答截断时明确失败，不收费。K2.7不能关闭思考，因此该入口不传
`thinking=disabled`，也不复用旧DeepSeek工具循环。独立Session直连，超时有界。
其他 `.gpt`、每日新闻及旧 `get_web_search()` 辅助函数保持原路由。
只读实测模型列表包含K2.7，Formula工具声明返回web_search；212项单测通过，
未执行付费模型/搜索或真实QQ消息验收。
同日已重启 `tooglebot.service`，服务active/running、WebSocket connected，未报告插件加载失败。
2026-09-19 用户报告持续搜索失败。使用无用户聊天内容的查询实测：工具声明HTTP200、
模型HTTP200，Formula `/fibers` HTTP500，错误为创建/查找lambda session时上游401
Unauthorized。说明模型可用不代表官方搜索执行可用；无法仅据此判断上游授权故障归属。
新增阶段/HTTP状态日志，执行接口拒绝时回复“Kimi官方搜索工具暂不可用”，免扣费/冷却。
随后按用户要求增加自动回退：Kimi搜索执行拒绝、模型/工具协议错误或HTTP/网络失败时，
“查一下”切换 `deepseek-flash` + 现有 `tools/web_search.py` 本地搜索编排，默认
SerpApi→DuckDuckGo→360，沿用已配置源及额度熔断；只有成功搜索并生成回答才计费。
Kimi成功不调用备用，两条链路都失败免扣费/冷却；回复沿用实际搜索源标注。
`SEARCH_FALLBACK_MODEL` 默认deepseek-flash，仅控制此备用链路，不改每日新闻和其他模型。
未发送QQ测试消息，未执行付费搜索/生成实测。
官方接口最后核对2026-09-18：[K2.7](https://platform.kimi.com/docs/guide/kimi-k2-7-code-quickstart)、
[Formula工具](https://platform.kimi.com/docs/guide/use-official-tools)。

`toogle/llm_adapter.py` 是统一 LLM 适配层。DeepSeek、Moonshot、OrcaRouter 均通过同一组
`chat()`、`chat_stream()`、`completion()`、`stream_logic_chain()` 和 `tool_loop()` 方法访问；
业务插件不应直接调用模型 HTTP endpoint，切换 provider 只需修改 profile 参数或根配置。
旧DeepSeek工具适配层会将标准 `tool_calls` 与 DSML 文本形式统一为 assistant/tool 消息，支持
`web_search`/`open_url` 调用；达到搜索轮次上限后追加明确的最终回答指令，页面核验失败
也不会丢弃已有搜索证据，避免协议标记或过程性半截文本泄露到聊天正文。

`tools/web_search.py` 是平台无关的在线搜索契约。它提供同步 `search()` 和不阻塞 event
loop 的 `asearch()`，将 DuckDuckGo 或 SearXNG-like JSON 响应归一为 `SearchResponse` /
`SearchResult`；默认使用 SerpApi Google 结构化 provider，失败自动切 DuckDuckGo，再失败
切 360，其他 provider 仍可配置。SerpApi 返回 `organic_results`，不依赖网页验证码或
HTML 页面结构。
旧 `get_web_search()` 通过 DeepSeek 标准 `function` tool 调用此契约，并将工具结果
回传模型完成多轮链路；配置和密钥规则见 06，解析及两轮 tool-chain 均有 mock 测试，
2026-09-01 已完成本机 SerpApi 查询、DeepSeek tool-chain 和 provider fallback 验收。

`toogle/utils.py` 提供 `text2img()`、`list2img()`、`draw_rich_text()`、
`draw_pic_text()`、缩放和 MP4/GIF 转换。图片缩放使用 Pillow 当前的
`Image.Resampling.LANCZOS` API，兼容 Pillow 10+；字体统一从 `tools/fonts/` 读取。

`tools/pic_recognition.py` 使用 BloomFilter、imagehash 和 FalconsAI ViT INT8 ONNX；推理经 ONNX Runtime 并在 worker 线程执行。平均哈希为空时
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
<!-- Runtime recovery update 2026-09-11 -->
2026-09-11 当前恢复机制：正常运行 `run.sh` 不再因 NapCat 端口未就绪退出，
由适配层退避重连；`RUN_DRY_RUN=1` 仍执行端口预检查。
普通插件和消息后处理受 `PLUGIN_TIMEOUT_SECONDS`（默认 300 秒）限制；
worker 关闭超时覆盖满队列投递退出标记的等待。
事件循环连续阻塞超过 `EVENT_LOOP_TIMEOUT_SECONDS`（默认 600 秒，最小 10 秒）
时，独立线程令进程异常退出，由 systemd 重启。此兜底会丢失内存队列及未保存状态，
不能替代同步插件 I/O 迁移，也不能保证外部操作恰好执行一次。
验证覆盖：`test_worker_flow.py` 的超时恢复与满队列关闭、`test_watchdog.py` 的子进程阻塞退出。
2026-09-11 本机运维配置：主实例开启 fileLog/consoleLog，文件等级 debug、控制台 info；
WebUI 从禁用改为监听 127.0.0.1:6099，经 Nginx 36198 代理，入口 /webui/。
随机登录密钥只保存在实例 workdir/config/webui.json，不写入仓库。
启动脚本保留已有实例配置，重启不会覆盖这些设置。日志不能补回此前关闭期间的事件。
配置字段最后核对：2026-09-11，https://napneko.github.io/config/basic 。
