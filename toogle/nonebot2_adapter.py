import os
import re
import signal
import time
import traceback
from typing import Any, Optional, Sequence, Tuple

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
if "traffic_control.py" in os.listdir('data'):
    from data.traffic_control import TRAFFIC_CTRL
else:
    TRAFFIC_CTRL = {}
    nonebot.logger.warning("Traffic time control is not available. please check `data/traffic_control.py`") # type: ignore

class PluginWrapper:
    def __init__(self, plugin: MessageHandler) -> None:
        self.plugin_class = plugin
        self.plugin = plugin()

    async def ret(
        self,
        matcher: Matcher,
        event: MessageEvent,
        message: MessageChain = EventMessage(),
    ) -> None:
        message_pack = PluginWrapper.get_message_pack(matcher, event, message)
        if not message_pack:
            await matcher.send("不支持该种聊天方式！")
            return
        if get_block(message_pack):
            return
        if not is_traffic_free(self.plugin, message_pack):
            await matcher.send(get_traffic_time(self.plugin, message_pack))
            return
        await plugin_run(self.plugin, message_pack, matcher, event, message)

    @staticmethod
    def get_message_pack(
        matcher: Matcher,
        event: MessageEvent,
        message: MessageChain = EventMessage(),
    ) -> Optional[MessagePack]:
        if isinstance(event.sender, GroupChatInfo):
            group = Group(event.sender.group.id, event.sender.group.name)
            member = Member(event.sender.id, event.sender.name)
        elif isinstance(event.sender, PrivateChatInfo):
            group = Group(0, "私聊")
            member = Member(event.sender.id, event.sender.nickname)
        else:
            return None
        return MessagePack(nb2toogle(message), group, member)

class LinearHandler:
    def __init__(self, plugins: Sequence[PluginWrapper]) -> None:
        self.plugins = plugins

    async def ret(
        self,
        matcher: Matcher,
        event: MessageEvent,
        message: MessageChain = EventMessage()
    ) -> None:
        message_pack = PluginWrapper.get_message_pack(matcher, event, message)
        if not message_pack:
            await matcher.send("不支持该种聊天方式！")
            return
        for plugin in self.plugins:
            if plugin.plugin.is_trigger(message_pack):
                if not is_traffic_free(plugin.plugin, message_pack):
                    await matcher.send(get_traffic_time(plugin.plugin, message_pack))
                    return
                await plugin_run(plugin.plugin, message_pack, matcher, event, message)
                return

async def plugin_run(
    plugin: MessageHandler,
    message_pack: MessagePack,
    matcher: Matcher,
    event: MessageEvent,
    message: MessageChain
):
    def handle_timeout(signum, frame):
        raise VisibleException(f"[To {message_pack.member.id}] {plugin.name}运行超时，请稍后重试")

    try:
        signal.signal(signal.SIGALRM, handle_timeout)
        signal.alarm(60)
        res = await plugin.ret(message_pack)
        await matcher.send(toogle2nb(res, message, event))
        signal.alarm(0)
    except VisibleException as e:
        await matcher.send(f"{repr(e)}")
        return
    except Exception as e:
        print(traceback.format_exc(), file=open("err.log", "a"))
        nonebot.logger.error(f"[{plugin.name}] {repr(e)}") # type: ignore


def get_block(message: MessagePack):
    if str(message.member.id) in config["BLACK_LIST"]:
        return True
    return False


def get_traffic_time(plugin: MessageHandler, message: MessagePack) -> str:
    tz = TRAFFIC_CTRL.get(plugin.name).get(str(message.group.id)) # type: ignore
    tz = ", ".join([f"{x[0]}:00 - {x[1]}:00" for x in tz]) # type: ignore
    return f'管理员设置，该功能在 {tz} 时段禁用'


def is_traffic_free(plugin: MessageHandler, message: MessagePack) -> bool:
    nonebot.logger.success(f"Triggered [{plugin.name}]") # type: ignore
    plugin_traffic = TRAFFIC_CTRL.get(plugin.name)
    group_id = str(message.group.id)
    if plugin_traffic and group_id in plugin_traffic.keys():
        now_hr = time.localtime().tm_hour
        for traffic_time in plugin_traffic[group_id]:
            if now_hr >= traffic_time[0] and now_hr < traffic_time[1]:
                return False
    return True


def toogle2nb(
    message: ToogleChain, origin: MessageChain, event: MessageEvent
) -> MessageChain:
    message_list = []
    for item in message.root:
        if isinstance(item, Plain):
            message_list.append(MessageSegment.plain(item.text))
        elif isinstance(item, Quote):
            pass
            # message_list.append(
            #     MessageSegment.quote(
            #         event.source.id,  # type: ignore
            #         event.sender.group.id,
            #         event.sender.id,
            #         event.sender.group.id,
            #         origin,
            #     )
            # )
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
