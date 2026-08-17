# 06 配置、数据与持久化

## 配置加载现状

根 `configs.py` 按仓库根定位 `.env`，忽略空行/注释，以 `split("=", 1)` 保留值中的
等号；列表仅用 `ast.literal_eval()` 解析，其他值保持字符串。`reload_config()` 原位更新
共享字典，因此已经 import `config` 的模块也能看到新值，并同步刷新代理配置。

尚未完成的是全量 typed schema 和普通运行配置的环境变量覆盖；新增 key 必须在使用处
显式转换/校验，不能重新引入 `eval()`。

## 本机私有扩展

环境专用实现、说明和测试统一放在根 `private/`，该目录及其位于公开模块目录中的兼容
入口都由 `.gitignore` 排除。公开源码、配置默认值、文档索引和测试基线不得依赖这些文件；
私有配置只保存在本机 `.env`，不能写入公开默认值或测试 fixture。

## 连接和进程配置

| Key | 使用方 | 含义/现状 |
| --- | --- | --- |
| `WS_URL` | `adapter/server.py` | 可选完整正向 WebSocket URL；设置时优先于拆分字段。 |
| `WS_HOST`、`WS_PORT`、`WS_PATH`、`WS_TOKEN` | `adapter/server.py` | 拆分的 NapCat 正向 WebSocket 配置；默认 path 为 `/`。 |
| `HTTP_HOST`、`HTTP_PORT`、`HTTP_TOKEN` | `adapter/http_request.py` | NapCat HTTP action endpoint。 |
| `NAPCAT_QQ_BIN` | `tools/start_napcat_main.sh` | systemd 启动的 QQ/NapCat 可执行文件，默认 `/root/Napcat/opt/QQ/qq`。 |
| `NAPCAT_MAIN_WORKDIR` | `tools/start_napcat_main.sh` | 主账号 NapCat 配置、日志和二维码目录；默认 `~/.local/state/tooglebot/napcat-main-<account>`。 |
| `NAPCAT_MAIN_QQ_DATA_DIR` | `tools/start_napcat_main.sh` | 主账号 QQ 登录数据目录；默认 `~/.config/QQ-ToogleBot-Main-<account>`，首次授权后不得清空。 |
| `API_HOST`、`API_PORT`、`API_PUBLIC_PORT` | `api/api.py` / `tooglebot-api.service` / nginx | Flask 内部监听 `127.0.0.1:36002`，nginx 对外代理到 `:36001`。 |
| `RECV_QUEUE_SIZE`、`SEND_QUEUE_SIZE`、`WORK_QUEUE_SIZE` | adapter queue/worker | 有界队列容量，非法值回退到内置默认值。 |
| `WORKER_NUM` | `adapter/worker.py` | 同一 event loop 的 worker task 数，当前默认 1；并发审计完成前不要提高。 |
| `BOT_TIMEZONE` | `toogle/scheduler.py` | APScheduler 时区，默认 `Asia/Shanghai`。 |
| `ADMIN_LIST` | 多处 | 管理员 QQ 列表，通常应为字符串列表。 |
| `SUPERUSERS` | `plugins/runPython.py` | 解释器高权限用户。 |
| `CONCURRENCY` | 暂无有效使用 | 已明确保留多插件命中，应删除该旧配置。 |
| `ENVIRONMENT` | 暂无有效使用 | 历史环境标识。 |

`MIRAI_QQ` 已不属于新配置且运行时读取已移除。帮助命令固定前缀不需要 self id；如需
`@机器人` 前缀，可暂用明确的 `BOT_QQ` / `QQ_ACCOUNT`，长期应来自 NapCat lifecycle。

双账号验收使用 `NAPCAT_MAIN_ACCOUNT`、`NAPCAT_SENDER_ACCOUNT`、`NAPCAT_TEST_GROUP`；
主动探针另用 `NAPCAT_ACTIVE_PROBE_ENABLED/TRIGGER/REPLY/EXPECT`。这些值只存在于本机
`.env`/CI secret，源码和 NapCat JSON 模板不得包含真实账号或群号。

本地 systemd unit 由 `tools/install_systemd_services.sh` 安装。主账号启动器只从本机
`.env` 读取主账号、HTTP/WS token，在独立 workdir 生成 NapCat JSON；HTTP/WS 默认只绑定
`127.0.0.1`，WebUI 默认关闭。unit 文件不包含 token，且通过 `KillMode=control-group`
管理 `xvfb-run` 和 QQ 子进程。主账号 NapCat 配置关闭自身 console/file 日志，避免首次
扫码时的二维码 URL 进入 systemd journal；二维码仅临时保存在 workdir 的 `cache/qrcode.png`。

API 的 nginx location 片段安装到 `/etc/nginx/conf.d/tooglebot-api-locations.conf`，只允许
由已有 `36001` server 代理 `/api`、`/send` 和 `/afdian`；不要把 Flask 内部端口直接暴露到
公网，也不要把片段放在 `/root` 下绕过 SELinux。

## 权限、群组和后处理

| Key | 用途 |
| --- | --- |
| `ONLY_READ` | 只读群列表；入站群消息不触发 history、后处理、主动插件或普通插件，主动发送不受影响。 |
| `BLACK_LIST` | 完全阻止指定用户触发插件。 |
| `ADMIN_GROUP_LIST` | 管理员群，绕过部分冷却/权限。 |
| `DISABLED_MODULE` | 按插件类名禁用动态加载。 |
| `ECO_GROUP` | 启用余额检查/聊天收益的群。 |
| `CHAT_GROUP_LIST` | 允许主动聊天插件运行的群。 |
| `GROUP_LIST` | 主群列表和部分群发逻辑。 |
| `NSFW_LIST`、`ANTI_NSFW_LIST`、`ANTI_SHIT_LIST` | 图片后处理和排行策略。 |
| `CENSOR_LIST` | 内容审查群。 |
| `TOOGLEPICGEN_GROUP_LIST` | 允许普通成员使用 TooglePicGen 的群；管理员不受此列表限制。 |
| `HISTORY_SAVE_PATH` | `MESSAGE_HISTORY` pickle 文件。 |

这些 key 当前有的使用 `config[...]`，缺失会直接异常；有的使用 `get()`。配置 schema
应区分必需、可选和插件专属配置，并在启动报告中一次性显示缺失项。

## 外部服务配置

- GPT：`GPTSecret`、`GPTModel`、`GPTModelLarge`、`GPTUrl`。
- NovelAI：`NovelAISecret`。
- 豆包：`DOUBAO_API_KEY`、`DOUBAO_IMAGE_MODEL`、`DOUBAO_VIDEO_MODEL`。两个模型 key 在
  `configs.CONFIG_DEFAULTS` 中有当前默认值，可由 `.env` 覆盖；插件内不再写死模型名。
- 战雷：`WT_DATAMINE_GIT`。
- 塔科夫：`TARKOV_MARKET_SECRET`。
- 反爬和代理：`SCRIPING_ANT_TOKEN`、`REQUEST_PROXY_HTTP`、`REQUEST_PROXY_HTTPS`。
- Minecraft：`MCRCON_HOST`、`MCRCON_PORT`、`MCRCON_PASSWORD`。
- CS：`CSGO_SERVER_HOST`、`CSGO_SERVER_PORT`、`CSGO_MYSQL_HOST`、
  `CSGO_MYSQL_USER`、`CSGO_MYSQL_PASSWD`。
- debug 插件：`DARKSTAR_SERVER_HOST` / `DARKSTAR_SERVER_PORT` 配置 A2S 查询目标；
  `TOOGLEPICGEN_BASE_URL` / `TOOGLEPICGEN_ACCESS_TOKEN` 配置生图服务。主机、端口、URL、
  token 和下述日志路径都只能保存在本机 `.env`，公开配置没有实际值或地址兜底；缺失时
  对应功能明确返回未配置，不会尝试连接预设目标。

debug 插件还有两个本机行为配置：`WNW_ANSWER_DELAY_SECONDS` 控制竞猜题目与答案的等待
秒数，`TOOGLEWORLD_LOG_PATH` 指向管理员可读取的 ToogleWorld 日志。使用处会转换并校验
数值或路径；文件不存在时返回功能不可用，不在 import 阶段打开文件。

密钥不得出现在日志、fixture、异常通知或文档中。管理员通知里的原始 webhook/body
也应先脱敏。

## 数据分层

### 仓库静态资源

- `plugins/remake/remake_data.csv`、`continent_skin.json`。
- `plugins/thunderskill/vehicle_tree.json`、`vehicle_price.json`。
- `tools/fonts/*.ttf`。

这些必须随代码部署，路径应相对模块文件计算。remake 和 thunderskill 的旧
`toogle/plugins/...` 引用已经迁移。

### 运行状态和缓存

`data/` 整体被 `.gitignore` 忽略，典型内容：

| 路径 | 所有者 |
| --- | --- |
| `data/toogle.db` | `toogle/sql.py`，用户余额、remake、waifu 等。 |
| `data/history.pkl` | 消息历史。 |
| `data/user_info.json` | 群内用户昵称/资料。 |
| `data/schedule.json` | 用户创建的手动定时任务。 |
| `data/afdian.json` | 会员订单状态。 |
| `data/debug_cnt.json` | debug 撤回统计人工校正计数。 |
| `data/gbLuckyPocket.json` | 各群当前 GB 红包、领取成员和份额。 |
| `data/wnw.data` | “猜来猜趣”题目/答案交替行题库；当前仍是本机运行数据，不进入 git。 |
| `data/not_shit_pics.json` | 管理员人工确认不是屎图的图片哈希豁免列表；优先于 `data/shit_bloom` 判定。 |
| `data/*_bloom` | 图片重复、SFW、黑名单 BloomFilter。 |
| `data/setu_record*.json` | 图片贡献排行。 |
| `data/send_api.json` | 主动发送 API 的密钥、群和 qpm。敏感。 |
| `data/lottery/`、图片目录 | 抽奖和群图片功能。 |
| `data/dnd5e/`、`wt/`、`pcbench/`、`milkywayidle/` 等 | 插件离线数据和缓存。 |

`plugins/others/milkywayidle.py` 已从自身 `__file__` 解析仓库根，所有银河奶牛文件固定在
`data/milkywayidle/`，不再通过 `../../../data` 越出仓库；有路径回归测试。

因为 Docker 挂载 `./data:/bot/data`，全新部署得到的可能是空目录。项目需要明确的
bootstrap/迁移创建必需 JSON、BloomFilter 和可选插件数据；SQLite 基础 schema 已能在
首次连接时幂等创建，但后续版本 migration 仍待建立。不能依赖开发者本机被忽略的文件。

### 日志

- `toogle/logger.py` 写 `logs/bot.log`，按天轮转。
- 旧工具和插件仍写 `log/call.log`、`err.log`、`slow.tsv`、API 日志等。
- `plugins/debug.py` 可选读取旧 `log/recall.log` 做撤回统计；文件不存在时降级为无统计数据。

Mirai 日志读取器和对应统计脚本已经删除；聊天总结改读当前 `MESSAGE_HISTORY`。迁移目标
仍是统一 `log/`/`logs/` 和结构化事件字段。

## SQLite

`toogle/sql.py` 每次操作连接仓库 data root 的 `toogle.db`。首次连接在进程锁保护下执行
幂等 `sqlite.sql`，创建 `qq_user`、`qq_waifu`、`remake_data`；空库 bootstrap 已有测试和
本机实测。未使用且没有 schema 的旧 SQL scheduler 方法已删除，手动任务只使用 JSON。

当前 wrapper 通过字符串拼接生成 SQL，`data_str_proc()` 只移除单引号和 emoji，
不构成参数化防注入。新增用户输入查询必须使用 `?` 参数；不要复制现有拼接风格。

结构变更要提供版本化 migration，并在真实数据副本上验证。不要提交本地 `guild1.db*`
或 `data/toogle.db`。

## Docker 数据安全

当前没有 `.dockerignore`，`COPY . .` 会把 `.env`、数据库、日志、venv 和本地缓存
送入 Docker build context，并可能烘进镜像，即使运行时再用 volume 覆盖也无法消除
镜像层泄露。修复部署前必须增加 `.dockerignore`，并以显式 COPY 清单为优先方案。
