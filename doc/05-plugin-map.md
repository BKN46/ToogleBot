# 05 业务插件地图

本文按功能域整理 `toogle/plugins/`。如果未来 AI 收到“改某个功能”的需求，优先从这里定位文件，再读具体源码。

## 加载范围

`toogle/index.py` 只扫描 `toogle/plugins/` 顶层 `.py` 文件中的类：

- `MessageHandler`
- `ActiveHandler`
- `ScheduleModule`

子目录如 `compose/`、`others/`、`dnd/`、`thunderskill/`、`waifu_utils/` 通常是辅助库，不会直接成为业务插件，除非顶层插件导入并暴露。

## 基础聊天与群互动

文件：`toogle/plugins/basic.py`

| 类 | 触发/功能 | 主要状态 |
| --- | --- | --- |
| `NowTime` | 世界时间查询。 | 无。 |
| `Swear` | `骂我`，从 `data/swear.txt` 随机取文本。 | `data/swear.txt`。 |
| `Lottery` | 发起、查看、参与、抽取抽奖。 | `data/lottery/*.pickle`。 |
| `SeeRecall` | 查看最近撤回记录。 | `RECALL_HISTORY`。 |
| `Vote` | 发起/查看/结束/参与投票。 | `data/vote/<group>.json`。 |
| `EatWhat` | 记录和随机选择吃什么。 | 通常走 `modify_json_file()`。 |
| `UpdatePersonalInfo` | `.nick` 更新群聊个人信息。 | `data/user_info.json`。 |

适合任务：

- 调整用户交互文案。
- 新增轻量群互动功能。
- 改 JSON 状态结构。

注意：

- `Lottery` 使用 pickle，状态不可直接人工编辑。
- `Vote` 用 `modify_json_file(f"vote/{group}")`，需要确保 `data/vote/` 存在。
- `SeeRecall` 依赖 `plugins/toogle.py` 的撤回事件后处理。

## 管理与风控

文件：`toogle/plugins/admin.py`

| 类 | 触发/功能 | 主要依赖 |
| --- | --- | --- |
| `Mute` | `.ban` 临时禁用成员或某功能。 | `add_mute()`。 |
| `VoteMute` | 对指定群中的目标发起表情/关键词禁言投票。 | `config["ANTI_SHIT_LIST"]`、`VOTE_MUTE_DICT`、`mute_member()`。 |
| `T800Send` | `.kill` 玩笑式管理响应。 | 管理员权限。 |
| `QuitGroup` | `.quit` 让机器人退群。 | Mirai HTTP API。 |
| `AcceptGroupInvite` | `.accept_invite` 接受邀请入群。 | Mirai HTTP API。 |

相关后处理：

- `toogle/msg_proc.py` 中有 NSFW/违规图片检测、延迟撤回、政治内容审查等逻辑。
- `plugins/toogle.py` 收到入群邀请事件时会私聊管理员 `.accept_invite ...`。

注意：

- 这些功能直接调用 Mirai HTTP API，有实际管理副作用。
- 修改前确认 `config["ADMIN_LIST"]` 和目标群配置。

## 经济与会员

文件：

- `toogle/plugins/economy.py`
- `toogle/economy.py`
- `toogle/membership.py`

| 类/函数 | 功能 | 状态 |
| --- | --- | --- |
| `Membership` | 赞助入口提示。 | 无。 |
| `Balance` | `/balance`、管理员加减余额。 | SQLite `qq_user.credit`。 |
| `get_balance/give_balance/take_balance` | gb 余额 API。 | SQLite。 |
| `recv_afdian_msg` | 爱发电 webhook。 | `data/afdian.json`、SQLite。 |

框架层计费：

- 插件类设置 `price > 0`。
- 群号在 `config["ECO_GROUP"]` 时检查和扣费。
- 返回 `MessageChain(no_charge=True)` 可免扣。

## 骰子、数学、TRPG

文件：

- `toogle/plugins/dice.py`
- `toogle/plugins/math.py`
- `toogle/plugins/trpg.py`
- `toogle/plugins/dnd/`

| 文件/类 | 功能 |
| --- | --- |
| `Dice` | `.d20`、`.1d6+1`、优劣势、重骰、爆炸骰、概率分布图。 |
| `WarhammerD20DiceMigrate` | 战锤 d6 到 d20 映射分析。 |
| `Calculator` | 以 `=` 结尾的快速表达式计算。 |
| `Mathematica` | 数学绘图。 |
| `WolframAlpha` | Wolfram Alpha 查询。 |
| `FastPythagorean` | 勾股快速计算。 |
| `FastFallCal` | 英尺掉落时间。 |
| `UnitConversion` | 英/美制单位转换。 |
| `Search5EMagic` | DND 5E 魔法查询。 |
| `CustomDiceTable` | 自定义骰表。 |
| `DPRCalculator` | DND DPR 计算与图像输出。 |
| `Search5ECHM` | 天麟不全书查询。 |

状态和数据：

- `data/dice_table/`
- `data/dnd5e/`
- `toogle/plugins/dnd/search_5e.py`
- `toogle/plugins/dnd/DPRcalculator.py`

注意：

- `Dice.roll()` 最后使用 `eval(dice_str)`，它依赖前置正则和转换限制；扩展时不要放宽用户输入正则。
- 数学/绘图类功能常依赖 matplotlib、scipy、外部 API 或系统字体。

## 图片、素材与娱乐图片

文件：

- `toogle/plugins/pic.py`
- `toogle/plugins/setu.py`
- `toogle/tools/pic_recognition.py`
- `toogle/plugins/compose/`

| 类 | 功能 | 状态/资源 |
| --- | --- | --- |
| `GetQutu` | 趣图随机/列表/指定发送。 | `data/qutu/`。 |
| `LongTu` | 龙图随机/存/删/列表。 | `data/long_img/`、SQLite 权限。 |
| `HistoryTu` | 群黑历史存取和删除。 | `data/history_img/<group>/`。 |
| `Tarrot` | 塔罗牌抽取。 | `toogle/plugins/compose/tarrot.py`。 |
| `ReverseGIF` | GIF 反转。 | PIL。 |
| `GenPixelChinese` | 生成像素字。 | 字体文件。 |
| `GetLuck` | 每日运势图。 | `compose/luck.py`、SQLite。 |
| `GetSetu` | 色图。 | 外部源/配置。 |
| `NFSWorNot` | 判断图片 NSFW。 | `opennsfw2`、BloomFilter。 |

图像工具：

- `toogle.utils.text2img/list2img/draw_rich_text/draw_pic_text`
- `toogle.message.Image`
- `toogle.tools.pic_recognition.detect_pic_nsfw/is_shit_pic`

注意：

- 图片目录中的素材是运行资产。
- `opennsfw2` 依赖 TensorFlow，首次加载较重。
- GIF/视频转换函数使用 OpenCV 和 POSIX `/proc/self/fd`。

## GPT 与 AI 生成

文件：

- `toogle/plugins/gpt.py`
- `toogle/plugins/online_ai.py`
- `toogle/plugins/compose/novelai.py`
- `toogle/plugins/compose/midjourney.py`

| 类 | 功能 | 配置 |
| --- | --- | --- |
| `GetOpenAIConversation` | `.gpt` 对话，支持预设和历史上下文。 | `GPTSecret`、`GPTModel`、`GPTUrl`。 |
| `ActiveAIConversation` | 主动加入聊天，目前实际禁用。 | 同 GPT。 |
| `WhatIs` | `查一下`，调用带搜索工具的 GPT 兼容接口。 | `GPTModel`、`GPTUrl`。 |
| `AIConclude` | 总结 Mirai 日志聊天。 | `GPTModelLarge`、Mirai 日志。 |
| `GetAICompose` | NovelAI 图片生成。 | `NovelAISecret`。 |
| `GetMidjourney` | Midjourney 图片生成/操作。 | 对应 compose 配置。 |
| `GetDoubaoCompose` | 豆包图片/视频生成。 | 外部接口配置。 |

注意：

- `gpt.py` 当前使用 OpenAI Chat Completions 兼容接口，底层是 `requests.post()`。
- `verify=False` 在多处请求中出现，安全性不是重点设计目标，改动时不要无意扩大风险。
- GPT 相关功能有 `price` 和 `interval`，错误返回应设置 `no_charge=True`。
- `AIConclude` 读取 `mirai/logs/`，不是 `MESSAGE_HISTORY`。

## 工具查询与生活信息

文件：`toogle/plugins/tools.py`

| 类 | 功能 | 依赖 |
| --- | --- | --- |
| `StockReport` | 上市企业财报图。 | `compose/stock.py`、外部财经接口。 |
| `StockTrace` | 用户自选股。 | `data/stock.json`。 |
| `BaiduIndex` | 百度指数。 | `others/baidu_index.py`、Cookie。 |
| `GetRainfallWeatherGraph` | 全国降水图。 | `others/weather.py`。 |
| `HealthCalculator` | BMI、心率、BMR 等。 | 无外部依赖。 |
| `PCBenchCompare` | PC 硬件对比。 | `others/pcbench.py`、`data/pcbench/`。 |
| `AnimeSchedule` | 当季新番。 | `compose/anime_calendar.py`、`data/anime/`。 |
| `AnimeDownloadSearch` | DMHY 动漫下载搜索，带翻页/下载交互。 | requests、BeautifulSoup、`WaitCommandHandler`。 |
| `FilmDownloadSearch` | 影视下载搜索。 | 外部站点。 |
| `DateCalculator` | 日期差。 | 无。 |

适合任务：

- 修外部站点解析。
- 调整查询交互。
- 增加小工具类插件。

注意：

- 外部站点结构会变，解析失败通常返回空结果或异常。
- `AnimeDownloadSearch` 会先发结果，再等待同用户后续输入。

## 游戏与垂直领域工具

主文件：`toogle/plugins/other.py`

辅助库：`toogle/plugins/others/`

| 类 | 功能 | 辅助库/状态 |
| --- | --- | --- |
| `RaceHorse` | 模拟赛马。 | `others/racehorse.py`。 |
| `JokingHazard` | 氰化欢乐秀随机卡片。 | `data/joking_hazard.pkl`。 |
| `BaseballGame` | 模拟棒球、注册球员。 | `others/baseball.py`、`data/baseball_players.json`。 |
| `RandomAlbum` | 随机专辑。 | `data/albums.pkl`。 |
| `CSGOBuff` | BUFF 饰品查询。 | `others/csgo.py`、`data/buff_cookie`。 |
| `UpdateBuffCookie` | 管理员更新 BUFF Cookie。 | `data/buff_cookie`。 |
| `CSGORandomCase` | CSGO 开箱模拟。 | SQLite `qq_user.data.csgo_inventory`。 |
| `TarkovSearch` | 塔科夫物品/任务/弹药/地图/利润/BOSS 查询。 | `others/tarkov.py`、`data/tarkov/`。 |
| `ToogleCSServer` | CS 服务器状态/库存/绑定。 | `others/steam.py`、SQLite。 |
| `MinecraftRCON` | Minecraft RCON 命令。 | `others/minecraft.py`、配置。 |
| `Diablo4Tracker` | D4 世界 boss 订阅和查询。 | 代码内/外部请求。 |
| `MarvelSnapZone` | Marvel Snap 工具。 | 外部站点。 |
| `ZLibDownload` | 电子书下载。 | 外部服务。 |
| `GF2DataSearch` | 少前2技能词条搜索。 | `others/gf2.py`、`data/gf2_mcc_data/`。 |
| `LawQuickSearch` | 法律速查。 | `data/laws/`。 |
| `MilkywayidleSearch` | 银河奶牛价格/等级/强化工具。 | `others/milkywayidle.py`、`data/milkywayidle/`。 |
| `MilkywayidleJokes` | 银河奶牛笑话。 | 数据文件。 |
| `UpdateWeiboCookie` | 管理员更新微博 Cookie。 | `data/weibo_cookie` 或相关缓存。 |
| `NFSWorNot` | 判断图片 NSFW。 | `toogle/tools/pic_recognition.py`。 |
| `MagnetParse` | 磁链解析/预览。 | `others/magnet.py`、libtorrent。 |

注意：

- `other.py` 非常大，修改时尽量局部化。
- 外部站点、Cookie、代理、Cloudflare 相关问题常出现在这个域。
- 长耗时模拟或查询常通过 `bot_send_message()` 分段主动发送。

## 战雷/ThunderSkill

文件：

- `toogle/plugins/wt.py`
- `toogle/plugins/thunderskill/`

| 类 | 功能 |
| --- | --- |
| `WTVehicleLine` | 战雷载具研发路线资源。 |
| `ThunderSkill` | 快查 Thunder Skill 近期战绩。 |
| `WTDatamine` | 战雷导弹拆包数据查询。 |
| `WTWinRate` | 历史模式国家胜率。 |

数据：

- `toogle/plugins/thunderskill/vehicle_tree.json`
- `toogle/plugins/thunderskill/vehicle_price.json`
- `data/wt/`
- `config["WT_DATAMINE_GIT"]`

## ACG 对象系统

文件：

- `toogle/plugins/waifu.py`
- `toogle/plugins/waifu_utils/waifu_random.py`
- `toogle/plugins/waifu_utils/waifu_card.py`
- `toogle/plugins/waifu_utils/waifu_battle.py`

主类：`GetRandomAnimeFemale`

功能：

- 随机老婆/老公。
- 查看/锁定对象。
- 排行。
- 属性筛选。
- NTR/换妻等互动。

状态：

- SQLite `qq_user.waifu`
- SQLite `qq_waifu`
- 图片缓存 `data/buffer/`
- 外部 ACG/Bangumi 数据源。

## remake

文件：

- `toogle/plugins/remaking.py`
- `toogle/plugins/remake/remake.py`
- `toogle/plugins/remake/remake_data.csv`
- `toogle/plugins/remake/continent_skin.json`

主类：`GetRemake`

功能：

- `/remake` 随机生成人生重开结果。
- 数据来源 README 中说明为世界银行。
- 历史结果进入 SQLite `remake_data`。

## 代码执行插件

文件：`toogle/plugins/runPython.py`

| 类 | 功能 |
| --- | --- |
| `RunPython` | 简易 Python 脚本运行，做了敏感关键词屏蔽。 |
| `RunLua` | 简易 Lua 脚本运行。 |

注意：

- 这是高风险模块。
- 不要为了功能便利放宽敏感库、`eval/exec`、文件系统或网络访问限制。
- 修改后应专门做安全回归测试。

## 调试插件

文件：`toogle/plugins/debug.py`

包含多种调试/实验类插件，如：

- `DebugPlugin`
- `RecallDebugPlugin`
- `CounterPlugin`
- `DarkstarServerPing`
- `WitsAndWagers`
- `PoliticsOrNot`
- `AsyncDebug`
- `gbLuckyPocket`
- `TooglePicGen`

注意：

- 这类插件可能依赖临时数据或个人服务。
- 正式功能不要直接塞进 `debug.py`，除非确实是实验。

## 已废弃或历史模块

路径：`toogle/plugins/deceprated/markov.py`

拼写为 `deceprated`，保留历史 Markov 聊天模型。当前不在顶层扫描范围内，除非有顶层导入。

