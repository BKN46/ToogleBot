import datetime
from typing import Optional
from toogle.message import At, MessageChain
from toogle.message_handler import MessageHandler, MessagePack
from toogle.nonebot2_adapter import add_mute
from toogle.utils import is_admin


class Mute(MessageHandler):
    name = "禁用成员"
    trigger = r"^\.ban"
    readme = "暂时禁用成员功能"
    interval = 10
    price = 2

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        if not is_admin(message.member.id):
            return

        content = message.message.asDisplay()[4:].split()
        if message.message.get(At):
            target = message.message.get(At)[0].target
        else:
            target = int(content[0])
        
        mute_content = " ".join(content[1:-1]).strip()

        mute_time = content[-1]
        if mute_time.endswith('h'):
            mute_time = int(mute_time[:-1]) * 60
        elif mute_time.endswith('d'):
            mute_time = int(mute_time[:-1]) * 60 * 24
        else:
            mute_time = int(mute_time)
        mute_til_time = datetime.datetime.now() + datetime.timedelta(minutes=mute_time)

        add_mute(target, mute_til_time, mute_content)
        return MessageChain.plain("done", quote=message.as_quote())
