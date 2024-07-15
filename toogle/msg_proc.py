import json
import os
import threading
import time

import nonebot

from toogle.economy import get_balance, give_balance
from toogle.message import At, ForwardMessage, Image, MessageChain, Plain
from toogle.message_handler import MESSAGE_HISTORY, MessagePack
from toogle.mirai_extend import recall_msg
from toogle.nonebot2_adapter import bot_send_message
from toogle.configs import config
from toogle.utils import SETU_RECORD_PATH, detect_pic_nsfw, print_err
from toogle.plugins.openai import gpt_censor, GetOpenAIConversation

POST_PROC_LOCK = threading.Lock()
DELAY_RECALL_POOL = []

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
    DelayedRecall.add_recall(message_pack.group.id, message_pack, only_repeat=True)
    if get_balance(message_pack.member.id) < 15:
        if len(MessageChain(message_pack.message.get(Plain)).asDisplay()) >= 10:
            give_balance(message_pack.member.id, 1)

    if pics:
        if str(message_pack.group.id) in config.get('NSFW_LIST', []) + config.get('ANTI_NSFW_LIST', []):
            if len(pics) > 5:
                pics = pics[:5]
            setu_detect(message_pack, pics)


def setu_detect(message_pack: MessagePack, pics):
    cnt, raw_cnt = 0, 0
    for pic in pics:
        start_time = time.time()
        score, repeat = detect_pic_nsfw(pic.getBytes(), output_repeat=True) # type: ignore
        use_time = (time.time() - start_time) * 1000
        nonebot.logger.info(f"Pic analysis done, nsfw score {score:.5f}, use time {use_time:.2f}ms") # type: ignore
        if score >= 0.25:
            if not repeat:
                cnt +=1
            raw_cnt += 1
    if cnt > 0:
        give_balance(message_pack.member.id, cnt)
        update_setu_record(message_pack.group.id, message_pack.member.id, cnt)
        MESSAGE_HISTORY.add(f"setu_{message_pack.group.id}", message_pack)
    if raw_cnt > 0 and not message_pack.message.get(ForwardMessage, forward_layer=1):
        if str(message_pack.group.id) in config.get('ANTI_NSFW_LIST', []):
            DelayedRecall.add_recall(message_pack.group.id, message_pack)


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
                bot_send_message(
                    int(message_pack.group.id),
                    MessageChain.create([
                        Plain(f"鉴证警报 鉴证警报: {content}\n"),
                        *[At(int(x)) for x in config.get('ADMIN_LIST', [])],
                    ]),
                )
            MESSAGE_HISTORY.delete(f"censor_{message_pack.group.id}")


class DelayedRecall:
    def __init__(self, target, msg: MessagePack, delay=5, max_delay=300):
        self.target = target
        self.msg_list = [msg]
        self.end_time = time.time() + delay
        self.delay = delay
        self.max_delay = max_delay

    def add(self, msg: MessagePack, add_delay=True):
        if not [x for x in self.msg_list if x.id == msg.id]:
            self.msg_list.append(msg)
            if add_delay:
                self.end_time = time.time() + self.delay
                nonebot.logger.info(f"Refreshed recall thread for {msg.member.id}") # type: ignore

    def recall(self):
        while time.time() < self.end_time and not time.time() > self.end_time + self.max_delay:
            time.sleep(1)
        send_list = []
        for msg in self.msg_list:
            if recall_msg(self.target, msg.id, ignore_exception=True):
                send_list.append((msg.member.id, msg.member.name, msg.message))
            time.sleep(0.3)
        send_seg_num = 5
        for i in range(0, len(send_list), send_seg_num):
            bot_send_message(self.target, ForwardMessage.get_quick_forward_message(send_list[i: i+send_seg_num]))
            time.sleep(1)
        DELAY_RECALL_POOL.remove(self)

    def run(self):
        threading.Thread(target=self.recall).start()

    @staticmethod
    def add_recall(target, msg: MessagePack, delay=5, max_delay=300, only_repeat=False):
        for recall_thread in DELAY_RECALL_POOL:
            if recall_thread.target == target and msg.member.id == recall_thread.msg_list[0].member.id:
                recall_thread.add(msg, add_delay=not only_repeat)
                return
        if not only_repeat:
            recall_thread = DelayedRecall(target, msg, delay, max_delay)
            nonebot.logger.info(f"Add recall thread for {msg.member.id} in {target}") # type: ignore
            DELAY_RECALL_POOL.append(recall_thread)
            recall_thread.run()
