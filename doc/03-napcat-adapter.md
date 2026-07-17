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
[`send_private_msg`](https://napcat.apifox.cn/226656553e0)。Apifox 主要描述 API schema；
WebSocket URL/path、token 和正向/反向模式仍需按实际 NapCat 配置验证。

2026-07-17 对本地主机 NapCat Core 4.15.4 的脱敏实测确认：正向 WebSocket 监听
`127.0.0.1:3456`，query `access_token` 鉴权可用，`/`、`/ws`、`/bot/ws` 三种 path
均能执行 `get_status` 并收到匹配 echo 的成功响应。这只能证明当前安装版本兼容这些
path；项目仍应把 URL/path 配置化，不能据此固化 NapCat 的长期行为。

## 文件职责

| 文件 | 职责 | 当前状态 |
| --- | --- | --- |
| `server.py` | 建立 WebSocket、收帧、发帧、连接钩子。 | JSON、echo 路由、ready、任务回收和退避重连已实现；进程级健康检查待补。 |
| `action_router.py` | action future、echo 响应关联、超时和断线失败。 | 已用本地 NapCat 完成只读 action 往返。 |
| `msg_queue.py` | 事件分类、OneBot/内部消息互转、有界收发队列。 | message 和 recall notice 已接入；其余 notice/request 仍待实现。 |
| `http_request.py` | 调用 NapCat HTTP action：退群、禁言、文件、撤回、转发和历史。 | 已有连接/读取 timeout 和 HTTP 状态校验；仍为同步调用，OneBot retcode/统一错误待收敛。 |
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
| `At` | `type=at`, `data.qq` | `type=at`, `data.qq` | 基础往返已实现。 |
| `AtAll` | `type=at`, `data.qq=all` | 同左 | 基础往返已实现。 |
| `Image` | `type=image`, `data.file/url/...` | `data.file=url/base64://.../path` | 基础字段已修复，真实媒体仍受本机 FFmpeg 限制。 |
| `Quote` | `type=reply`, `data.id` | `type=reply`, `data.id` | 本地 history 补全，未命中时保留占位且不阻塞收帧。 |
| `ForwardMessage` | `type=forward`, `data.id/content` | 通常需 forward nodes action | 入站内联节点可解析；出站暂降级摘要文本。 |
| `Xml` | OneBot 扩展段 | OneBot 扩展段 | 当前出站转换未实现，应明确降级策略。 |

未知消息段不应抛弃整条消息。建议转换成可诊断的占位 `Element`，日志记录段类型但
不记录敏感正文。

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
执行验收。当前退群参数、bounded timeout 和 `raise_for_status()` 已有单测；统一 client
仍需补 OneBot retcode 校验、脱敏日志、异步/可替换 transport。

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
