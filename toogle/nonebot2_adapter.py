from typing import Any, Tuple

import nonebot
from nonebot.adapters.mirai2 import MessageChain, MessageSegment
from nonebot.adapters.mirai2.event.base import GroupChatInfo, PrivateChatInfo
from nonebot.adapters.mirai2.event.message import MessageEvent
from nonebot.adapters.mirai2.message import MessageType
# from nonebot.adapters import Event, Message
from nonebot.matcher import Matcher
from nonebot.params import EventMessage, RegexGroup, RegexMatched

from toogle.configs import config
from toogle.exceptions import VisibleException
from toogle.message import At, Element, Group, Image, Member
from toogle.message import MessageChain as ToogleChain
from toogle.message import Plain, Quote
from toogle.message_handler import MessageHandler, MessagePack

warning = nonebot.logger.warning  # type: ignore


class PluginWrapper:
    def __init__(self, plugin: MessageHandler) -> None:
        self.plugin = plugin()

    async def ret(
        self,
        matcher: Matcher,
        event: MessageEvent,
        message: MessageChain = EventMessage(),
    ) -> None:
        if isinstance(event.sender, GroupChatInfo):
            group = Group(event.sender.group.id, event.sender.group.name)
            member = Member(event.sender.id, event.sender.name)
        elif isinstance(event.sender, PrivateChatInfo):
            group = Group(0, "私聊")
            member = Member(event.sender.id, event.sender.nickname)
        else:
            await matcher.send("不支持该种聊天方式！")
            return
        message_pack = MessagePack(nb2toogle(message), group, member)
        if get_block(message_pack):
            return
        try:
            res = await self.plugin.ret(message_pack)
        except VisibleException as e:
            await matcher.send(f"{repr(e)}")
            return
        await matcher.send(toogle2nb(res, message, event))


def get_block(message: MessagePack):
    if str(message.member.id) in config["BLACK_LIST"]:
        return True
    return False


def toogle2nb(
    message: ToogleChain, origin: MessageChain, event: MessageEvent
) -> MessageChain:
    message_list = []
    for item in message.root:
        if isinstance(item, Plain):
            message_list.append(MessageSegment.plain(item.text))
        elif isinstance(item, Quote):
            message_list.append(
                MessageSegment.quote(
                    event.source.id,  # type: ignore
                    event.sender.group.id,
                    event.sender.id,
                    event.sender.group.id,
                    origin,
                )
            )
        elif isinstance(item, Image):
            message_list.append(MessageSegment.image(base64=item.getBase64()))
            # if item.path:
            #     message_list.append(MessageSegment.image(path=item.path))
            # elif item.url:
            #     message_list.append(MessageSegment.image(url=item.url))
        elif isinstance(item, At):
            message_list.append(MessageSegment.at(item.target))

    return MessageChain(message_list)


def nb2toogle(message: MessageChain) -> ToogleChain:
    message_list = []
    for item in message:
        if item.type == MessageType.PLAIN:
            message_list.append(Plain(item.data["text"]))
        elif item.type == MessageType.IMAGE:
            message_list.append(
                Image(
                    id=item.data.get("id"),
                    url=item.data.get("url"),
                    path=item.data.get("path"),
                )
            )
        else:
            message_list.append(Element())
    return ToogleChain(message_list)
