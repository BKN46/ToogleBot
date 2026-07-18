# 03 NapCat 适配层

`adapter/` 是 OneBot/NapCat 细节进入项目的唯一边界。业务层只应看到
`MessagePack`、`MessageChain` 和管理操作函数。

## 官方文档基线

action 路径、请求字段、响应和数据模型优先参考
[NapCat Apifox 接口文档](https://napcat.apifox.cn/)。该文档随 NapCat 更新自动生成，
本页最后核对日期为 2026-07-17。版本升级或修改 action 时必须重新核对对应页面并用
脱敏 fixture 固化实际 payload。

常用入口：[`get_status`](https://napcat.apifox.cn/226657083e0)、
[`get_login_info`](https://napcat.apifox.cn/226656952e0)、
[`get_group_list`](https://napcat.apifox.cn/226656992e0)、
[`send_group_msg`](https://napcat.apifox.cn/226656598e0)、
[`send_private_msg`](https://napcat.apifox.cn/226656553e0)、
[`OB11MessageMarkdown`](https://napcat.apifox.cn/246111204d0)。Apifox 主要描述 API schema；
WebSocket URL/path、token 和正向/反向模式仍需按实际 NapCat 配置验证。

2026-07-17 首次使用 NapCat Core 4.15.4/NTQQ 3.2.21-42086 完成脱敏实测，同日将
Core 升级到 4.18.9，并将当前本地运行基线更新到 NTQQ 3.2.28-48517。正向 WebSocket
监听 `127.0.0.1:3456`，query `access_token` 鉴权可用，`/`、`/ws`、`/bot/ws` 三种
path 均能执行 `get_status` 并收到匹配 echo 的成功响应；当前版本的
`nc_get_packet_status` 同时返回 `status=ok, retcode=0`。这只能证明当前安装版本兼容
这些 path/action；项目仍应把连接参数配置化，不能据此固化 NapCat 的长期行为。

官方[高级配置](https://napneko.github.io/config/advanced)将 Markdown 列为
PacketBackend 扩展能力，并说明受支持平台的 Native 实现无需外部 packet server。
因此 Markdown 实测前必须同时核对启动日志中的 NativePacketClient Hook 和
`nc_get_packet_status`，不能只以进程在线或消息 schema 正确判定后端可用。

## 文件职责

| 文件 | 职责 | 当前状态 |
| --- | --- | --- |
| `server.py` | 建立 WebSocket、收帧、发帧、连接钩子。 | JSON、echo 路由、ready、任务回收和退避重连已实现；进程级健康检查待补。 |
| `action_router.py` | action future、echo 响应关联、超时和断线失败。 | 已用本地 NapCat 完成只读 action 往返。 |
| `msg_queue.py` | 事件分类、OneBot/内部消息互转、有界收发队列。 | message、recall notice 和 JSON/Ark 卡片已接入；其余 notice/request 仍待实现。 |
| `http_request.py` | 调用 NapCat HTTP action：退群、禁言、文件、撤回、转发和历史。 | 已有分 action timeout、HTTP 状态及 OneBot status/retcode 校验；仍为同步调用，重试/脱敏日志待收敛。 |
| `worker.py` | 插件匹配和执行。 | 已改为显式单 event loop worker；同步插件 I/O 仍会阻塞。 |
| `post_process.py` | 消息历史、主动插件、经济后处理、启动/关闭钩子。 | 已按阶段隔离错误并区分私聊历史；重型 I/O 待迁移。 |
| `schedule.py` | 注册代码型和手动定时任务。 | 已接入 start/stop，真实时间与持久化策略待测。 |
| `ws_test.py` | 手工连接并输出脱敏 frame schema。 | 不再持久化原始消息正文。 |

## 帧的三种类型

NapCat WebSocket 上至少要区分：

1. **事件**：通常含 `post_type`，进入 `push_event()`。
2. **action 响应**：通常含 `status`、`retcode`、`data`、`echo`，交给等待该 echo 的调用方。
3. **生命周期/心跳**：`post_type == "meta_event"`，更新连接状态，不进入插件。

当前 transport 已在事件入队前完成三类分流，并用 UUID echo 关联 action response。
发送消息仍是 fire-and-observe；需要 message id 的调用应改用 `action_router.call_action()`。

## 内部转换矩阵

以下是目标映射，最终字段以捕获的脱敏 NapCat fixture 为准：

| 内部元素 | OneBot 入站 | OneBot 出站 | 注意 |
| --- | --- | --- | --- |
| `Plain` | `type=text`, `data.text` | 同左 | 文本允许空字符串但整条空消息应跳过。 |
| `Markdown` | `type=markdown`, `data.content` | 同左 | 双向转换、JSON 构造和 fixture 已完成；真实投递尚未通过。 |
| `JsonCard` | `type=json`, `data.data` | 同左 | 字符串/对象无损保存；fixture 和独立账号真实投递已通过。 |
| `At` | `type=at`, `data.qq` | `type=at`, `data.qq` | 基础往返已实现。 |
| `AtAll` | `type=at`, `data.qq=all` | 同左 | 基础往返已实现。 |
| `Image` | `type=image`, `data.file/url/...` | `data.file=url/base64://.../path` | 基础字段已修复，真实媒体仍受本机 FFmpeg 限制。 |
| `Quote` | `type=reply`, `data.id` | `type=reply`, `data.id` | 本地 history 补全，未命中时保留占位且不阻塞收帧。 |
| `ForwardMessage` | `type=forward`, `data.id/content` | 通常需 forward nodes action | 入站内联节点可解析；出站暂降级摘要文本。 |
| `Xml` | OneBot 扩展段 | OneBot 扩展段 | 当前出站转换未实现，应明确降级策略。 |

未知消息段不应抛弃整条消息。建议转换成可诊断的占位 `Element`，日志记录段类型但
不记录敏感正文。

2026-07-17 核对 NapCat 文档和本机 converter：Markdown 消息段的字段为字符串
`data.content`，本机 Core 4.15.4/4.18.9 都将其转换成 `ElementType.MARKDOWN`，对应源码
同时标注了 `Need signing`。在 4.15.4/42086、4.18.9/42086、4.18.9/48517 上各实测一次，
`send_group_msg` 均发生 `NodeIKernelMsgService/sendMsg`/HTTP timeout；主实例本地历史
分别生成消息 `2099370023`、`798967633`、`83519291`，但独立观察账号未收到，因此只能
视为本地回显。最新一次 NativePacketClient Hook 和 `nc_get_packet_status` 都正常，已排除
旧 QQ 版本或 PacketBackend 未初始化这一层。官方当前[消息兼容表](https://napneko.github.io/develop/msg)
进一步明确 Markdown 只能在双层合并转发内发送、不能直接发送；后续应实现双层
`node`/forward，不再继续直发或为此修改 Markdown schema。

Markdown smoke 的成功条件必须是：发送前从独立观察账号建立 message id 基线，发送后
该账号看到来自主账号、完整 content 相同、且不在基线中的新 Markdown 段。action 成功
或主账号本地历史出现消息都不是充分条件；action timeout 后只继续观察，不能自动重发。

## 特殊消息类型

2026-07-17 对照 NapCat 4.18.9 的
[`OB11MessageDataType`](https://github.com/NapNeko/NapCatQQ/blob/v4.18.9/packages/napcat-onebot/types/message.ts)
和[转换器](https://github.com/NapNeko/NapCatQQ/blob/v4.18.9/packages/napcat-onebot/api/msg.ts)
确认，特殊内容需要区分普通 segment、Ark/JSON 卡片和独立 action：

| 类别 | NapCat 4.18.9 事实 | 当前项目 | 迁移建议 |
| --- | --- | --- | --- |
| JSON/Ark 卡片 | `type=json`, `data.data`；底层为 `ElementType.ARK`，收发均支持。 | `JsonCard` 已完成双向转换和真实投递。 | 保持载荷无损及日志脱敏；不把 Ark 私有类型暴露给插件。 |
| 链接、位置、音乐卡片 | `share/location/music` 接收时通常统一为 `json`；`music` 发送会调用可配置的外部签名服务再生成 JSON。 | 未建模。 | 先保证 JSON 无损；音乐快捷构造作为可选能力，不能把第三方签名服务放进稳定契约。 |
| 联系人/群推荐 | `contact` 可发送，内部先取得推荐 Ark 再转为 JSON；`send_ark_share` 系列 action 只返回 Ark 内容。 | 未实现。 | action 返回值必须再包装为 JSON segment 发送，不能把“生成卡片”当成“已投递”。 |
| 小程序卡片 | 接收表现为 lightapp/JSON；发送先调用依赖 PacketBackend 的 `get_mini_app_ark`，再发送返回的 Ark JSON。 | 未实现。 | P1：采用生成、发送、独立观察三阶段验收。 |
| QQ/商城表情 | `face/mface/dice/rps`；`mface` 入站也可能是带 emoji 元数据的 `image`。 | 普通图片可读，其余降级。 | P1：独立表情元素，保留 ID、包 ID、key 和结果。 |
| 语音/视频/文件 | `record/video/file` 均支持；在线文件是 `onlinefile`，QQ 闪传是 `flashtransfer`。 | 只有 Image。 | 普通媒体建模；在线文件和闪传使用专用 action，不伪装成普通 File。 |
| 合并转发 | `node` 仅用于发送节点，`forward` 用于上报；node 不能与普通 segment 混发。 | 入站部分解析，出站降级摘要文本。 | P1：先补双层 node，这也是 Markdown 真实投递前置。 |
| 戳一戳 | 接收走 notice，发送走 `send_poke`/group/friend action，不是普通消息段。 | notice 仅记录，未形成业务事件。 | 放在事件/action 层，不新增普通 Message 元素。 |
| XML | 类型 schema 仍存在，但 4.18.9 出站 converter 返回 `undefined`，官方兼容表也未列为可发。 | 保留旧 `Xml`，出站只会降级显示文本。 | 仅兼容旧历史；取得真实 fixture 前不承诺收发。 |
| 内联键盘 | Core 有 keyboard element 和 `click_inline_keyboard_button` action，但公开 OB11 segment union 没有 keyboard。 | 未实现。 | 先采集脱敏入站 fixture，避免凭 Core 私有结构设计稳定类型。 |
| 群签到、AI 语音 | `send_group_sign`、`send_group_ai_record` 是扩展 action。 | 未实现。 | 作为业务 action 封装，不纳入通用消息元素。 |

当前 `nb2toogle()` 对未实现 segment 会保留 `[不支持的消息段:<type>]` 占位，因此不会
无声丢掉整条消息；补新类型时应把真实脱敏 payload 加入 fixture，再替换对应占位。

2026-07-17 JSON/Ark 本地验收：主实例先调用 `send_group_ark_share` 为配置测试群生成
合法 Ark 字符串；该 action 只返回卡片内容，不代表已发送。项目用 `JsonCard` 构造
`type=json` segment 并调用 `send_group_msg` 一次，主端返回消息 `393834187`，独立观察
账号从发送前历史基线后确认完整 JSON 等价的新消息 `1683463177`。这证明通用 JSON
字符串卡片链路可用，不代表音乐签名、小程序 Ark 或任意自造卡片都已通过。

## MessagePack 的群聊与私聊

建议统一约定：

| 字段 | 群聊 | 私聊 |
| --- | --- | --- |
| `message_type` | `group` | `private` |
| `group.id` | 真实群号 | `0` |
| `group.name` | 可用则填写，否则空字符串 | `私聊` |
| `member.id` | 发送者 QQ | 发送者 QQ |
| 回复目标 | `group.id` | `member.id` |

`toogle.adapter.bot_send_message()` 已继承传入 `MessagePack.message_type`；私聊使用
`member.id`，显式好友发送也会把整数目标放入 member。两种场景已有单测。

## 引用消息

目标流程：

1. 在 message segments 找到 reply 段，读取其 `data.id`。
2. 从群或独立私聊 history namespace 按 message id 查找。
3. 构造 `Quote` 并赋给 `MessagePack.quote`，reply 段不重复进入正文。
4. 查询失败时保留 `[引用消息]` 占位；需要远端原文的业务在收帧之后异步补全。

旧 Mirai adapter 会把 quote 单独放进 `MessagePack.quote`，`PluginWrapper` 再根据
`ignore_quote` 决定是否把引用原文拼入命令。迁移要保留这个业务语义。

## 管理操作

`adapter/http_request.py` 当前暴露：

- `quit_group(group_id, is_dismiss=False)`
- `mute_member(group_id, user_id, duration)`
- `upload_group_file(group_id, file_name, file_path)`
- `recall_msg(message_id)`
- `get_forward_msg(message_id)`
- `get_group_msg_history(group_id, message_seq, count=20)`

这些函数有真实副作用。自动测试必须 mock HTTP transport；不得对真实 QQ、群或文件
执行验收。当前退群、群文件字段、bounded timeout、`raise_for_status()` 和 OneBot
`status/retcode` 失败均有单测；统一 client 仍需补重试、脱敏日志和异步 transport。

2026-07-17 重新核对 NapCat Apifox
[上传群文件](https://napcat.apifox.cn/226658753e0)：action 为 `POST /upload_group_file`，
请求字段是 `group_id`、`file`（本地资源路径或 URL）、`name`，成功时返回
`status=ok`、`retcode=0` 和 `data.file_id`。当前本地进程实现使用临时绝对路径，读取超时
放宽到 120 秒，结束后无论成功失败都删除临时文件。该 action 尚未连接真实测试群执行；
付费豆包生成和真实文件上传必须单独显式验收。

## Fixture 测试建议

建立 `tests/fixtures/onebot/`，脱敏保存：

- 群文本、私聊文本。
- @用户、@全体、图片、引用。
- 内联转发和仅有 forward id 的转发。
- group recall、friend recall、poke、成员进退群。
- heartbeat/lifecycle。
- action 成功和失败响应，含 echo。

最小断言：入站 fixture 可解析为稳定内部对象；内部对象再转出时生成合法 action；
未知字段不影响已知字段；失败响应不会被当作消息；断线后任务能停止或重连。

真实登录和后续 Docker 持久化验收统一遵循
[10 NapCat 登录自动化验收](./10-napcat-login-test.md)。两端账号、群和探针文本必须由
本机 `.env`/runner secret 注入，源码和模板不得写死；发送前工具会分别核对 endpoint
登录账号和群。当前迁移阶段只执行本地进程阶段，Docker 验收已明确延后。
