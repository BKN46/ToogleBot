# Mirai -> NapCat 迁移 TODO

更新时间：2026-07-17

基线：当前工作树为 NapCat 迁移主线；旧行为参考
`origin/archived-mirai2-version`。本清单按阻断程度排序，`[x]` 只表示有源码或本地验证
依据，不能用“已写骨架”代替端到端完成。

## P0：阻断构建或核心收发

### 1. 恢复可重复安装和启动

- [x] 明确项目为直接运行源码的非打包应用，设置 `[tool.uv] package = false`，锁文件
  根项目为 `virtual`；`uv sync` / `uv run` 不再尝试构建不存在的 `ToogleBot/tooglebot` 包。
- [ ] 审计并声明所有直接依赖。当前源码直接 import 但 `pyproject.toml` 未完整声明的
  至少包括 `poyo`、`python-a2s`、`libtorrent`、`lupa`、MySQL client、`thulac`、
  `wordcloud`、`tqdm`；`networkx`/`numpy` 目前只是被其他包间接带入。
- [ ] 区分核心依赖和可选插件依赖；缺少可选依赖时只禁用对应插件并在启动报告说明。
- [ ] 提供不含密钥的 `.env.example` 和配置校验，clean 环境可启动到等待 NapCat。

验收：空缓存环境执行 `uv sync --frozen` 成功；`uv run python -m compileall ...`
成功；`uv run python bot.py` 不因构建、缺核心依赖或旧配置 key 在 import 阶段退出。

### 2. 修复 WebSocket transport 闭环

- [x] `recv_loop()` 对文本帧执行 `json.loads()`；非法帧记录脱敏错误并继续收帧。
- [x] `send_loop()` 对 action dict 执行 `json.dumps()`，不把字典直接传给 `ws.send()`。
- [x] 将主 loop 的同步 `queue.Queue.get(timeout=5)` 改为有界 `asyncio.Queue`；
  主循环不再轮询或阻塞 WebSocket event loop。
- [x] 为 action 添加唯一 `echo`，将 action response 与等待方关联；事件和响应分流。
- [x] transport 对单帧解析/转换异常做隔离，记录脱敏 frame 类型后继续；不能因一个未知
  消息段或坏事件永久结束 `recv_loop()`。
- [x] 保持 `parse_event()` 不访问网络；reply 从本地 history 补全，forward id 的远程补全
  不在收帧协程执行；空响应不再访问首项。
- [x] 2026-07-17 对本地 NapCat 4.15.4 正向 WebSocket 服务完成脱敏实测：query token
  可鉴权，`/`、`/ws`、`/bot/ws` 都能执行 `get_status` 并按 echo 返回成功响应。
- [x] 正向 WebSocket 支持 `WS_URL` 或 host/port/path 配置及 query token，移除固定
  `/bot/ws`；反向 WebSocket 模式尚未实现，按部署需求再决定是否支持。
- [x] 实现带退避的断线重连、连接 ready 状态、任务取消和有界发送队列。

验收：mock WebSocket 测试完成“一条群文本事件 -> MessagePack -> send_group_msg action
-> 成功 response”，并覆盖 malformed JSON、action 失败、断线重连和关闭，无 event
loop 5 秒卡顿。

### 3. 修复插件启动阻断

- [x] `plugins/meta.py` 移除 `MIRAI_QQ`；帮助命令使用固定前缀，可选从明确 self id 配置
  增加 @ 前缀。
- [x] 修复帮助 registry 初始化顺序；`plugins.meta` reload 后不会把
  `EXPORT_PLUGINS` 重置为空；移除未定义的 `get_help_regex`，改为注入只读 registry。
- [x] `plugins/basic.py`、`plugins/remaking.py` 从正确模块 import `interval_limiter`。
- [x] `adapter/worker.py` 从根 `configs` 读取 `config`，移除错误的
  `from networkx import config`。
- [x] 删除 `toogle/scheduler.py` 未使用的 `poyo` import。
- [x] 将插件发现从 import 副作用改为显式 registry build：基于模块路径、每次重新发现、
  稳定排序，只注册当前模块定义的类，并以 `module + qualname` 去重。
- [x] 模块 import、插件构造分别隔离错误；首次 import 不无条件 reload，构建完成后原子
  发布 registry 快照，运行期 reload 不与 worker 遍历竞争。
- [x] 移除损坏的双 wrapper / `copied_plugin_list`；指定 reload 当前安全地重建整个 registry，
  后续再优化为单模块事务。
- [x] loader 不启动 worker/scheduler；删除 `adapter.worker` 模块末尾的 `worker_start()`，
  由 `bot.py` 在 registry 健康后显式启动并在失败时完整回收。
- [x] 启动时输出 loaded/disabled/failed 汇总；`meta` / `basic` 核心失败会保留旧快照并
  阻止启动。

验收：在最小数据 fixture 下导入插件 registry，无未预期失败；帮助页列出的类与
`export_plugins` 一致；错误通知能正确读取 `ADMIN_LIST`。从任意 cwd 连续 build/reload
两次得到相同顺序，模块顶层只执行约定次数，单个坏插件不破坏上一版健康快照。

2026-07-17 修复证据：本地 venv 连续 load/reload 均为 normal=79、active=1、schedule=3，
failed=0；帮助页 smoke 通过。缺可选依赖/数据的聚合模块改为功能级降级。详见 02、05。

### 4. 修复插件上移后的资源路径

- [x] `plugins/remake/remake.py` 不再读取 `toogle/plugins/remake/*`。
- [x] `plugins/thunderskill/get_wt_data.py` 不再读取 `toogle/plugins/thunderskill/*`。
- [x] `plugins/others/milkywayidle.py` 使用由 `__file__` 定位的仓库 `data/milkywayidle/`，
  移除上移后多退一层的 `../../../data` 路径和 `sys.path` 注入。
- [ ] 核对 DND 路径（如 `toogle/data/dnd/...`）和所有 import 时打开的文件。
- [ ] 所有仓库静态资源用 `Path(__file__)` 定位；运行数据用统一 data root。

验收：从任意当前工作目录运行资源单测；remake、战雷路线和至少一个字体渲染冒烟
成功；缺可选 data 时给出明确禁用原因而非只在动态 loader 中消失。

### 5. 使 Docker 配置可用且不泄密

当前阶段按项目要求仅使用本地 NapCat/QQ 进程；本节 Docker 构建、启动和持久化验收
在代码迁移完成后再执行。2026-07-17 的构建尝试已在镜像完成前取消，未启动容器。

- [ ] 增加 `.dockerignore`，排除 `.env`、`.git`、`venv`、数据库/WAL、日志、缓存和
  本地 `data/`；优先把 `COPY . .` 改为显式代码/资源清单。
- [ ] 修复容器内 `uv run` 触发项目构建失败的问题。
- [ ] 统一 NapCat HTTP/WS 模板、`MODE`、容器监听端口、compose 映射和 `.env` 中端口。
- [ ] 验证 entrypoint 能生成/保留 OneBot 配置，不用固定 sleep 代替 readiness。
- [ ] 增加 healthcheck，至少区分 QQ/NapCat、WS 连接和 worker 是否健康。
- [x] 提供只读登录探针和单元测试：`tools/napcat_login_check.py` 强校验参数/环境配置
  账号，接口依据和流程见 `doc/10-napcat-login-test.md`。
- [x] 2026-07-17 本地进程为 `3888217194` 完成首次人工扫码授权；NapCat Core 4.15.4、
  NTQQ 3.2.21-42086，`get_status`、`get_login_info`、`get_group_list` 均通过。
- [x] 2026-07-17 从官方 Release 更新 NapCat Core 到 4.18.9，SHA-256 与发布资产一致；
  QQ 版本和登录数据未改动，主账号与第二账号均无扫码恢复并通过双账号只读探针。
- [x] 2026-07-17 将本地 NTQQ 更新到 3.2.28-48517：因上游 deb 链接已失效，从带
  NapCat-Docker 官方仓库 SLSA 来源证明的 v4.18.9 amd64 OCI 层离线提取并核对 layer
  SHA-256，全程未启动 Docker。两个账号均无扫码快速登录，`nc_get_packet_status`
  返回 `status=ok, retcode=0`；旧 3.2.21-42086 目录完整保留用于回滚。
- [x] 2026-07-17 保留本地 QQ 数据后重启进程，无需再次扫码，快速登录及 HTTP/WS 服务
  自动恢复。
- [x] 2026-08-06 正式主账号通过 `tooglebot-napcat.service` 完成首次人工扫码；只读
  `tools/napcat_login_check.py --check-group-list` 确认 online/good、登录账号和群列表，
  随后 `tooglebot.service` 通过 WS 启动 worker。账号值仅保存在本机 `.env`。
- [x] 2026-08-06 重启 NapCat unit 后在 180 秒内无扫码恢复登录；ToogleBot 预检重试后
  重新加载 registry、启动 worker 并连回 WS。
- [x] 2026-07-17 启动本地第二 NapCat 实例并扫码登录发送账号 `3560612394`；两个账号
  均通过 online/good、账号和群 `1070265969` 校验。发送端调用 `send_group_msg` 发送
  `.help ping`，主账号命中帮助插件并回复，发送端历史确认新回复来自 `3888217194`。
- [ ] 使用持久化卷自动执行容器 restart/force-recreate，两次均在 180 秒内通过登录探针，
  全程无需再次扫码；此项按当前约束延后到代码迁移完成后。
- [ ] 解决当前宿主机 NapCat FFmpeg native addon 要求 `GLIBC_2.29`、且系统无可用
  FFmpeg CLI 的问题；在解决前将图片/音视频转换标记为未验收。
- [ ] 将本地 NapCat WebUI 从全接口监听收敛到回环地址或增加主机防火墙规则；HTTP/WS
  当前已仅监听 `127.0.0.1`。
- [x] 2026-08-06 为本地进程提供可控的停止/守护方式：新增
  `deploy/systemd/tooglebot-napcat.service`、`tooglebot.service` 和安装脚本；NapCat
  使用 `KillMode=control-group` 回收 `xvfb-run`/QQ 子进程，ToogleBot 按 WS 依赖自动重试。
  首次账号授权仍需按文档人工扫码，不能把 unit active 等同于账号 online/good。

验收：clean Docker build 不包含本机密钥/数据库；`3888217194` 首次登录、自动重启/
重建登录、消息往返和 volume 持久化通过；错误账号会在任何消息/管理测试前失败。

## P1：恢复 Mirai 时代核心行为

### 6. 完成消息段转换

- [x] 入站 `at` 读取 OneBot `data.qq`，`qq=all` 转 `AtAll`。
- [x] 出站 `AtAll` 使用标准 `at` 段；文本和 @ 已有 fixture。
- [x] 按 NapCat `OB11MessageMarkdown` schema 新增内部 `Markdown(content)`，覆盖入站、
  出站、`json_to_msg()` 和 fixture 单测。
- [ ] 完成 Markdown 真实群投递。2026-07-17 依次在 Core/QQ 4.15.4/42086、
  4.18.9/42086、4.18.9/48517 上各测试一次，均发生 `sendMsg`/HTTP timeout；主实例
  本地历史生成消息 `2099370023`、`798967633`、`83519291`，但独立观察账号未收到。
  2026-07-17 官方兼容表已明确 Markdown “发是在双层合并转发内，无法直接发送”，
  三次直发失败不再作为账号/风控问题继续排查。先完成 `node` 双层转发出站，再以第二
  账号历史验证嵌套 Markdown；不得继续直发试错。
- [ ] 为图片 URL/base64/file 增加 fixture 和本地 NapCat 媒体冒烟。
- [x] 新增无损 `JsonCard`/Ark 内部元素并完成 `type=json` 双向 fixture；字符串/对象载荷
  会校验 JSON object、深拷贝保存，显示和 `to_dict()` 不泄露卡片正文。2026-07-17 使用
  `send_group_ark_share` 生成合法 Ark 后经项目序列化发送，独立账号在配置群确认完整 JSON
  等价的新消息 `1683463177`（主端 action message `393834187`）。
- [ ] 补 `face`、`mface`、`dice`、`rps` 的入站显示和出站转换；商城表情入站还要覆盖
  NapCat 以带 emoji 元数据的 `image` 段上报的形态。
- [ ] 补 `record`、`video`、`file` 内部元素及 fixture；真实发送需等待 FFmpeg/媒体环境
  阻断解除。`onlinefile`、`flashtransfer` 走专用 action，不与普通 `File` 混用。
- [ ] 小程序卡片采用 `get_mini_app_ark -> json segment` 两阶段流程，并复用 PacketBackend
  前置检查；联系人/群推荐卡片采用 `contact` 或 Ark 生成 action。不得把 action 返回的
  Ark JSON 当成已发送结果。
- [ ] `poke` 作为 notice/action 接入，不实现成普通出站消息段；内联键盘当前只有点击
  action、没有公开 OB11 keyboard segment，取得脱敏 fixture 前不新增内部类型。
- [x] reply 使用 `data.id` 查询本地历史；查询为空不再访问 `msg[0]`；正确填充
  `MessagePack.quote` 和 sender 的 `user_id`。
- [ ] 合并转发使用 NapCat 支持的 `node`/action，支持 Markdown 所需双层节点并移除固定
  伪造 forward id；`node` 不能与普通 segment 混发。
- [ ] 明确 XML 和其余未知段的支持/降级策略。NapCat 4.18.9 虽保留 `xml` schema，但
  出站 converter 返回 `undefined`；现有 `Xml` 只能兼容旧数据，不能声称可发送。
- [x] `MessageChain.plain(..., quote=..., no_charge=True)` 及消息链相加正确保留结果 flags。
- [x] 恢复 GPT 计费失败语义：“查一下”仅匹配显式命令；`.gpt`/“查一下”的输入、能力、
  超时及服务错误均 `no_charge/no_interval`，并有 worker 层不扣余额/不写冷却测试。
- [x] 豆包图片/视频模型移到根配置默认值并允许 `.env` 覆盖；API key 改为调用时校验，
  付费请求、下载和转换均有 timeout/offload，异常不回显接口 body 且不扣费。
- [x] 按 2026-07-17 NapCat Apifox 契约重构群文件上传：业务层经平台无关门面调用
  `upload_group_file`，校验 HTTP 与 OneBot 结果，视频临时文件始终清理；字段、失败响应、
  私聊不误调用和上传失败 GIF 降级均有 mock 测试。真实群文件上传按安全约束尚未执行。

### 7. 恢复群聊、私聊和事件

- [x] `bot_send_message(MessagePack, ...)` 继承原消息类型；私聊回复目标是 member id，
  不能向 group 0 发群消息。
- [x] 实现 group/friend recall notice 写入 `RECALL_HISTORY`，并覆盖 group recall 单测。
- [ ] 按业务需要实现 poke、成员进退群、群名片、好友申请、群邀请；删除旧 Mirai
  `event.type` 分支或改成 OneBot dict/内部事件类型。
- [ ] heartbeat/lifecycle 只更新连接状态，不进入插件队列。
- [x] self message 不进入插件，私聊历史按 `private_<user_id>` 隔离；已有单元测试。
- [ ] 用真实 NapCat 脱敏 fixture 固化 self-event 的实际 `post_type` 和字段。
- [ ] 对 notice/request 建立自动测试和明确的权限策略。

### 8. 统一插件分发和并发语义

- [x] worker 和插件基类统一使用 `re.search`。
- [ ] 对所有非 `^` 开头 trigger 做业务回归测试。
- [x] 明确保留同一消息允许多个插件触发；旧 `CONCURRENCY` 配置后续移除。
- [ ] 明确 `white_list`、`thread_limit`、`to_me_trigger` 等历史属性是实现还是删除。
- [x] 移除“10 个线程各自一个 event loop、共享同一插件实例”的模型，改为单 event loop
  + 有界 asyncio queue，默认一个 worker。
- [ ] 将同步 HTTP、SQLite、模型和 CPU 渲染按调用显式 async 化或 offload。豆包图片/视频
  生成轮询、下载、GIF 转换和群文件上传已用 `asyncio.to_thread()` 完成，其他插件待审计。
- [x] 修复真实群消息暴露的 clean data 阻断：首次 SQLite 连接在锁保护下幂等执行
  `sqlite.sql`；空库会创建 3 张基础表并有临时库单测、本机空库实测。版本升级 migration
  仍作为 P2 独立任务保留。
- [x] 修复 scheduler 插件作为普通命令注册后的触发契约；真实消息曾在遍历
  `DailySetuRanking` 时因缺少 `is_trigger()` 报错，现由 `ScheduleModule` 统一提供并有单测。
- [x] 固定 history、主动插件、普通插件、经济/审计的执行顺序和错误边界；一个
  `chat_earn`/主动插件异常不能终止整个 `process_loop()`。
- [x] quote 原文通过派生消息交给插件，不得原地修改共享 `MessagePack`；覆盖
  history 不污染和 post-process 并发测试。
- [x] 避免每次主动发送创建未跟踪线程；worker 启停纳入显式生命周期。
- [ ] 同一用户余额扣除和冷却更新具备并发一致性。

### 9. 完成 scheduler programmable 迁移

- [x] `bot.py` 显式启动和关闭 `native_scheduler`，job id 重复注册保持幂等。
- [x] `program=true` 使用 `Group`、`Member` 构造合法虚拟 `MessagePack`，并通过正常
  plugin registry 分发。
- [x] 覆盖普通发送、可触发、单次成功/失败、重复注册、创建者隔离删除、空管理员异常、
  3 个代码任务边界和 start/stop；registry smoke 为 3 个唯一 job。
- [x] 定义 `BOT_TIMEZONE`（默认 `Asia/Shanghai`）、`coalesce=True`、`max_instances=1`、
  `misfire_grace_time=300`，避免阻塞恢复后并发补跑。
- [x] 清理 scheduler 中旧 NoneBot 注释、正文型 job id、重复 JSON 读写和旧 adapter
  `WORK_QUEUE`；手动任务改用 UUID/legacy hash 与原子持久化。
- [x] 监测任务按 `monitor_send.json` 的实际订阅惰性拉取数据源；空订阅不访问网络，
  单源失败隔离且不影响 scheduler 主循环。
- [x] 地震监测从已返回 405 的 `news.ceic.ac.cn/speedsearch.html` 迁到当前官方
  `www.ceic.ac.cn/data/data.json`，恢复 TLS 校验并覆盖新字段 schema；2026-07-17
  只读实时请求和解析通过。

### 10. 恢复 API 和后处理生命周期

- [x] 2026-08-06 将 Flask API 定为独立进程并接入 `tooglebot-api.service` 的 start/stop；
  unit 依赖 ToogleBot worker，不并入 `bot.py` 的 asyncio loop。
- [x] 2026-08-06 统一 `API_HOST`/`API_PORT` 配置，移除本机 `.env` 中未使用的
  `API_HTTP_PORT`；Flask 内部监听 `127.0.0.1:36002`，由 nginx 对外暴露 `:36001`，
  `curl http://127.0.0.1:36001/api` 返回 200。
- [ ] `/afdian` 增加验签和敏感数据脱敏；`/send` 并发限流、输入校验、发送失败响应。
- [ ] 明确 `chat_earn`、图片检测、内容审查哪些默认开启；不要保留“代码存在但调用注释”。
- [ ] 将启动通知定义为每进程一次或每连接一次，并防止重连刷屏。
- [x] `bot.py` 捕获顶层 `KeyboardInterrupt`；`Ctrl-C` 仍执行 task/worker/scheduler 清理，
  不再把正常调试停止显示为 Python traceback。

### 11. 清理运行时 Mirai 遗留

- [x] `AIConclude` 改读当前 `MESSAGE_HISTORY`，删除 Mirai 日志读取器和失效的
  `statistics/chat_analysis.py`。
- [x] 删除未使用的 `MessageChain.to_mirai()`、scheduler NoneBot/调试注释、SQL scheduler
  死方法、未启用 B 站监测分支和 `.mirai` 图片扩展。
- [x] 删除未被发现或引用的旧 Markov 模块、HTTP 手工调试入口和过期插件地图描述；
  修复图片识别临时文件泄漏、空哈希 BloomFilter 污染及 `regist_*` 历史拼写。
- [x] 更新/删除运行代码中 `toogle/plugins`、Mirai、NoneBot 和旧 scheduler 名称；源码
  扫描无命中。
- [x] 扫描当前 Python 运行目录，NoneBot/Mirai import、旧 scheduler 名称和真实验证账号
  硬编码均为 0；归档行为只保留在 git 分支和历史说明。
- [x] 清理运行目录未使用 import、错误 `sys.path` 注入、调试入口和生成缓存；Python
  3.12 严格 SyntaxWarning 编译、53 个单元测试及 79/2/3 registry smoke 通过。

## P2：工程化和长期维护

### 12. 建立自动测试

- [ ] `tests/fixtures/onebot/` 覆盖群/私聊、文本、图片、@、引用、转发、notice、meta、
  action success/failure。
- [ ] 扩展消息模型、PluginWrapper 权限/余额/冷却和 scheduler 业务测试；registry、quote
  不可变、队列生命周期和重复注册已有基础单测。
- [x] 登录 HTTP probe、WebSocket frame/action 和 event -> plugin -> group action 使用 mock，
  普通测试不连接真实 QQ、群管理或付费 API。
- [x] 增加配置驱动的双账号/群真实消息检查工具及虚构 ID 单测；默认只读，只有显式
  `--confirm-send` 才发送 command/active 场景配置文本并等待配置主账号新回复。
- [x] Markdown smoke 默认只读；显式发送强制由不同的配置账号观察群历史，发送账号的
  本地回显不能作为送达证据。
- [ ] 为重要爬虫保存脱敏 fixture，把实时冒烟与确定性解析测试分开。
- [ ] CI 至少运行 compile、测试、`git diff --check` 和旧依赖/路径扫描。
- [ ] 自托管串行 job 按 `doc/10-napcat-login-test.md` 定期执行主账号阶段 B 和双账号
  阶段 D；Docker 启用后增加阶段 C。token 和登录数据不进入普通 CI artifact。

### 13. 配置、数据和数据库治理

- [x] 用 `ast.literal_eval` 和 `split("=", 1)` 替换配置 `eval`/截断逻辑，按仓库根读取、
  支持注释并原位 reload；全量 typed schema/普通运行配置环境覆盖仍待补。
- [x] 提供 SQLite 基础 schema bootstrap；必需 JSON、BloomFilter 和可选插件数据的统一
  bootstrap 仍待补。
- [ ] 为 SQLite 建立版本 migration；使用参数化 SQL，覆盖余额并发和失败回滚。
- [ ] 统一 `log/` 与 `logs/`，结构化记录连接、action、插件和调度状态。
- [ ] pickle 历史加载失败时备份而非直接覆盖。

### 14. 安全和阻塞 I/O

- [ ] 管理 HTTP client 统一 timeout、状态/retcode 校验、重试边界和脱敏日志。HTTP 状态、
  OneBot `status/retcode` 及群文件 120 秒 timeout 已统一，重试和结构化脱敏日志仍待补。
- [ ] 审计同步 requests、模型推理和 CPU 渲染，不阻塞主 event loop。
- [ ] 隔离或移除 `RunPython` / `RunLua` 用户代码执行风险。
- [ ] 移除 `draw_rich_text()` 等位置的 `eval()`。
- [ ] 管理员异常通知不包含 token、Cookie、webhook 完整 body 或用户隐私。

## 已完成的迁移基础

- [x] `bot.py` 已移除 NoneBot driver 和 Mirai adapter 注册，改为 asyncio 入口骨架。
- [x] 新增 `adapter/` 的 WebSocket、HTTP、队列、worker、后处理和调度注册模块骨架。
- [x] 业务插件主目录从 `toogle/plugins/` 上移到 `plugins/`，多数 Python import 已调整。
- [x] Mirai 执行文件、旧启动脚本、`mirai_extend.py` 和 `nonebot2_adapter.py` 已从当前
  工作树移除。
- [x] 新增标准 logging 封装，核心迁移文件不再依赖 NoneBot logger。
- [x] 字体和图片识别工具已移动到 `tools/`，多数字体路径已更新。
- [x] 项目目标 Python 已提升到 3.12，并生成 `uv.lock`。
- [x] 2026-07-17 使用 Python 3.12 对 `bot.py`、`configs.py`、`adapter/`、`api/`、
  `toogle/`、`plugins/`、`tools/`、`statistics/` 执行 `compileall`，语法检查通过。
- [x] 2026-07-17 依据 NapCat Apifox 的 `get_status` / `get_login_info` schema，新增
  `3888217194` 登录探针、纯单元测试和分阶段自动化验收文档。
- [x] 2026-07-17 真实登录与本地重启登录通过；已确认账号 `3888217194`、昵称 `Geeha`，
  基础 HTTP action 和正向 WebSocket action 可用。
- [x] 2026-07-17 完成正向 WebSocket JSON/action、显式 registry、单 event loop worker、
  scheduler 第一轮修复；自动测试、79/2/3 零失败 registry smoke、帮助页 smoke 和真实
  NapCat 只读 action 往返通过。
- [x] 2026-07-17 使用 `3560612394` -> 群 `1070265969` -> `3888217194` 完成真实
  `.help ping` 插件往返；同时登记了 SQLite schema 与 scheduler 命令触发问题。
- [x] 2026-07-17 将验证账号/群移出代码并从本机 `.env` 注入；双账号完成主动插件
  `message_post_process -> ActivePathProbe -> outbound -> group history` 真实往返。
- [x] scheduler 完成第二轮修复和 3-job registry/lifecycle smoke；监测/会员阻塞 I/O
  offload，微博依赖移除 eval 并补 timeout，SQLite 空库 bootstrap 通过。
- [x] 新增本地 `run.sh`：固定项目 cwd、自动选择 Python、检查 `.env`/NapCat WS、阻止
  重复启动并通过 `exec` 保留信号语义；当前阶段不调用 Docker。

## 里程碑

- **M0 可构建**：P0.1 完成。
- **M1 消息闭环**：P0.2、P0.3 完成，mock transport 文本往返通过。
- **M2 核心兼容**：全部 P0 + P1.6-P1.9 完成，隔离测试号消息矩阵通过。
- **M3 可部署**：P1 全部完成，Docker、持久化、API 和健康检查通过。
- **M4 迁移完成**：P0/P1 清零，P2 中测试、配置和数据 bootstrap 完成，README 可移除
  “迁移中”提示。
