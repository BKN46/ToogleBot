import asyncio
import random
import re
import time
from typing import Any, Dict, List, Optional, Union

import nonebot

from toogle.message import Group, Member, MessageChain, Plain, Quote


class MessageHistory:
    def __init__(self, windows=100) -> None:
        self.history = {}
        self.windows = windows

    def add(self, id: int, message: "MessagePack"):
        if id not in self.history:
            self.history[id] = []
        self.history[id].append(message)
        if len(self.history[id]) > self.windows:
            self.history[id].pop(0)

    def get(self, id: int, windows=10) -> List["MessagePack"]:
        if id not in self.history:
            return []
        return self.history[id][-windows:]

    def search(self, group_id: Optional[int]=None, msg_id: Optional[int]=None, text: Optional[str] = None) -> Optional["MessagePack"]:
        for group_id, messages in self.history.items():
            for message in messages:
                if group_id and group_id != message.group.id:
                    continue
                if text and text in message.message.asDisplay():
                    return message
                if msg_id and msg_id == message.id:
                    return message

    def recent(self) -> Optional[List["MessagePack"]]:
        if not self.history:
            return None
        return list(self.history.values())[-1]


MESSAGE_HISTORY = MessageHistory()
RECALL_HISTORY = MessageHistory()


class MessagePack:
    def __init__(
        self,
        id: int,
        message: MessageChain,
        group: Group,
        member: Member,
        quote: Optional[Quote],
    ) -> None:
        self.id = id
        self.message = message
        self.group = group
        self.member = member
        self.quote = quote
        self.time = time.time()

    def as_quote(self):
        return Quote(
            id=self.id,
            sender_id=self.member.id,
            target_id=self.group.id,
            group_id=self.group.id,
            message=self.message,
        )


class MessageHandler:
    name = "BKN的聊天机器人组件"
    trigger = r""
    readme = "这是一个BKN的聊天机器人组件"
    white_list = False
    thread_limit = False
    to_me_trigger = False
    interval = 0

    def __init__(self) -> None:
        pass

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        return self.__init__(*args)

    def is_trigger(self, message: MessagePack) -> bool:
        message_str = message.message.asDisplay()
        if bool(re.search(self.trigger, message_str)):
            return True
        return False

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        return MessageChain([])
    

class ActiveHandler:
    name = "BKN的聊天机器人主动组件"
    trigger = r""
    readme = "这是一个BKN的聊天机器人主动消息组件"
    white_list = False
    thread_limit = False
    to_me_trigger = False
    trigger_rate = 0.001
    interval = 0

    def __init__(self) -> None:
        pass

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        return self.__init__(*args)

    def is_trigger(self, message: MessagePack) -> bool:
        message_str = message.message.asDisplay()
        if bool(re.search(self.trigger, message_str)):
            return True
        return False

    def is_trigger_random(self, message: Optional[MessagePack] = None):
        if random.random() < self.trigger_rate:
            nonebot.logger.success(f"Triggered [{self.name}]")  # type: ignore
            return True
        return False

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        return MessageChain([])

    async def ret_wrapper(self, message: MessagePack) -> Optional[MessageChain]:
        try:
            return await self.ret(message)
        except Exception as e:
            nonebot.logger.error(f"[{self.name}]{repr(e)}") # type: ignore
            return 


class WaitCommandHandler:
    def __init__(self, group_id: int, member_id: int, hit_regex: str, start_time=0.0, timeout=30, sleep_interval=0.1) -> None:
        self.group_id = group_id
        self.member_id = member_id
        self.hit_regex = hit_regex
        self.timeout = timeout
        if start_time == 0:
            self.start_time = time.time()
        else:
            self.start_time = start_time
        self.sleep_interval = sleep_interval

    def is_trigger(self, message: MessagePack) -> bool:
        message_str = message.message.asDisplay()
        if message.group.id != self.group_id or message.member.id != self.member_id:
            return False
        return bool(re.search(self.hit_regex, message_str))

    async def run(self):
        wait_start_time = time.time()
        while time.time() - wait_start_time < self.timeout:
            message = MESSAGE_HISTORY.get(self.group_id, 5)
            for msg in message:
                if msg.time < self.start_time:
                    continue
                if self.is_trigger(msg):
                    return msg
            await asyncio.sleep(self.sleep_interval)
            # time.sleep(self.sleep_interval)
        return None


def get_user_name(message: MessagePack) -> str:
    return message.member.name or str(message.member.id)
