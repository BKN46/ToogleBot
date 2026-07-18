import copy
import datetime
import os
import re
import time
from typing import Any, Callable, Optional, Union

from configs import config
from toogle.message import Group, Member
from toogle.message import MessageChain as ToogleChain
from toogle.message_handler import MessageHandler, MessagePack
from toogle.utils import (
    interval_limiter,
    is_admin,
    is_admin_group,
    print_call,
    print_err,
)
from toogle.economy import get_balance, take_balance
from toogle.logger import logger

if "traffic_control.py" in os.listdir("data"):
    from data.traffic_control import TRAFFIC_CTRL # type: ignore
else:
    TRAFFIC_CTRL = {}
    logger.warning("Traffic time control is not available. please check `data/traffic_control.py`")  # type: ignore

BOT_SEND: Optional[Callable] = None
GROUP_FILE_UPLOAD: Optional[Callable[[int, str, str], Any]] = None

class PluginWrapper:
    def __init__(self, plugin: MessageHandler) -> None:
        self.plugin_class = plugin
        self.plugin: MessageHandler = plugin()

    async def ret(
        self,
        message_pack: MessagePack
    ) -> bool:
        return await self.prepare(message_pack) is not None

    async def prepare(self, message_pack: MessagePack) -> Optional[MessagePack]:
        if not message_pack.message.asDisplay():
            logger.warning("不处理空消息传入") # type: ignore
            return None
        if not re.search(self.plugin.trigger, message_pack.message.asDisplay().strip()):
            logger.warning(f"错误正则匹配: [{self.plugin.trigger}] {message_pack.message.asDisplay()}") # type: ignore
            return None

        member_is_admin = is_admin(message_pack.member.id)

        if self.plugin.price > 0:
            balance = get_balance(message_pack.member.id)
            if balance < self.plugin.price and str(message_pack.group.id) in config.get("ECO_GROUP", []) and not member_is_admin:
                bot_send_message(
                    message_pack,
                    ToogleChain.plain(f"余额不足，{self.plugin.name}功能需要{self.plugin.price}gb，您剩余{balance}gb\n请通过正常日常聊天来获取gb", quote=message_pack.as_quote())
                )
                return None

        if self.plugin.interval and not interval_limiter.user_interval(
            self.plugin.name, message_pack.member.id, interval=self.plugin.interval
        ) and not member_is_admin and not is_admin_group(message_pack.group.id):
            bot_send_message(
                message_pack,
                ToogleChain.plain(f"[{self.plugin.name}]请求必须间隔[{self.plugin.interval}]秒", quote=message_pack.as_quote())
            )
            return None
        if self.plugin.admin_only and not member_is_admin:
            return None
        if get_block(message_pack, self.plugin):
            return None
        if not is_traffic_free(self.plugin, message_pack) and not member_is_admin:
            traffic_str = get_traffic_time(self.plugin, message_pack)
            if traffic_str:
                bot_send_message(message_pack, traffic_str)
            return None

        prepared = copy.copy(message_pack)
        if message_pack.quote and not self.plugin.ignore_quote:
            prepared.message = ToogleChain.create(
                [*message_pack.message.root, *message_pack.quote.message.root]
            )
            logger.info(f"Afterward msg: {prepared.message.asDisplay()}") # type: ignore
        else:
            prepared.message = ToogleChain.create(list(message_pack.message.root))

        return prepared


MUTE_LIST = [
    {
        "id": 123454321,
        "til_time": datetime.datetime(2077, 7, 7),
        "function": "",
    }
]


def add_mute(id: int, til_time: datetime.datetime, function: str=""):
    for mute_id in MUTE_LIST:
        if id == mute_id["id"] and mute_id["function"] == function:
            mute_id["til_time"] = til_time
            return
    MUTE_LIST.append({
        "id": id,
        "til_time": til_time,
        "function": function,
    })
    return


def get_block(message: MessagePack, plugin: MessageHandler) -> bool:
    if str(message.member.id) in config.get("BLACK_LIST", []):
        return True
    for mute_id in MUTE_LIST:
        if message.member.id == mute_id["id"]:
            if mute_id["til_time"] > datetime.datetime.now():
                logger.info(f"Blocked [{plugin.name}]") # type: ignore
                if mute_id["function"]:
                    if plugin.is_trigger(mute_id["function"]):
                        return True
                else:
                    return True
            else:
                MUTE_LIST.remove(mute_id)
    return False


def get_traffic_time(plugin: MessageHandler, message: MessagePack) -> str:
    tz = TRAFFIC_CTRL.get(plugin.name).get(str(message.group.id))  # type: ignore
    if tz[0][1] - tz[0][0] == 24:  # type: ignore
        return ""
    tz = ", ".join([f"{x[0]}:00 - {x[1]}:00" for x in tz])  # type: ignore
    return f"管理员设置，{plugin.name} 功能在 {tz} 时段禁用"


def is_traffic_free(plugin: MessageHandler, message: MessagePack) -> bool:
    logger.info(f"Triggered [{plugin.name}]")  # type: ignore
    plugin_traffic = TRAFFIC_CTRL.get(plugin.name)
    group_id = str(message.group.id)
    if plugin_traffic and group_id in plugin_traffic.keys():
        now_hr = time.localtime().tm_hour
        for traffic_time in plugin_traffic[group_id]:
            if now_hr >= traffic_time[0] and now_hr < traffic_time[1]:
                return False
    return True


def bot_send_message(
    target: Union[int, MessagePack],
    message: Union[ToogleChain, str],
    friend: bool = False,
) -> bool:
    global BOT_SEND
    if not BOT_SEND:
        logger.error("BOT 未初始化，无法发送消息")
        return False

    if isinstance(target, MessagePack):
        message_type = "private" if friend else target.message_type
        group_id = target.group.id if message_type == "group" else 0
        member_id = target.member.id
        quote = target.as_quote()
    elif friend:
        message_type = "private"
        group_id = 0
        member_id = target
        quote = None
    else:
        message_type = "group"
        group_id = target
        member_id = 0
        quote = None

    msg = MessagePack(
        id = 0,
        message = message if isinstance(message, ToogleChain) else ToogleChain.plain(message),
        group = Group(
            id = group_id,
            name = "",
        ),
        member = Member(
            id = member_id,
            name = "",
        ),
        quote = quote,
        message_type = message_type,
    )
    try:
        return bool(BOT_SEND(msg))
    except Exception:
        logger.exception("发送消息入队失败: message_type=%s", message_type)
        return False


def register_group_file_uploader(
    uploader: Optional[Callable[[int, str, str], Any]],
) -> None:
    global GROUP_FILE_UPLOAD
    GROUP_FILE_UPLOAD = uploader


def bot_upload_group_file(group_id: int, file_name: str, file_path: str) -> Any:
    if not GROUP_FILE_UPLOAD:
        raise RuntimeError("群文件上传器未初始化")
    return GROUP_FILE_UPLOAD(group_id, file_name, file_path)


def send_admins(message: Union[ToogleChain, str]):
    for i in config.get("ADMIN_LIST", []):
        bot_send_message(int(i), message, friend=True)
