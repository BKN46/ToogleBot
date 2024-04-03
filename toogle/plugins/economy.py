from typing import Union

from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack
from toogle.economy import get_balance, give_balance, take_balance
from toogle.utils import is_admin


class Balance(MessageHandler):
    name = "余额"
    trigger = r"^/(balance|give_balance|take_balance)"
    readme = "大黄狗余额操作"

    async def ret(self, message: MessagePack) -> Union[MessageChain, None]:
        cmd = message.message.asDisplay()[1:].strip()
        if cmd.startswith("balance"):
            return MessageChain.create([Plain(f"您的余额为{get_balance(message.member.id)}gb")])
        elif cmd.startswith("give_balance") and is_admin(message.member.id):
            give_balance(int(cmd.split()[1]), int(cmd.split()[2]))
            return MessageChain.plain(f"已给予{cmd.split()[1]} {cmd.split()[2]}gb, 余额为{get_balance(int(cmd.split()[1]))}gb")
        elif cmd.startswith("take_balance") and is_admin(message.member.id):
            take_balance(int(cmd.split()[1]), int(cmd.split()[2]))
            return MessageChain.plain(f"已扣除{cmd.split()[1]} {cmd.split()[2]}gb, 余额为{get_balance(int(cmd.split()[1]))}gb")