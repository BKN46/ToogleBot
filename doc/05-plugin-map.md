# 05 业务插件地图

`toogle/index.py` 只自动扫描 `plugins/*.py`。下面先列注册入口，再列辅助目录。

## 顶层插件

| 文件 | 插件/功能 | 主要依赖或状态 |
| --- | --- | --- |
| `plugins/meta.py` | ping、帮助列表 | 通过只读 provider 使用当前 registry；旧 `MIRAI_QQ` 依赖已移除。 |
| `plugins/admin.py` | 插件刷新、临时禁用、投票禁言、退群、取消屎图标记 | `.reload` 仅管理员可用，刷新配置、全部插件 registry 和代码型 scheduler job；投票禁言由 `ANTI_SHIT_LIST` 控制；图片不再自动判定后撤回禁言。其余功能涉及 NapCat 禁言/退群 HTTP action、图片哈希等高副作用。 |
| `plugins/autodl.py` | AutoDL 容器实例 Pro API 管理 | `.autodl` 管理命令覆盖实例创建、列表、详情、状态、开关机、释放和私有镜像；仅 `ADMIN_LIST` 管理员可用，网络请求在 worker 线程中执行。 |
| `plugins/basic.py` | 随机选择、世界时间、骂人、抽奖、反撤回、投票、吃什么、昵称 | `data/lottery/`、`user_info.json`、撤回事件。 |
| `plugins/currencyExchange.py` | 货币转换 | 外部汇率 API。 |
| `plugins/daily_news.py` | 每日10点AI新闻精选、零点缓存清理 | 同文件包含 RSS/AI/日期缓存及定时插件；结果含生成时间头、标题与简述，当天首次成功生成后复用；`每日新闻` / `.news` 仅回复当前会话。 |
| `plugins/debug.py` | 微博/撤回统计/服务器查询/竞猜/异步等待/日志/GB 红包/生图 | 当前 11 个插件类；高权限调试命令使用 `admin_only`，外部 I/O 已移出 event loop，专属配置和本地数据见 06。 |
| `plugins/dice.py` | 通用骰子、战锤骰制转换 | NumPy、SciPy、Matplotlib。 |
| `plugins/economy.py` | 赞助入口、余额管理 | SQLite 余额、会员。 |
| `plugins/gpt.py` | GPT 对话、主动聊天、“查一下”、总结 | `.gpt` 使用现有配置；“查一下”独立使用 `kimi-k2.7-code` 与Kimi官方Formula搜索，附搜索标注，失败免扣费/冷却；不改每日新闻或全局模型。 |
| `plugins/math.py` | 数学绘图、计算器、Wolfram、勾股、坠落、单位转换 | Matplotlib、Wolfram 辅助模块。 |
| `plugins/online_ai.py` | NovelAI、Midjourney、豆包图片/视频 | 豆包模型由根配置选择；重型步骤 offload，视频原文件经群文件 action 上传并附 GIF 预览。 |
| `plugins/other.py` | 游戏、站点、服务器、法律、NSFW、磁链等垂直功能 | 最大业务文件；依赖 `plugins/others/` 和大量本地数据。 |
| `plugins/pic.py` | 趣图、龙图、黑历史、塔罗、GIF、像素字 | 群图片目录、字体、图像处理。 |
| `plugins/remaking.py` | 科学 remake | `plugins/remake/`、SQLite；仓库静态资源已按模块路径定位。 |
| `plugins/runPython.py` | Python/Lua 解释器 | `exec`、signal timeout、可选 lupa。安全边界较弱。 |
| `plugins/schedule.py` | 色图排行、会员补余额、外部监测、用户定时 | APScheduler、`data/schedule.json`、消息发送。 |
| `plugins/setu.py` | 每日运势、色图 | Pixiv/外部图源、SQLite、图片素材。 |
| `plugins/tools.py` | 股票、百度指数、天气、健康、硬件、新番、下载、日期 | `compose/`、`others/`、Cookie 和外部站点。 |
| `plugins/trpg.py` | DND 魔法、骰表、DPR、不全书 | `data/dnd5e/`。 |
| `plugins/waifu.py` | 随机 ACG 对象、排行和互动 | `waifu_utils/`、SQLite、图片缓存。 |
| `plugins/wt.py` | 战雷路线、ThunderSkill、拆包、胜率 | `thunderskill/` 和 `data/wt/`；仓库 JSON 已按模块路径定位。 |

## 当前加载审计

“查一下”在Kimi不可用时自动回退DeepSeek Flash与本地搜索编排（沿用SerpApi/
DuckDuckGo/360配置）；Kimi成功不调用备用，备用必须取得搜索证据才返回付费回答。

2026-09-15 修复 `remaking.py` 缺少根配置 `config` 导入导致故事生成分支
抛出 NameError；未调用真实模型、生图 API 或写入 remake 数据进行验收。

磁链解析结果使用 ForwardMessage：摘要速度按 KB/s 或 MB/s 显示，图片只发送
最大边 960px 的 2x3 合成图。文件列表独立成节点，从 torrent 根目录起展示两层，
最多 50 个文件；同层文件夹优先，再按大小降序排列，文件夹大小包含所有后代。
此展示变更仅做本地验证，未发送真实 QQ 消息。

2026-09-16 磁链预览当前实现：PyAV 通过可 seek 的 `TorrentVideoReader` 按实际读取
范围请求 torrent 分片，取代固定首尾分片和按文件大小比例估算截图位置。元数据取得前
默认禁用内容下载；读取仅返回经 libtorrent 校验且 `read_piece` 成功的数据，不读取
稀疏文件空洞。六张截图共用容器索引，从目标时间前的关键帧解码至目标时间；已下载
分片复用，内存缓存最多四片。只有六张全部解码成功才返回预览，失败免扣费、免冷却。
最小粒度为完整 torrent 分片，另有 FFmpeg 探测/32 KiB 读取缓冲开销，不承诺理论最小
字节数；无索引、长 GOP 等资源可能需要更多数据。单次请求分片总量上限 128 MiB，
默认元数据等待 180 秒、总读取/解码检查期限 720 秒，超过即失败而非退回整文件下载。
`tests/test_magnet_preview.py` 覆盖跨文件偏移、分片复用、下载限额/超时/读取错误，
真实 libtorrent 的零默认优先级和 partfile 读取，以及带较大尾部 moov、前置索引 MP4、
MKV 和可变帧大小的本地视频经真实 PyAV 解码得到六帧。未发送 QQ 消息。

2026-09-16 后续按用户提供磁链做本机临时目录诊断：一个 2,053,875,272 字节 MP4
的分片大小为 2 MiB，原策略下载 0、1、978、979 号分片后，ffprobe 退出码为 1，
报 `moov atom not found`，JSON 为 `{}`，复现旧代码的 `'format'` 异常。
其 `moov` 从文件偏移 2,048,675,173 开始，长度 5,200,099 字节，覆盖 976 至 979
号分片；对照下载补齐 976、977 后，ffprobe 成功读出时长 6017.058725 秒。
此对照结果确认原首尾固定分片策略不足，是上述按需读取实现的回归依据。
该轮诊断仅验证元数据与时长探测，临时下载已清理，未发送 QQ 消息。

同日新实现本机实测（Python 3.12、PyAV 17.1.0）：该视频成功生成六帧和 960x810
合成图，请求 16 个分片、32,220,873 字节（30.73 MiB，约文件大小 1.57%），耗时
93.52 秒；临时数据已清理。手动管理的 torrent 会话在 DHT 启动后重新 announce，
避免初始路由表未就绪时一直等待首次查询；无 peer 仍会明确超时。
该统计是应用请求的唯一完整分片总量，不包含协议开销或网络重传，不代表所有资源的
固定下载比例。全量 184 项单测通过；已有无关模块仍报告未关闭文件的 ResourceWarning。

接口最后核对：2026-09-16，依据 [PyAV 文件对象与缓冲](https://pyav.basswood.io/docs/stable/api/_globals.html)、
[PyAV seek/解码](https://pyav.basswood.io/docs/stable/api/container.html) 和
[libtorrent 分片优先级/read_piece](https://libtorrent.org/reference-Torrent_Handle.html)。

2026-08-17 对不含本机私有扩展的公开 registry 执行 smoke，得到 90 个普通、2 个主动、
3 个定时插件，4 个按配置禁用，`PluginLoadReport.failed` 为 0；其中 11 个 debug 插件类均已
注册。帮助页可以从当前 registry 生成转发结果。

Git 忽略的 `private/` 及其本机兼容入口不计入上述公开基线；本机插件总数不能写回公开
registry 审计结果。

此前阻断整个模块的可选条件现在按功能降级：

| 条件 | 当前行为 |
| --- | --- |
| 无 `libtorrent` 或 `av` | `other.py` 仍加载，磁链插件返回依赖缺失且不扣费。 |
| 无 `mysql-connector` | CSGO 查询/库存功能返回依赖缺失，其他 `other.py` 插件保留。 |
| 无 `python-a2s` | 仅 CS 服务器状态查询不可用。 |
| 无 `data/baidu_cookie` | `tools.py` 仍加载，百度指数调用时提示未配置。 |
| 无 DND 法术/不全书数据 | 自定义骰表和 DPR 仍加载；两个数据查询命令提示未配置。 |
| 无 GF2 缓存目录 | import 时使用空缓存，显式更新时再创建目录。 |

这证明 registry 可构建，不代表每个外部 API 或数据插件已通过业务冒烟。下一步仍需维护
预期 manifest，并为各插件输出 available/degraded 状态。

2026-07-17 已核对并恢复两个付费功能的产品边界：

- “查一下”只匹配显式 `^查一下`，价格 12 gb、冷却 600 秒；2026-09-18起使用
  `KIMI_SEARCH_MODEL` 和Kimi Formula搜索，只有获得联网证据和完整模型回答才结算，
  输入超限、超时、主/备用模型失败均免扣费且不写冷却。
- `.gpt` 价格仍为 5 gb、冷却 600 秒；输入/能力校验失败和模型服务错误同样不结算。
- 豆包图片/视频价格仍为 50 gb、冷却 300 秒。图片成功即正常结算；视频要求群文件上传
  成功才结算，上传失败但 GIF 预览成功时返回预览并免扣费。私聊没有群文件目标，也按
  预览降级并免扣费。

以上结算和 action 使用 mock/fixture 验证，尚未调用真实付费模型或在真实群上传文件。

`plugins/debug.py` 的导入、registry、微博转发结构、撤回统计、A2S 查询、竞猜题库、GPT
审查、等待消息、日志 tail、GB 红包全部份额以及 TooglePicGen HTTP/poll/result 路径已有
14 条 mock 单测。测试没有调用真实微博、GPT、生图服务或 QQ 发送；相关功能仍取决于 06
中的本机配置、外部服务和运行数据。

## 组合与渲染

`plugins/compose/` 提供顶层插件复用的外部 API 和图像合成：

| 文件 | 职责 |
| --- | --- |
| `anime_calendar.py` | 抓取季度新番并渲染日历。 |
| `luck.py` | 每日运势图。 |
| `midjourney.py` | Midjourney 任务提交、查询和操作。 |
| `novelai.py` | NovelAI 请求和图片结果。 |
| `stock.py` | 股票搜索、财务数据、报告渲染。 |
| `tarrot.py` | 塔罗数据和牌面渲染。 |
| `wolfram_alpha.py` | Wolfram WebSocket 查询和 pod 图片拼接。 |

这些模块不应 import NapCat；输入输出尽量保持普通 Python 数据、PIL 或 bytes。

## 垂直辅助模块

`plugins/others/`：

| 文件 | 服务对象 |
| --- | --- |
| `baidu_index.py` | 百度指数和 Cookie。 |
| `baseball.py` | 棒球模拟和球员数据。 |
| `csgo.py` | BUFF、开箱、CS 服务器/MySQL。 |
| `gf2.py` | 少前 2 数据抓取和搜索。 |
| `magnet.py` | torrent/magnet 元数据和预览。 |
| `milkywayidle.py` | 银河奶牛市场、等级和翻译数据。 |
| `minecraft.py` | Minecraft RCON。 |
| `pcbench.py` | 硬件榜单下载、CSV 查询和对比。 |
| `racehorse.py` | 赛马模拟及图片输出。 |
| `steam.py` | Steam ID 转换。 |
| `tarkov.py` | 塔科夫 GraphQL/市场数据与渲染。 |
| `weather.py` | 全国降水图抓取和缓存。 |
| `weibo.py` | 微博内容抓取。 |

修改这类爬虫时，要把“网络请求”和“纯解析”拆开，使用保存的脱敏 fixture 测试解析，
不要依靠实时站点作为唯一验证。

## DND、战雷和 ACG

| 目录 | 文件 | 说明 |
| --- | --- | --- |
| `plugins/dnd/` | `DPRcalculator.py`、`search_5e.py`、`search_chm.py`、`gen_chm_jpg.py` | DPR 绘图、法术/不全书索引和离线生成工具。依赖 `data/dnd5e/`。 |
| `plugins/remake/` | `remake.py`、`remake_data.csv`、`continent_skin.json` | remake 核心算法和仓库静态数据。 |
| `plugins/thunderskill/` | `datamine.py`、`get_stat.py`、`get_winrate.py`、`get_wt_data.py`、`parse_stat.py`、`main.py` | 战雷数据抓取、解析、绘图和查询；两个 JSON 是仓库静态数据。 |
| `plugins/waifu_utils/` | `waifu_random.py`、`waifu_card.py`、`waifu_battle.py` | ACG 数据请求、卡片/排行渲染和互动战斗。 |

## 工具和统计

- `tools/pic_recognition.py`：NSFW 模型调用、图片平均哈希、BloomFilter 重复/黑名单；
  无法计算的空哈希不会写入 BloomFilter，也不会被判为命中。
- `tools/napcat_login_check.py`：只读轮询 NapCat 状态并校验配置/参数账号，详见 10。
- `tools/start_napcat_sender.sh`、`tools/napcat_sender_config/`：按配置账号启动本地发送
  NapCat 实例，并动态生成账号文件名；模板不含账号和密钥。
- `tools/napcat_dual_account_check.py`：默认只读校验配置的双账号和群；显式确认后执行
  command/active 场景往返，详见 10。
- `tools/fonts/`：所有图像渲染共用字体，是代码资源，不是运行缓存。
- `statistics/call_analysis.py`：分析 `log/call.log` 调用次数。
- `statistics/word_cloud.py`：从统计 JSON 生成词云，依赖未完整声明。

## 定位新功能

- 简单群交互：优先放 `basic.py`。
- 纯数学/格式转换：`math.py` 或独立顶层插件。
- 通用信息查询：`tools.py`。
- 大型垂直域：新增顶层 `<domain>.py`，实现类放辅助子目录，避免继续扩大 `other.py`。
- 图像/API 组合函数：`compose/`，保持与消息框架解耦。
- 仅离线生成数据：放相应辅助目录或 `statistics/`，不要被插件加载器扫描。
