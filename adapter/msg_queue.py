import asyncio
import time
import uuid
from collections.abc import Sequence
from typing import Any

import configs
import toogle.message as message
from toogle import adapter
from toogle.logger import logger
from toogle.message import (
    At,
    AtAll,
    ForwardMessage,
    Group,
    Image,
    Member,
    MessageChain,
    Plain,
    Quote,
)
from toogle.message_handler import MESSAGE_HISTORY, RECALL_HISTORY, MessagePack


def _queue_size(key: str, default: int) -> int:
    try:
        return max(1, int(configs.config.get(key, default)))
    except (TypeError, ValueError):
        return default


recv_queue: asyncio.Queue[MessagePack] = asyncio.Queue(
    maxsize=_queue_size("RECV_QUEUE_SIZE", 1000)
)
send_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
    maxsize=_queue_size("SEND_QUEUE_SIZE", 1000)
)
_transport_loop: asyncio.AbstractEventLoop | None = None


def reset_queues() -> None:
    global recv_queue, send_queue
    if _transport_loop is not None:
        raise RuntimeError("cannot reset queues while NapCat transport is bound")
    recv_queue = asyncio.Queue(maxsize=_queue_size("RECV_QUEUE_SIZE", 1000))
    send_queue = asyncio.Queue(maxsize=_queue_size("SEND_QUEUE_SIZE", 1000))


def bind_transport_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _transport_loop
    _transport_loop = loop


def unbind_transport_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _transport_loop
    if _transport_loop is loop:
        _transport_loop = None


def _put_outbound(action: dict[str, Any]) -> None:
    try:
        send_queue.put_nowait(action)
    except asyncio.QueueFull:
        logger.error("NapCat outbound queue is full; action=%s", action.get("action"))


def enqueue_outbound(action: dict[str, Any]) -> bool:
    loop = _transport_loop
    if loop is None or loop.is_closed():
        logger.error("NapCat transport is not ready; action=%s", action.get("action"))
        return False

    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    if running_loop is loop:
        _put_outbound(action)
    else:
        loop.call_soon_threadsafe(_put_outbound, action)
    return True


def make_action(action: str, params: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": action,
        "params": params,
        "echo": uuid.uuid4().hex,
    }


def push_event(raw_event: dict[str, Any]) -> str:
    post_type = raw_event.get("post_type")
    if post_type == "message":
        user_id = raw_event.get("user_id")
        self_id = raw_event.get("self_id")
        if user_id is not None and self_id is not None and str(user_id) == str(self_id):
            return "self_message"
        message_pack = parse_event(raw_event)
        try:
            recv_queue.put_nowait(message_pack)
        except asyncio.QueueFull:
            logger.error(
                "NapCat inbound queue is full; message_type=%s",
                raw_event.get("message_type"),
            )
            return "dropped"
        return "message"
    if post_type == "notice":
        handle_notice(raw_event)
        return "notice"
    if post_type == "meta_event":
        return "meta_event"
    if post_type == "request":
        logger.info("NapCat request event is not implemented: %s", raw_event.get("request_type"))
        return "request"
    logger.debug("Ignored NapCat frame without supported post_type")
    return "unknown"


def handle_notice(event: dict[str, Any]) -> None:
    notice_type = event.get("notice_type")
    if notice_type not in {"group_recall", "friend_recall"}:
        logger.debug("NapCat notice is not implemented: %s", notice_type)
        return

    group_id = _as_int(event.get("group_id"), 0)
    history_key: int | str = (
        group_id
        if notice_type == "group_recall"
        else f"private_{_as_int(event.get('user_id'), 0)}"
    )
    message_id = _as_int(event.get("message_id"), 0)
    recalled = MESSAGE_HISTORY.search(group_id=history_key, msg_id=message_id)
    if recalled:
        RECALL_HISTORY.add(history_key, recalled)


def send_message(message_pack: MessagePack) -> bool:
    if message_pack.message_type == "group":
        action = make_action(
            "send_group_msg",
            {
                "group_id": message_pack.group.id,
                "message": toogle2nb(message_pack.message),
            },
        )
    elif message_pack.message_type == "private":
        action = make_action(
            "send_private_msg",
            {
                "user_id": message_pack.member.id,
                "message": toogle2nb(message_pack.message),
            },
        )
    else:
        logger.error("Unsupported outbound message_type=%r", message_pack.message_type)
        return False
    return enqueue_outbound(action)


adapter.BOT_SEND = send_message


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_sender_name(sender: dict[str, Any]) -> str:
    return str(sender.get("card") or sender.get("nickname") or "")


def _parse_quote(event: dict[str, Any]) -> Quote | None:
    chain = event.get("message")
    if not isinstance(chain, Sequence) or isinstance(chain, (str, bytes)):
        return None
    reply = next(
        (
            item
            for item in chain
            if isinstance(item, dict) and item.get("type") == "reply"
        ),
        None,
    )
    if not reply:
        return None

    reply_id = _as_int((reply.get("data") or {}).get("id"), 0)
    if not reply_id:
        return None
    group_id = _as_int(event.get("group_id"), 0)
    history_key: int | str = (
        group_id
        if event.get("message_type") == "group"
        else f"private_{_as_int(event.get('user_id'), 0)}"
    )
    original = MESSAGE_HISTORY.search(group_id=history_key, msg_id=reply_id)
    if original:
        sender_id = original.member.id
        origin = original.message
    else:
        sender_id = 0
        origin = MessageChain.plain("[引用消息]")
    return Quote(
        id=reply_id,
        sender_id=sender_id,
        target_id=_as_int(event.get("user_id"), 0),
        group_id=group_id,
        message=origin,
    )


def parse_event(event: dict[str, Any]) -> MessagePack:
    if not isinstance(event, dict):
        raise TypeError("OneBot event must be an object")
    message_type = event.get("message_type")
    if message_type not in {"group", "private"}:
        raise ValueError(f"unsupported message_type: {message_type!r}")

    sender = event.get("sender")
    if not isinstance(sender, dict):
        sender = {}
    group_id = _as_int(event.get("group_id"), 0) if message_type == "group" else 0
    group_name = (
        str(event.get("group_name") or sender.get("group_name") or "")
        if message_type == "group"
        else "私聊"
    )
    user_id = _as_int(sender.get("user_id") or event.get("user_id"), 0)
    pack = MessagePack(
        id=_as_int(event.get("message_id"), 0),
        message=nb2toogle(event.get("message"), parse_forward=True),
        group=Group(id=group_id, name=group_name),
        member=Member(id=user_id, name=get_sender_name(sender)),
        quote=_parse_quote(event),
        message_type=message_type,
    )
    try:
        pack.time = float(event.get("time", time.time()))
    except (TypeError, ValueError):
        pass
    return pack


def _forward_nodes(data: dict[str, Any]) -> list[dict[str, Any]]:
    content = data.get("content")
    if not isinstance(content, list):
        return []
    nodes = []
    for node in content:
        if not isinstance(node, dict):
            continue
        sender = node.get("sender") if isinstance(node.get("sender"), dict) else {}
        node_message = node.get("message") or node.get("content") or []
        nodes.append(
            {
                "sender": _as_int(sender.get("user_id") or node.get("user_id"), 0),
                "time": _as_int(node.get("time"), 0),
                "senderName": get_sender_name(sender) or str(node.get("nickname") or ""),
                "message": nb2toogle(node_message, parse_forward=True),
            }
        )
    return nodes


def nb2toogle(raw_message: Any, parse_forward: bool = False) -> MessageChain:
    if isinstance(raw_message, str):
        return MessageChain.plain(raw_message)
    if not isinstance(raw_message, list):
        return MessageChain([])

    message_list: list[message.Element] = []
    for item in raw_message:
        if not isinstance(item, dict):
            message_list.append(Plain("[不支持的消息段]"))
            continue
        segment_type = item.get("type")
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        if segment_type == "text":
            message_list.append(Plain(str(data.get("text") or "")))
        elif segment_type == "at":
            target = data.get("qq")
            if str(target) == "all":
                message_list.append(AtAll())
            else:
                message_list.append(At(target=_as_int(target, 0)))
        elif segment_type == "image":
            message_list.append(
                Image(
                    id=data.get("file"),
                    url=data.get("url"),
                    path=data.get("path"),
                )
            )
        elif segment_type == "reply":
            continue
        elif segment_type == "forward":
            if not parse_forward:
                message_list.append(Plain("[转发消息]"))
                continue
            nodes = _forward_nodes(data)
            message_list.append(
                ForwardMessage(
                    node_list=nodes,
                    sender_id=None,
                    sender_name=None,
                    time=None,
                    message_id=data.get("id"),
                    message=MessageChain.plain("[转发消息]"),
                )
            )
        else:
            message_list.append(Plain(f"[不支持的消息段:{segment_type or 'unknown'}]"))
    return MessageChain(message_list)


def toogle2nb(chain: MessageChain) -> list[dict[str, Any]]:
    message_list: list[dict[str, Any]] = []
    for item in chain.root:
        if isinstance(item, Plain):
            message_list.append({"type": "text", "data": {"text": item.text}})
        elif isinstance(item, Quote):
            message_list.append({"type": "reply", "data": {"id": item.id}})
        elif isinstance(item, Image):
            if item.id and item.cache:
                file_value = item.id
            elif item.url:
                file_value = item.url
            elif item.path:
                file_value = item.path
            else:
                file_value = f"base64://{item.getBase64()}"
            message_list.append({"type": "image", "data": {"file": file_value}})
        elif isinstance(item, At):
            message_list.append({"type": "at", "data": {"qq": item.target}})
        elif isinstance(item, AtAll):
            message_list.append({"type": "at", "data": {"qq": "all"}})
        elif isinstance(item, ForwardMessage):
            message_list.append(
                {"type": "text", "data": {"text": item.message.asDisplay()}}
            )
        else:
            message_list.append(
                {"type": "text", "data": {"text": item.asDisplay()}}
            )
    return message_list
