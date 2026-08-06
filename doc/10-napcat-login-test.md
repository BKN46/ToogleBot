# 10 NapCat 登录自动化验收

本文定义 NapCat 登录和真实消息测试的唯一流程。被测主账号、发送账号和专用群分别由
`NAPCAT_MAIN_ACCOUNT`、`NAPCAT_SENDER_ACCOUNT`、`NAPCAT_TEST_GROUP` 配置；源码、Shell、
测试 fixture 和 NapCat JSON 模板不得写死真实值。不得用生产 QQ/群替代验证资源。
QQ 扫码/风控步骤不应绕过，但授权后的重启、账号校验和健康检查必须自动完成。当前代码
迁移阶段只运行本地 NapCat/QQ 进程，Docker 阶段明确延后。

## 官方接口依据

最后核对：2026-07-17。

NapCat 的 [Apifox 接口文档](https://napcat.apifox.cn/) 由项目更新时自动生成。实现或
升级 NapCat 后应重新核对接口，不能把本页示例永久当作协议真相。

| 验收动作 | 官方接口 | 本方案断言 |
| --- | --- | --- |
| 检查运行状态 | [`POST /get_status`](https://napcat.apifox.cn/226657083e0) | `status=ok`、`retcode=0`、`data.online=true`、`data.good=true`。 |
| 核对登录账号 | [`POST /get_login_info`](https://napcat.apifox.cn/226656952e0) | `data.user_id` 严格等于该 endpoint 的配置角色账号。 |
| 可选验证业务 API | [`POST /get_group_list`](https://napcat.apifox.cn/226656992e0) | 成功且 `data` 为列表；允许空列表。 |
| 双账号消息冒烟 | [`POST /send_group_msg`](https://napcat.apifox.cn/226656598e0) | 两端账号和群先匹配配置；主账号新回复必须可从发送端群历史确认。 |

Apifox 文档描述 action schema，不一定描述当前部署使用的 WebSocket URL/path。连接地址、
access token 和正向/反向 WS 模式仍需结合 NapCat 配置及脱敏实测确认。

## 已准备的探针

`tools/napcat_login_check.py` 只调用无副作用的 HTTP action：

1. 轮询 `get_status`，直到 online/good。
2. 调用 `get_login_info`，强校验账号。
3. 可选调用 `get_group_list` 验证登录后的基础 action。
4. 超时或账号不符时返回非零状态；永不输出 access token。

默认值：

| 参数/环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `--base-url` / `NAPCAT_TEST_HTTP_URL` | `http://127.0.0.1:6543` | 本地 NapCat HTTP endpoint，不是 ToogleBot Flask API。 |
| `--account` / `NAPCAT_TEST_ACCOUNT` / `NAPCAT_MAIN_ACCOUNT` | 无，必填 | 预期登录账号；脚本拒绝非正整数和 endpoint 返回的不一致账号。 |
| `--token` / `NAPCAT_TEST_TOKEN` | 空 | NapCat access token，只通过 secret 环境变量注入。 |
| `--timeout` | `180` | 总等待秒数。首次扫码可提高到 600。 |
| `--interval` | `3` | 轮询间隔秒数。 |
| `--check-group-list` | 关闭 | 开启后额外验证群列表响应类型。 |

运行纯单元测试：

```bash
python -m unittest tests/test_napcat_login_check.py
```

对已启动的 NapCat 运行探针：

```bash
export NAPCAT_TEST_HTTP_URL=http://127.0.0.1:6543
export NAPCAT_TEST_TOKEN='<从安全环境注入>'
python tools/napcat_login_check.py --account "$NAPCAT_MAIN_ACCOUNT" --check-group-list
```

## 双账号消息工具

`tools/napcat_dual_account_check.py` 从环境变量、指定 `.env` 或 CLI 读取角色：

| 角色 | 配置 | 默认 endpoint |
| --- | --- | --- |
| 被测主机器人 | `NAPCAT_MAIN_ACCOUNT` | `http://127.0.0.1:6543` |
| 消息发送端 | `NAPCAT_SENDER_ACCOUNT` | `http://127.0.0.1:6544` |
| 专用测试群 | `NAPCAT_TEST_GROUP` | 两端必须都在群内 |
| 主动场景 | `NAPCAT_ACTIVE_PROBE_TRIGGER/EXPECT` | 默认场景 |
| 普通命令场景 | `NAPCAT_COMMAND_PROBE_TRIGGER/EXPECT` | 可选回归 |

工具默认只执行两端的 `get_status`、`get_login_info`、`get_group_info`，不会发送消息：

```bash
export NAPCAT_MAIN_HTTP_TOKEN='<从安全环境注入>'
export NAPCAT_SENDER_HTTP_TOKEN='<发送实例配置 token；空 token 时不设置>'
uv run python tools/napcat_dual_account_check.py --scenario active
```

只有显式确认才调用一次 `send_group_msg`。工具先保存发送前的群历史基线，然后要求出现
一条基线中不存在、发送者为配置主账号且包含场景配置标记的新回复：

```bash
uv run python tools/napcat_dual_account_check.py \
  --scenario active --confirm-send
```

Markdown 消息由已登录主实例发送，并从 `.env` 读取主账号、独立观察账号和测试群。
工具必须按模块运行；默认仅验证主账号、群和项目序列化，不发送，也不要求第二实例
在线：

```bash
venv/bin/python -m tools.napcat_markdown_check
venv/bin/python -m tools.napcat_markdown_check --confirm-send
```

执行 `--confirm-send` 前必须先用 `tools/start_napcat_sender.sh` 启动第二实例。发送验收
以独立观察账号的发送前群历史为基线；仅当该账号的历史出现来自配置主账号、完整
content 相同且不在基线中的新 Markdown 段时才能判定通过。action 返回 message id 或
主账号本地历史出现消息都不能单独证明送达；action timeout 后继续观察但不自动重发。

超时失败后不得自动重发，避免故障期间刷群。token 只通过环境变量注入，工具不会输出。

## 阶段 A：本地首次授权

首次登录必然可能需要扫码或设备确认，因此这是唯一允许人工介入的阶段：

1. 使用独立测试主机/runner 和专用 NapCat/QQ 数据目录；不要复用生产机器人目录。
2. 从 QQ 安装目录启动本地进程。当前验证机可以直接使用 systemd unit（它会隔离
   `NAPCAT_MAIN_WORKDIR` 和 QQ 数据目录）：

   ```bash
   sudo tools/install_systemd_services.sh
   sudo systemctl start tooglebot-napcat.service
   ```

   也可以按上面的 unit 配置手工执行 `tools/start_napcat_main.sh`。二维码保存在
   `NAPCAT_MAIN_WORKDIR/cache/qrcode.png`，不会写入仓库。
3. 同时以 `--timeout 600` 启动登录探针。
4. 操作者扫描进程生成的二维码，并在手机 QQ 完成安全确认。
5. 只有探针同时确认 online/good 和配置主账号一致才算首次授权成功。
6. 保留专用 QQ/NapCat 数据目录，不导出到 git、普通 CI artifact 或公共对象存储。

二维码、登录凭证、Cookie、ClientKey、access token 和 WebUI token 不得写入持久测试
日志。用于当次人工扫码的二维码只能临时展示，登录后不得归档。

## 阶段 B：本地自动重启登录

在阶段 A 成功且不删除 QQ 数据目录的前提下：

1. 通过 `tooglebot-napcat.service` 停止测试进程，并确认 `3456`、`6099`、`6543`
   已释放。不要使用可能误杀其他 QQ 实例的全局 `pkill qq`。
2. 使用与阶段 A 相同的账号、安装目录和 QQ 数据目录重新启动本地进程。
3. 自动执行：

   ```bash
   python tools/napcat_login_check.py \
     --account "$NAPCAT_MAIN_ACCOUNT" \
     --timeout 180 \
     --check-group-list
   ```

验收：

- 全程不扫码、不点击 WebUI。
- 180 秒内 online/good。
- 登录号严格等于配置主账号。
- 进程重启前后使用同一专用 QQ/NapCat 数据目录。
- 停止动作能回收全部 QQ/Xvfb 子进程，退出异常会由 systemd journal 记录。

## 阶段 C：Docker 自动重建登录（延后）

本阶段等代码迁移完成后才启用，用于验证容器可重建而登录状态由 volume 持久化：

```bash
docker compose stop tooglebot
docker compose up -d --no-deps --force-recreate tooglebot
python tools/napcat_login_check.py --account "$NAPCAT_MAIN_ACCOUNT" --timeout 180
```

自动化不得运行 `docker compose down -v`、删除 QQ 配置目录或清理登录凭证。重新授权是
显式人工维护操作，不属于日常 CI。

## 阶段 D：ToogleBot 联动

基础群文本已启用，执行顺序固定：

1. 主账号按阶段 A/B 登录并通过 `tools/napcat_login_check.py`。
2. 使用仓库模板启动本地发送实例：

   ```bash
   ./tools/start_napcat_sender.sh
   ```

   默认配置来自 `tools/napcat_sender_config/`：账号来自 `.env`/环境变量，NapCat 配置写到
   `~/.local/state/tooglebot/napcat-sender-<account>`，HTTP 仅监听 `127.0.0.1:6544`，WebUI 关闭。
   首次启动扫描终端二维码，图片同时保存到脚本输出的 `cache/qrcode.png`。

3. 模板只在运行配置不存在时复制，不覆盖已有 token/登录实例配置。当前 4.18.9 的
   `NAPCAT_WORKDIR` 可隔离 NapCat 配置；NTQQ native 仍可能在共享 `~/.config/QQ` 下按账号
   保存数据，需要更强隔离时使用单独 Linux 用户，不能假设 `--user-data-dir` 覆盖全部数据。
4. 确认 `BLACK_LIST` 不包含配置发送账号，`CHAT_GROUP_LIST` 包含配置测试群，并设置唯一的
   active probe trigger/reply；再用 `./run.sh` 启动主机器人。
5. 先运行双账号工具的默认只读模式；通过后由操作者执行一次 `--confirm-send`。
6. 工具必须同时确认发送 action 的 message id 和主账号新回复的 message id。失败时保留
   脱敏时间/错误类别，不保存群内其他消息正文。
7. 私聊、图片、引用、转发、撤回和管理 action 不由这条基础冒烟顺带执行，需各自授权。

账号和群 ID 不是凭证，但不应成为代码默认值；token、二维码和 QQ 登录数据仍必须保密。
普通 CI 只运行虚构 ID 单元测试，自托管 L3 job 才能注入配置并连接两个本地实例。

## CI 设计

- L1/普通 CI：只运行探针单元测试和 mock HTTP，不启动 QQ。
- L3/自托管 runner：当前保留专用本地 QQ 数据目录并串行执行阶段 B；Docker 启用后再
  增加阶段 C。
- 首次授权 job：只能人工触发，允许扫码，成功后转入定期阶段 B job。
- 定期 job：建议每日或 NapCat/Dockerfile 更新时运行，失败后停止后续消息测试。
- 并发锁：同一账号只允许一个登录验收 job，避免 QQ 顶号和状态污染。
- 证据：保存时间、NapCat 版本、online/good、脱敏账号和耗时；不保存响应中的凭证。

## 当前状态

2026-07-17 在 CentOS 8 x86_64 本地主机完成阶段 A/B/D：

2026-08-06 在同一主机为正式主账号使用 `tooglebot-napcat.service` 完成首次扫码授权；
`tools/napcat_login_check.py --check-group-list` 通过，随后 `tooglebot.service` 已启动并
报告插件 registry、worker、scheduler 和 NapCat WebSocket 均 ready。账号值只保存在本机
`.env`，不在本文或 unit 中记录。

同日重启 NapCat unit 后，保留同一 QQ 数据目录即可在 180 秒内无扫码通过相同探针；
ToogleBot 在 WS 端口短暂不可用时按 `run.sh` 预检策略重试，随后重新连回 NapCat。

- NapCat Core 4.15.4、NTQQ 3.2.21-42086 首次使用 `3888217194` 扫码登录成功；同日
  NapCat Core 更新到 4.18.9，随后将本地 NTQQ 更新到 3.2.28-48517。主账号和第二账号
  均沿用现有数据无扫码快速登录；旧 Core 和旧 QQ 均保留同级备份用于回滚。
- 腾讯历史 deb 地址失效后，本次 QQ 程序从 NapCat-Docker v4.18.9 amd64 OCI 镜像中的
  QQ 安装层离线提取。镜像 SLSA provenance 指向官方 `NapNeko/NapCat-Docker` 仓库，
  layer SHA-256 为
  `b6e45bc3e921b46f8b7649e1bf672e1ab25b4c098d8a5ddefd8513816a94d663`；仅访问 OCI
  registry 和解包文件，没有创建或启动 Docker 容器。
- `get_status` 返回 online/good，`get_login_info` 账号严格匹配，`get_group_list` 成功。
- 4.18.9/48517 的主、副实例启动日志均确认 `NativePacketClient Hook 初始化成功`；主实例
  `nc_get_packet_status` 返回 `status=ok, retcode=0`。
- 正向 WebSocket `127.0.0.1:3456` 的 `/`、`/ws`、`/bot/ws` 都能完成 query token
  鉴权及带 echo 的 `get_status` action。
- 保留 QQ 数据后重启本地进程，快速登录成功且不需要再次扫码。

当前结论与已知问题：

- 宿主机 glibc 低于 FFmpeg native addon 所需的 `2.29`，且没有可用 FFmpeg CLI；基础
  登录和 OneBot API 不受影响，图片/音视频转换尚不能判定可用。
- WebUI 当前监听所有接口的 `6099`，HTTP/WS 则只监听 `127.0.0.1`；WebUI 应收敛监听
  或由主机防火墙限制。
- 2026-08-06 已安装 `tooglebot-napcat.service` 和 `tooglebot.service`；两个 unit 均
  使用控制组停止，NapCat 首次扫码和 online/good 探针仍需单独完成。unit 不把账号、token
  或二维码写入仓库。
- 第二实例在一次启动中出现 NapCat worker 退出码 139，但 launcher 自动拉起后恢复
  online/good；自动化必须以登录探针为准，不能只检查父进程存在。
- ToogleBot transport 已完成 JSON 边界、有界 asyncio queue、echo 路由和重连，并用本地
  NapCat 完成只读 action 往返。
- 本地第二实例已为 `3560612394` 完成扫码登录，HTTP 监听 `127.0.0.1:6544`；两个账号
  均确认加入群 `1070265969`。
- 发送端调用 `send_group_msg` 发送 `.help ping` 后，主账号收到事件并命中帮助插件；
  发送端群历史确认一条来自 `3888217194` 的新插件说明回复，基础群文本阶段 D 已通过。
- 配置化主动探针也完成双账号往返；最近一次发送消息 `538513951`，主账号主动回复
  `1866019684`，日志确认命中 `message_post_process -> ActivePathProbe`，不是普通 worker。
- JSON/Ark 卡片链路已通过：主实例调用 `send_group_ark_share` 生成配置测试群的合法 Ark，
  经项目 `JsonCard -> type=json` 序列化后只发送一次；主端 action 返回 `393834187`，第二
  账号从发送前历史基线确认完整 JSON 等价的新消息 `1683463177`。生成 Ark 的 action 本身
  不算发送成功，验收仍以独立账号历史为准。
- Markdown 已按官方 `type=markdown` / `data.content` 完成内部模型、双向转换和 fixture。
  真实投递尚未通过：4.15.4/42086、4.18.9/42086、4.18.9/48517 三次测试均发生
  `NodeIKernelMsgService/sendMsg`/HTTP timeout，主实例自身历史分别生成消息
  `2099370023`、`798967633`、`83519291`，但独立观察账号未收到。最新一次发送目标已由
  双端只读探针确认是群 `1070265969`，且 PacketBackend 状态正常；三个 message id 都只
  是本地回显。官方兼容表已确认 Markdown 不能直接发送，只支持放在双层合并转发内；
  后续先实现双层 `node` 出站，再由第二账号观察嵌套 Markdown。不能继续直发，也不能把
  主端 action/local history 当作投递成功。
- 实测暴露的空 SQLite schema 和 scheduler `is_trigger()` 已修复。基础 schema 会幂等
  bootstrap；scheduler 的 3 个代码任务及手动 direct/program/single/error/delete、时区和
  生命周期已通过自动测试与 registry smoke。监测任务只访问实际订阅的数据源，空订阅
  不再产生外部请求；地震源已迁到中国地震台网当前官方 JSON 并完成只读 smoke，外部
  监测站点的持续可用性仍按单次运行结果判断。
- Docker 构建和阶段 C 按当前要求延后。
