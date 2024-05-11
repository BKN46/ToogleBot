import json
import os
import threading

from toogle.economy import get_balance, give_balance
from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MessagePack
from toogle.nonebot2_adapter import bot_send_message
from toogle.configs import config
from toogle.utils import SETU_RECORD_PATH, detect_pic_nsfw

POST_PROC_LOCK = threading.Lock()

def update_setu_record(group_id, member_id, cnt):
    group_id = str(group_id)
    member_id = str(member_id)
    with POST_PROC_LOCK:
        with open(SETU_RECORD_PATH, "r") as f:
            record = json.load(f)
        if group_id not in record:
            record[group_id] = {member_id: cnt}
        else:
            if member_id not in record[group_id]:
                record[group_id][member_id] = cnt
            else:
                record[group_id][member_id] += cnt
        with open(SETU_RECORD_PATH, "w") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)


async def chat_earn(message_pack: MessagePack):
    pics = message_pack.message.get(Image)
    if get_balance(message_pack.member.id) < 15:
        if len(MessageChain(message_pack.message.get(Plain)).asDisplay()) >= 10:
            give_balance(message_pack.member.id, 1)

    if pics:
        if str(message_pack.group.id) in config.get('NSFW_LIST', []):
            cnt = 0
            for pic in pics:
                score, repeat = detect_pic_nsfw(pic.getBytes(), output_repeat=True) # type: ignore
                if not repeat and score >= 0.25:
                    cnt +=1 
            if cnt > 0:
                give_balance(message_pack.member.id, cnt)
                update_setu_record(message_pack.group.id, message_pack.member.id, cnt)
