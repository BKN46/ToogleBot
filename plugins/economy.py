from typing import Union

from toogle.membership import get_membership_level
from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack
from toogle.economy import get_balance, give_balance, take_balance
from toogle.utils import is_admin


class Membership(MessageHandler):
    name = "大黄狗赞助"
    trigger = r"^我要给大黄狗充钱|^我要赞助大黄狗"
    readme = "大黄狗赞助渠道"

    async def ret(self, message: MessagePack) -> Union[MessageChain, None]:
        return MessageChain.create([
            Image.fromLocalFile("data/sponsor.png"),
            Plain(f"请前往爱发电主页 https://ifdian.net/a/ToogleBot 查看赞助方式"),
        ])


class Balance(MessageHandler):
    name = "余额"
    trigger = r"^/(balance|give_balance|take_balance)"
    readme = "余额操作，不对外开放"
    # readme = "/balance 查询余额\n正常聊天可获取余额、部分功能需要消耗余额\n该功能仅为防止机器人滥用"

    async def ret(self, message: MessagePack) -> Union[MessageChain, None]:
        cmd = message.message.asDisplay()[1:].strip()
        if cmd.startswith("balance") and get_membership_level(message.member.id) > 0:
            return MessageChain.create([Plain(f"您的余额为{get_balance(message.member.id)}gb")])
        elif cmd.startswith("give_balance") and is_admin(message.member.id):
            give_balance(int(cmd.split()[1]), int(cmd.split()[2]))
            return MessageChain.plain(f"已给予{cmd.split()[1]} {cmd.split()[2]}gb, 余额为{get_balance(int(cmd.split()[1]))}gb")
        elif cmd.startswith("take_balance") and is_admin(message.member.id):
            take_balance(int(cmd.split()[1]), int(cmd.split()[2]))
            return MessageChain.plain(f"已扣除{cmd.split()[1]} {cmd.split()[2]}gb, 余额为{get_balance(int(cmd.split()[1]))}gb")
