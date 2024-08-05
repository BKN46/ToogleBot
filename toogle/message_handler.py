import asyncio
import json
import os
import pickle
import random
import re
import time
from typing import Any, Dict, List, Optional, Union

import nonebot

from toogle.message import Group, Member, MessageChain, Plain, Quote, ForwardMessage


class MessageHistory:
    def __init__(self, windows=2000) -> None:
        self.history = {}
        self.windows = windows

    def add(self, id, message: "MessagePack"):
        if id not in self.history:
            self.history[id] = []
        self.history[id].append(message)
        if len(self.history[id]) > self.windows:
            self.history[id].pop(0)

    def get(self, id, windows=10) -> List["MessagePack"]:
        if id not in self.history:
            return []
        return self.history[id][-windows:]

    def delete(self, id):
        if id in self.history:
            del self.history[id]

    def search(self, group_id, msg_id: Optional[int]=None, text: Optional[str] = None) -> Optional["MessagePack"]:
        for iter_group_id, messages in self.history.items():
            if group_id and group_id != iter_group_id:
                continue
            for message in messages:
                if text and text in message.message.asDisplay():
                    return message
                if msg_id and msg_id == message.id:
                    return message

    def recent(self) -> Optional[List["MessagePack"]]:
        if not self.history:
            return None
        return list(self.history.values())[-1]
    
    def get_prev(self, message: "MessagePack", num=5) -> Optional[List["MessagePack"]]:
        if not self.history:
            return None
        if message.group.id not in self.history:
            return None
        for messages in self.history[message.group.id]:
            for i, msg in enumerate(messages):
                if msg.id == message.id:
                    if i > 0:
                        return messages[max(i-num, 0):i]
                    return None
    
    def save_str(self, path: str):
        with open(path, "w") as f:
            f.write(json.dumps({
                k: [x.to_dict() for x in v]
                for k, v in self.history.items()
            }, indent=2, ensure_ascii=False))

    def save(self, path: str):
        with open(path, "wb") as f:
            pickle.dump(self.history, f)
    
    def load(self, path: str):
        if os.path.exists(path):
            with open(path, "rb") as f:
                self.history = pickle.load(f)

    @staticmethod
    def seq_as_forward(message_list: List["MessagePack"]) -> MessageChain:
        return MessageChain([ForwardMessage(
            ForwardMessage.get_node_list([
                (msg.member.id, int(msg.time), msg.member.name, msg.message)
                for msg in message_list
            ]),
            sender_id=0,
            time=int(time.time()),
            sender_name="历史消息",
            message_id=0,
            message=MessageChain.plain('历史消息'),
        )])


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
        
        self.member.name = get_user_name(self)

    def as_quote(self):
        return Quote(
            id=self.id,
            sender_id=self.member.id,
            target_id=self.group.id,
            group_id=self.group.id,
            message=self.message,
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "message": self.message.to_dict(),
            "group": self.group.to_dict(),
            "member": self.member.to_dict(),
            "time": self.time,
            **({"quote": self.quote.to_dict()} if self.quote else {}),
        }


class MessageHandler:
    name = "BKN的聊天机器人组件"
    trigger = r""
    readme = "这是一个BKN的聊天机器人组件"
    white_list = False
    thread_limit = False
    to_me_trigger = False
    ignore_quote = False
    interval = 0
    price = 0

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

try:
    USER_INFO = json.load(open("data/user_info.json", "r"))
except Exception as e:
    USER_INFO = {}

def get_user_name(message: MessagePack) -> str:
    return USER_INFO.get(str(message.group.id), {}).get(str(message.member.id), {}).get("nickname", None) or message.member.name or str(message.member.id)
