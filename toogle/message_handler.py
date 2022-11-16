import re
from typing import Any, Dict

from toogle.message import Group, Member, MessageChain, Plain


class MessagePack:
    def __init__(
        self,
        message: MessageChain,
        group: Group,
        member: Member,
    ) -> None:
        self.message = message
        self.group = group
        self.member = member


class MessageHandler:
    trigger = r""
    readme = "这是一个BKN的聊天机器人组件"
    white_list = False
    thread_limit = False

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
