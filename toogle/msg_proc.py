import json
import os
import threading

from toogle.economy import get_balance, give_balance
from toogle.message import At, Image, MessageChain, Plain
from toogle.message_handler import MESSAGE_HISTORY, MessagePack
from toogle.nonebot2_adapter import bot_send_message
from toogle.configs import config
from toogle.utils import SETU_RECORD_PATH, detect_pic_nsfw, print_err
from toogle.plugins.openai import gpt_censor, GetOpenAIConversation

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
    pics = message_pack.message.get(Image, ignore_forawrd=False, forward_layer=1)
    if get_balance(message_pack.member.id) < 15:
        if len(MessageChain(message_pack.message.get(Plain)).asDisplay()) >= 10:
            give_balance(message_pack.member.id, 1)

    if pics:
        if str(message_pack.group.id) in config.get('NSFW_LIST', []):
            cnt = 0
            if len(pics) > 5:
                pics = pics[:5]
            for pic in pics:
                score, repeat = detect_pic_nsfw(pic.getBytes(), output_repeat=True) # type: ignore
                if not repeat and score >= 0.25:
                    cnt +=1 
            if cnt > 0:
                give_balance(message_pack.member.id, cnt)
                update_setu_record(message_pack.group.id, message_pack.member.id, cnt)
                MESSAGE_HISTORY.add(f"setu_{message_pack.group.id}", message_pack)


async def chat_cencor(message_pack: MessagePack):
    if str(message_pack.group.id) in config.get('CENSOR_LIST', []):
        if not message_pack.message.get(Plain) or len(message_pack.message.asDisplay()) < 4:
            return
        MESSAGE_HISTORY.add(f"censor_{message_pack.group.id}", message_pack)
        remain_history = MESSAGE_HISTORY.get(f"censor_{message_pack.group.id}", windows=10)
        if len(remain_history) >= 10:
            try:
                score, content, cost = gpt_censor(remain_history) # type: ignore
            except Exception as e:
                print_err(e, GetOpenAIConversation, message_pack)
                return
            if score >= 30:
                await bot_send_message(
                    int(message_pack.group.id),
                    MessageChain.create([
                        Plain(f"鉴证警报 鉴证警报: {content}\n"),
                        *[At(int(x)) for x in config.get('ADMIN_LIST', [])],
                    ]),
                )
            MESSAGE_HISTORY.delete(f"censor_{message_pack.group.id}")
