import datetime
import os
import re
import signal
import time
import traceback
from multiprocessing import Semaphore
from typing import Any, Optional, Sequence, Tuple, Union

import nonebot
from nonebot.adapters import Event
from nonebot.adapters.mirai2 import MessageChain, MessageSegment
from nonebot.adapters.mirai2.event.base import GroupChatInfo, PrivateChatInfo, GroupInfo, UserPermission
from nonebot.adapters.mirai2.event.message import MessageEvent, MessageSource, GroupMessage
from nonebot.adapters.mirai2.message import MessageType

# from nonebot.adapters import Event, Message
from nonebot.matcher import Matcher
from nonebot.params import EventMessage, RegexGroup, RegexMatched
from requests.exceptions import HTTPError as RequestsError
from urllib3.exceptions import HTTPError as UrllibError

from toogle.configs import config, interval_limiter
from toogle.exceptions import VisibleException
from toogle.message import At, Element, Group, Image, Member
from toogle.message import MessageChain as ToogleChain
from toogle.message import Plain, Quote
from toogle.message_handler import MessageHandler, MessagePack
from toogle.utils import is_admin

THREAD_SEM = Semaphore(1)
warning = nonebot.logger.warning  # type: ignore
if "traffic_control.py" in os.listdir("data"):
    from data.traffic_control import TRAFFIC_CTRL
else:
    TRAFFIC_CTRL = {}
    nonebot.logger.warning("Traffic time control is not available. please check `data/traffic_control.py`")  # type: ignore


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
        if self.plugin.interval and not interval_limiter.user_interval(
            self.plugin.name, message_pack.member.id, interval=self.plugin.interval
        ) and not is_admin(message_pack.member.id):
            await matcher.send(f"[{self.plugin.name}]请求必须间隔[{self.plugin.interval}]秒")
            return
        if get_block(message_pack):
            return
        if not is_traffic_free(self.plugin, message_pack) and not is_admin(message_pack.member.id):
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
        message: MessageChain = EventMessage(),
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
    message: MessageChain,
):
    def handle_timeout(signum, frame):
        raise VisibleException(f"[To {message_pack.member.id}] {plugin.name}运行超时，请稍后重试")

    if plugin.thread_limit and not THREAD_SEM.acquire(timeout=1):
        toogle_message = ToogleChain.create(
            [At(target=message_pack.member.id), Plain(f"我知道你很急，但你别急")]
        )
        res = toogle2nb(toogle_message, message, event)
        await matcher.send(res)
        return

    try:
        signal.signal(signal.SIGALRM, handle_timeout)
        signal.alarm(60)
        res = await plugin.ret(message_pack)
        await matcher.send(toogle2nb(res, message, event))
        signal.alarm(0)
    except (UrllibError, RequestsError):
        # await matcher.send(f"爬虫网络连接错误，请稍后尝试")
        return
    except VisibleException as e:
        await matcher.send(f"{e.__str__()}")
    except Exception as e:
        if '误触发' not in repr(e):
            print(
                f"{'*'*20}\n[{datetime.datetime.now().strftime('%Y-%m-%d, %H:%M:%S')}]"
                f"[{plugin.name}] {repr(e)}\n"
                f"[{message_pack.group.id}][{message_pack.member.id}]{message_pack.message.asDisplay()}\n"
                f"\n{'*'*20}\n{traceback.format_exc()}",
                file=open("err.log", "a"),
            )
            nonebot.logger.error(f"[{plugin.name}] {repr(e)}")  # type: ignore
    finally:
        if plugin.thread_limit:
            THREAD_SEM.release()


def get_block(message: MessagePack):
    if str(message.member.id) in config["BLACK_LIST"]:
        return True
    return False


def get_traffic_time(plugin: MessageHandler, message: MessagePack) -> str:
    tz = TRAFFIC_CTRL.get(plugin.name).get(str(message.group.id))  # type: ignore
    tz = ", ".join([f"{x[0]}:00 - {x[1]}:00" for x in tz])  # type: ignore
    return f"管理员设置，该功能在 {tz} 时段禁用"


def is_traffic_free(plugin: MessageHandler, message: MessagePack) -> bool:
    nonebot.logger.success(f"Triggered [{plugin.name}]")  # type: ignore
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
                    id=item.data.get("imageId"),
                    url=item.data.get("url"),
                    path=item.data.get("path"),
                )
            )
        elif item.type == MessageType.AT:
            message_list.append(
                At(
                    target=item.data.get("target"),  # type: ignore
                )
            )
        else:
            message_list.append(Element())
    return ToogleChain(message_list)


async def admin_user_checker(event: Event) -> bool:
    return event.get_user_id() in config.get("ADMIN_LIST", [])


async def bot_send_group(target_id: int, message: Union[ToogleChain, MessageChain]):
    bot = nonebot.get_bot()
    source = MessageSource(id=target_id, time=datetime.datetime.now())
    permission = UserPermission.OWNER
    group = GroupInfo(
        id=target_id,
        name="",
        permission=permission,
    )
    sender = GroupChatInfo(
        id=100000,
        memberName="None",
        group=group,
        specialTitle="",
        permission=permission,
        joinTimestamp=0,
        lastSpeakTimestamp=0,
        muteTimeRemaining=0,
    )
    event = GroupMessage(
        self_id=int(bot.self_id),
        type="GroupMessage",
        source=source,
        sender=sender,
        messageChain=MessageChain(""),
    )
    if isinstance(message, ToogleChain):
        nb_message = toogle2nb(message, MessageChain(""), event)
    else:
        nb_message = message
    await bot.send(
        event=event,
        message=nb_message,
    )
    # await bot.send_group_message(
    #     group=target_id,
    #     message_chain=nb_message,
    # )


async def bot_get_all_group():
    bot = nonebot.get_bot()
    try:
        res = await bot.call_api(api="groupList", sessionKey=config.get("VERIFY_KEY", ""))
    except Exception as e:
        nonebot.logger.error(repr(e)) # type: ignore
        return []
    return res


async def bot_exec(api, **data):
    bot = nonebot.get_bot()
    res = await bot.call_api(api=api, sessionKey=config.get("VERIFY_KEY", ""), **data)
    return res
