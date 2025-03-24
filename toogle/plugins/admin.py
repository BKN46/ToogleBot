import datetime
import json
import time
from typing import Optional
from toogle.message import At, MessageChain, Plain, Quote
from toogle.message_handler import MessageHandler, MessagePack
from toogle.mirai_extend import mute_member
from toogle.nonebot2_adapter import add_mute, bot_send_message
from toogle.utils import is_admin
from toogle.configs import config


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


VOTE_MUTE_DICT = {}

class VoteMute(MessageHandler):
    name = "自动禁言发💩的"
    trigger = r"屎"
    readme = "自动禁言发💩的"
    interval = 10

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        if str(message.group.id) not in config['ANTI_SHIT_LIST']:
            return
        message_content = ''.join([x.text for x in message.message.get(Plain)][0])
        if message_content.strip() != "屎":
            return
        if not message.quote:
            return MessageChain.plain("请回复你觉得是屎的发言", quote=message.as_quote())

        target_id = message.quote.sender_id
        vote_mute_dict_key = f"{message.group.id}_{target_id}"

        if time.time() - VOTE_MUTE_DICT.get(vote_mute_dict_key, {'time': 0})['time'] < 600:
            if message.member.id not in VOTE_MUTE_DICT[vote_mute_dict_key]['vote_member']:
                VOTE_MUTE_DICT[vote_mute_dict_key]['vote_member'].append(message.member.id)
        else:
            VOTE_MUTE_DICT[vote_mute_dict_key] = {
                'time': time.time(),
                'vote_member': [message.member.id]
            }

        if len(VOTE_MUTE_DICT[vote_mute_dict_key]['vote_member']) >= 3:
            mute_member(message.group.id, target_id, 600)
            VOTE_MUTE_DICT[vote_mute_dict_key]['time'] = 0
