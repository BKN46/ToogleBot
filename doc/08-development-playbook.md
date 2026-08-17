# 08 开发与验证手册

## 每次任务的起点

```bash
git status --short --branch
```

当前迁移通常以未提交工作树存在。不要回退或覆盖不属于本任务的修改，也不要因旧文件
显示为删除，就从归档分支恢复 Mirai 代码。

按任务阅读：

- 普通插件：04、05、目标文件。
- 消息或事件：02、03、04、`TODO.md`。
- 配置/数据/部署：06、根配置和部署文件。
- 调度/API/框架共享逻辑：07、09。

当前迁移阶段真实 NapCat 验收只启动本地 QQ/NapCat 进程。不要运行 Docker build、
compose start/restart 或容器登录；这些步骤等代码迁移完成后再启用。

本地调试启动统一使用仓库根目录的 `./run.sh`。脚本会切换到项目根、选择 Python、检查
`.env`、探测 NapCat WS 并加进程锁；`Ctrl-C` 直接传给 `bot.py`。修改启动脚本后至少执行：

```bash
bash -n run.sh
RUN_DRY_RUN=1 ./run.sh
```

`RUN_SKIP_NAPCAT_CHECK=1` 只用于明确需要离线调试连接重试的场景。

### 本地 systemd 守护

生产或长期运行的本地 QQ/NapCat 使用仓库内的两个 unit，不直接依赖交互式 shell：

```bash
sudo tools/install_systemd_services.sh
sudo systemctl start tooglebot-napcat.service
sudo systemctl status tooglebot-napcat.service
sudo systemctl start tooglebot.service
```

`tooglebot-napcat.service` 调用 `tools/start_napcat_main.sh`，从 `.env` 读取主账号和
NapCat HTTP/WS token，在独立 workdir 生成配置并使用 `xvfb-run` 启动 QQ。首次登录必须
扫描 `NAPCAT_MAIN_WORKDIR/cache/qrcode.png`；先用 `tools/napcat_login_check.py` 确认 online/good 和账号一致，
再启动 ToogleBot。停止或重启使用 `systemctl stop|restart`，unit 会回收整个 QQ 子进程组。
机器人 unit 依赖 NapCat，但 NapCat 首次扫码未完成时会按 systemd 重试，不应据此判断登录
成功。

## 当前可执行检查

项目是从仓库根直接运行的非打包应用，`[tool.uv] package = false` 阻止 uv/Hatchling
误把它构建为不存在的 `tooglebot` 包。统一使用锁定环境：

```bash
uv sync --frozen
uv run python -m compileall -q bot.py configs.py adapter api toogle plugins tools statistics
uv run python -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'
```

上述命令只验证 Git 可见的公开基线。存在本机 `private/` 扩展时，其测试需在本机另行执行
`uv run python -W error::ResourceWarning -m unittest discover -s private/tests -p 'test_*.py'`；
私有目录及兼容入口不进入 Git 或普通 CI，也不计入公开 registry 数量。

当前依赖清单还显式包含图片 NSFW 检测所需的 TensorFlow，以及 `python-a2s`、
`libtorrent`、`lupa`、MySQL connector、`wordcloud` 和 `tqdm` 等可选/离线功能库。
TensorFlow 2.21 与 `h5py` 3.14 系列绑定；修改任一版本约束后必须重新运行
`uv lock` 和 `uv sync --frozen`。

本机旧 `venv/bin/python` 只作为迁移期应急解释器，不能替代 clean `uv sync` 验收。

源码 import 有线程、文件和插件加载副作用。没有隔离环境时，不运行 `import bot` 作为
普通 lint；必须运行时加 timeout，并说明可能访问本地数据或外部服务。

## 新增普通插件

1. 在 `plugins/` 选择现有业务域；大型独立域新增顶层文件。
2. 继承 `MessageHandler`，定义 `name`、`trigger`、`readme`。
3. 设置 `interval`、`price`、`admin_only`、`ignore_quote`。
4. 将解析与网络请求/渲染分开，纯函数放对应辅助目录。
5. 返回 `MessageChain` 或 `None`；错误返回明确是否扣费/冷却。
6. 添加正则、成功、参数错误、权限/余额边界测试。
7. 确认文件会被顶层扫描，且没有 import 时网络请求。

不要在插件里 import `adapter.msg_queue`、`websockets` 或 NapCat payload。主动消息统一
调用 `toogle.adapter.bot_send_message()`。

## 修改 OneBot 接入

推荐顺序：

1. 在 `tests/fixtures/onebot/` 加一份脱敏原始事件或响应。
2. 先写入站解析或出站 action 的纯函数测试。
3. 再修改 `adapter/msg_queue.py`。
4. transport 生命周期只在 `adapter/server.py` 修改。
5. 管理 action 只在可 mock 的 client 层修改。
6. 运行 fixture 测试，再按 10 使用配置的专用账号做隔离 NapCat 冒烟。

不得使用真实生产群测试禁言、撤回、退群、文件上传或群发。

## 修改外部 API/爬虫

- 为 requests 设置连接和读取 timeout。
- 网络获取与 HTML/JSON 解析拆开。
- 保存不含 Cookie/token/用户信息的响应 fixture。
- 空字段、站点错误页、限流和 schema 变化应有可见失败。
- 外部失败通常不扣费；不要把完整响应或密钥发给管理员。
- 同步请求不能放在 WebSocket 主 loop，必要时 `asyncio.to_thread()` 或异步 client。

## 修改数据结构

- 找到所有读写者：`rg -n '<file-or-table>' . -g '*.py'`。
- 区分仓库静态资源、可重建缓存和不可丢运行状态。
- JSON 变更提供默认值和旧字段兼容。
- SQLite 使用参数化 SQL和 migration，不直接编辑真实数据库。
- pickle 结构变更要提供回退/备份策略。
- 不提交 `.env`、`data/`、数据库 WAL、Cookie、日志或抓取的私人内容。

## 修改调度

代码型任务放 `plugins/schedule.py`，共享注册和手动任务逻辑放
`toogle/scheduler.py`。至少覆盖：

- cron 字段正确，scheduler 已 start。
- `ret(None)` 自动触发和 `ret(message_pack)` 手动触发。
- `program=true` 的虚拟 MessagePack 类型正确。
- 单次任务执行后只删除自身。
- 同一任务重复加载不会重复注册。
- 删除任务校验创建者/管理员和列表索引。

时间测试使用固定时钟或直接调用 job，不等待真实时间。

## 验证层级

### L0 静态

- `python -m compileall ...`
- `git diff --check`
- `rg` 检查旧依赖和路径。
- Markdown 相对链接存在。

### L1 单元

- OneBot fixture 转换。
- 消息链构造、正则和 PluginWrapper 策略。
- 纯解析、渲染、小型数据迁移。
- HTTP transport mock。

### L2 进程集成

- clean `uv sync --frozen`。
- mock WebSocket server 验证收帧、action、echo、断线重连和关闭。
- registry 连续 load/reload、核心失败保留旧快照、帮助 provider 和 scheduler 幂等。
- 临时目录 + 临时 SQLite，验证 bootstrap 和持久化。

### L3 隔离 NapCat 冒烟

- 在本机 `.env`/runner secret 配置主账号、发送账号、测试群和 active probe nonce；代码、
  Shell 和 JSON 模板不得写死真实值。
- 使用 `tools/start_napcat_sender.sh` 启动配置发送实例，使用
  `tools/napcat_dual_account_check.py --scenario active` 先只读探测，再显式确认发送。
- 当前先对本地 NapCat 进程执行登录、HTTP/WS action 和无扫码重启验证。
- 文本、图片、@、引用、私聊、转发、撤回事件。
- Markdown 使用 `tools.napcat_markdown_check` 先只读校验；显式发送前启动第二 NapCat
  实例，并且只以第二账号观察到的新 Markdown 段作为送达证据。
- 定时消息、启动/重连通知、API 主动发送。
- Docker 重启、登录数据和 data volume 持久化在代码迁移完成后执行。

首次扫码和自动重启/重建登录的完整流程见
[10 NapCat 登录自动化验收](./10-napcat-login-test.md)。生产 QQ 不得参与自动化测试。

最终报告必须说清执行到哪一级，以及没有执行更高级别验证的原因。

## 常见误区

- 语法通过不代表插件 import 成功；动态 loader 会捕获并跳过失败插件。
- 进程存在不代表健康；WebSocket 收发 loop 可能已经退出。
- `data/` 在本机存在不代表 Docker/新环境存在。
- Mirai 序列化、旧日志读取器、旧 SQL scheduler 和 scheduler 注释代码已经删除；新代码
  出现这些命名应视为迁移回归，而不是兼容层。
