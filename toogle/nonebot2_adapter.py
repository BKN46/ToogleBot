import asyncio
import datetime
import os
import queue
import re
import signal
import threading
import time
import traceback
from multiprocessing import Semaphore
from typing import Any, Optional, Sequence, Tuple, Union

import nonebot
from nonebot.adapters import Event
from nonebot.adapters.mirai2 import MessageChain, MessageSegment
from nonebot.adapters.mirai2.event.base import GroupChatInfo, PrivateChatInfo, GroupInfo, UserPermission
from nonebot.adapters.mirai2.event.message import MessageEvent, MessageSource, GroupMessage, FriendMessage
from nonebot.adapters.mirai2.message import MessageType

# from nonebot.adapters import Event, Message
from nonebot.matcher import Matcher
from nonebot.params import EventMessage, RegexGroup, RegexMatched
import requests
from requests.exceptions import HTTPError as RequestsError
from urllib3.exceptions import HTTPError as UrllibError

from toogle.configs import config, interval_limiter
from toogle.exceptions import VisibleException
from toogle.message import At, AtAll, Element, ForwardMessage, Group, Image, Member
from toogle.message import MessageChain as ToogleChain
from toogle.message import Plain, Quote
from toogle.message_handler import MessageHandler, MessagePack
from toogle.utils import is_admin, is_admin_group, print_err

# THREAD_SEM = Semaphore(1)
warning = nonebot.logger.warning  # type: ignore
if "traffic_control.py" in os.listdir("data"):
    from data.traffic_control import TRAFFIC_CTRL
else:
    TRAFFIC_CTRL = {}
    nonebot.logger.warning("Traffic time control is not available. please check `data/traffic_control.py`")  # type: ignore

WORK_QUEUE:"queue.Queue[Tuple[MessageHandler, MessagePack, bool]]" = queue.Queue()
THREAD_NUM = 10
THREAD_POOL: list[threading.Thread] = []

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
        message_pack = PluginWrapper.get_message_pack(event, message)
        if not message_pack:
            await matcher.send("不支持该种聊天方式！")
            return
        if not message_pack.message.asDisplay():
            nonebot.logger.warning("不处理空消息传入") # type: ignore
            return
        if self.plugin.interval and not interval_limiter.user_interval(
            self.plugin.name, message_pack.member.id, interval=self.plugin.interval
        ) and not is_admin(message_pack.member.id) and not is_admin_group(message_pack.group.id):
            await matcher.send(
                f"[{self.plugin.name}]请求必须间隔[{self.plugin.interval}]秒",
                quote=message_pack.id
            )
            return
        if get_block(message_pack):
            return
        if not is_traffic_free(self.plugin, message_pack) and not is_admin(message_pack.member.id):
            await matcher.send(get_traffic_time(self.plugin, message_pack))
            return
        await plugin_run(self.plugin, message_pack)

    @staticmethod
    def get_message_pack(
        event: MessageEvent,
        message: MessageChain = EventMessage(),
    ) -> MessagePack:
        if isinstance(event.sender, GroupChatInfo):
            group = Group(event.sender.group.id, event.sender.group.name)
            member = Member(event.sender.id, event.sender.name)
        elif isinstance(event.sender, PrivateChatInfo):
            group = Group(0, "私聊")
            member = Member(event.sender.id, event.sender.nickname)
        else:
            return MessagePack(0, nb2toogle(message), Group(0, "Unkown"), Member(0, "Unkown"), None)

        if event.quote:
            quote = Quote(
                event.quote.id,
                event.quote.sender_id,
                event.quote.target_id,
                event.quote.group_id,
                nb2toogle(event.quote.origin),
            )
        else:
            quote = None

        if event.source:
            source_id = event.source.id
        else:
            source_id = 0

        return MessagePack(source_id, nb2toogle(message), group, member, quote)


class LinearHandler:
    def __init__(self, plugins: Sequence[PluginWrapper]) -> None:
        self.plugins = plugins

    async def ret(
        self,
        matcher: Matcher,
        event: MessageEvent,
        message: MessageChain = EventMessage(),
    ) -> None:
        message_pack = PluginWrapper.get_message_pack(event, message)
        if not message_pack:
            await matcher.send("不支持该种聊天方式！")
            return
        for plugin in self.plugins:
            if plugin.plugin.is_trigger(message_pack):
                if not is_traffic_free(plugin.plugin, message_pack):
                    await matcher.send(get_traffic_time(plugin.plugin, message_pack))
                    return
                await plugin_run(plugin.plugin, message_pack)
                return


async def plugin_run(
    plugin: MessageHandler,
    message_pack: MessagePack,
):
    thread_put_job(plugin, message_pack)


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
    message: ToogleChain
) -> MessageChain:
    message_list = []
    for item in message.root:
        if isinstance(item, Plain):
            message_list.append(MessageSegment.plain(item.text))
        elif isinstance(item, Quote):
            message_list.append(
                MessageSegment.quote(
                    item.id,  # type: ignore
                    item.group_id,
                    item.sender_id,
                    item.target_id,
                    toogle2nb(item.message),
                )
            )
        elif isinstance(item, Image):
            message_list.append(MessageSegment.image(base64=item.getBase64()))
        elif isinstance(item, At):
            message_list.append(MessageSegment.at(item.target))
        elif isinstance(item, AtAll):
            message_list.append(MessageSegment.at_all())
        elif isinstance(item, ForwardMessage):
            message_list.append(MessageSegment.plain("消息历史:\n"))
            for node in item.node_list:
                message_list.append(MessageSegment.plain(f"{node['senderId']}:"))
                message_list.append(toogle2nb(node['message']))

    return MessageChain(message_list)


def nb2toogle(message: Union[MessageChain, list, None]) -> ToogleChain:
    message_list = []
    if not message:
        return ToogleChain(message_list)
    if isinstance(message, MessageChain):
        for item in message: # type: ignore
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
            elif item.type == MessageType.AT_ALL:
                message_list.append(AtAll())
            elif item.type == MessageType.FORWARD:
                message_list.append(
                    ForwardMessage(
                        node_list=[
                            {
                                "sender": x.get("senderId"),
                                "time": x.get("time"),
                                "senderName": x.get("senderName"),
                                "message": nb2toogle(x.get("messageChain")),
                            }
                            for x in item.data.get("nodeList") or []
                        ],
                        sender_id=item.data.get("senderLd"),
                        time=item.data.get("time"),
                        message=nb2toogle(item.data.get("message_chain")),
                    )
                )
            else:
                message_list.append(Element())
    else:
        for item in message:
            if item['type'] == "Plain":
                message_list.append(Plain(item.get("text")))
            elif item['type'] == "Image":
                message_list.append(
                    Image(
                        id=item.get("imageId"),
                        url=item.get("url"),
                        path=item.get("path"),
                    )
                )
            elif item['type'] == "Forward":
                message_list.append(
                    ForwardMessage(
                        node_list=[
                            {
                                "sender": x.get("senderId"),
                                "time": x.get("time"),
                                "senderName": x.get("senderName"),
                                "message": nb2toogle(x.get("messageChain")),
                            }
                            for x in item.get("nodeList") or []
                        ],
                        sender_id=item.get("senderLd"),
                        time=item.get("time"),
                        message=nb2toogle(item.get("message_chain")),
                    )
                )
    return ToogleChain(message_list)


async def admin_user_checker(event: Event) -> bool:
    return event.get_user_id() in config.get("ADMIN_LIST", [])


async def bot_send_message(target: Union[int, MessagePack], message: Union[ToogleChain, MessageChain, str], friend=False):
    bot = nonebot.get_bot()

    if isinstance(target, MessagePack):
        if target.group.id:
            target_id = target.group.id
        else:
            target_id = target.member.id
            friend = True
    else:
        target_id = target

    source = MessageSource(id=target_id, time=datetime.datetime.now())
    permission = UserPermission.OWNER
    if friend:
        sender = PrivateChatInfo(
            nickname="None",
            remark="None",
            id=target_id,
        )
        event = FriendMessage(
            self_id=int(bot.self_id),
            type="FriendMessage",
            source=source,
            sender=sender,
            messageChain=MessageChain(""),
        )
    else:
        event = get_event(bot, target_id, 100000, MessageChain(""))
    if isinstance(message, ToogleChain):
        quote = message.get_quote()
        nb_message = toogle2nb(message)
    elif isinstance(message, str):
        quote = None
        nb_message = toogle2nb(ToogleChain.plain(message))
    else:
        quote = None
        nb_message = message
    await bot.send(
        event=event,
        message=nb_message,
        quote = quote,
    )


def get_event(bot, target_id, sender_id, message_chain):
    source = MessageSource(id=target_id, time=datetime.datetime.now())
    group = GroupInfo(
        id=target_id,
        name="",
        permission=UserPermission.OWNER,
    )
    sender = GroupChatInfo(
        id=sender_id,
        memberName="None",
        group=group,
        specialTitle="",
        permission=UserPermission.OWNER,
        joinTimestamp=0,
        lastSpeakTimestamp=0,
        muteTimeRemaining=0,
    )
    event = GroupMessage(
        self_id=int(bot.self_id),
        type="GroupMessage",
        source=source,
        sender=sender,
        messageChain=message_chain,
    )
    return event


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


def thread_put_job(handler: MessageHandler, message_pack: "MessagePack"):
    WORK_QUEUE.put((handler, message_pack, False))


async def thread_worker(index):
    while True:
        try:
            plugin, message_pack, kill = WORK_QUEUE.get(timeout=30)
            if kill:
                break
        except queue.Empty:
            continue

        try:
            start_time = time.time()
            res = await plugin.ret(message_pack)
            if not res:
                continue
            if plugin.interval and not res.no_interval:
                interval_limiter.force_user_interval(plugin.name, message_pack.member.id, interval=plugin.interval)
            if len(res.root) > 0:
                await bot_send_message(message_pack, res)
            use_time = int((time.time() - start_time) * 1000)
            nonebot.logger.success(f"{plugin.name} in worker {index} running complete. ({use_time}ms)") # type: ignore
        except (
            UrllibError,
            RequestsError,
            requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout,
            requests.exceptions.ConnectTimeout,
            requests.exceptions.HTTPError
        ):
            await bot_send_message(message_pack, f"爬虫网络连接错误，请稍后尝试")
        except VisibleException as e:
            await bot_send_message(message_pack, f"{e.__str__()}")
        except Exception as e:
            if '误触发' not in repr(e):
                print_err(e, plugin, message_pack)

def worker_start(thread_num=THREAD_NUM):
    THREAD_POOL.clear()
    for i in range(thread_num):
        THREAD_POOL.append(threading.Thread(target=asyncio.run, args=[thread_worker(i)]))
    for x in THREAD_POOL:
        x.start()

async def worker_shutdown(thread_num=THREAD_NUM):
    for i in range(thread_num * 2):
        WORK_QUEUE.put((None, None, True)) # type: ignore
    for x in THREAD_POOL:
        x.join()
    nonebot.logger.success("All worker thread shutdown.") # type: ignore
    # for i in config.get("ADMIN_LIST", []):
    #     await bot_send_message(int(i), "Toogle threads all shutdown.", friend=True)

worker_start()
