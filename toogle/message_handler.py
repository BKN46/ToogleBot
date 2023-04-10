import re
from typing import Any, Dict, Optional, Union

from toogle.message import Group, Member, MessageChain, Plain, Quote


class MessagePack:
    def __init__(
        self,
        id: int,
        message: MessageChain,
        group: Group,
        member: Member,
        qoute: Optional[Quote],
    ) -> None:
        self.id = id
        self.message = message
        self.group = group
        self.member = member
        self.qoute = qoute

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

    async def ret(self, message: MessagePack) -> MessageChain:
        return MessageChain([])

def get_user_name(message: MessagePack) -> str:
    return message.member.name or str(message.member.id)
