import io
import pickle
import random

import PIL.Image

from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack
from toogle.nonebot2_adapter import bot_send_message
from toogle.utils import is_admin
import toogle.plugins.others.racehorse as race_horse

try:
    JOKING_HAZARD_GAME_DATA = pickle.load(open("data/joking_hazard.pkl", "rb"))
except Exception as e:
    JOKING_HAZARD_GAME_DATA = {}

class RaceHorse(MessageHandler):
    name = "模拟赛马"
    trigger = r"^\.racehorse"
    thread_limit = True
    readme = "赛马"

    async def ret(self, message: MessagePack) -> MessageChain:
        if not is_admin(message.member.id):
            return MessageChain.plain("无权限")
        
        race, horse = race_horse.init_race()
        for msg in race_horse.do_race(race, horse, sleep_interval=10):
            await bot_send_message(message.group.id, MessageChain.plain(msg))
        
        return MessageChain.plain("比赛结束")


class JokingHazard(MessageHandler):
    name = "Joking Hazard"
    trigger = r"^\.jokinghazard"
    thread_limit = True
    readme = "氰化欢乐秀桌游 随机卡片"

    async def ret(self, message: MessagePack) -> MessageChain:
        if not JOKING_HAZARD_GAME_DATA:
            return MessageChain.plain("无数据")
        
        # byte pic data
        if random.random() <= 0.8:
            start_two = random.sample(JOKING_HAZARD_GAME_DATA["normal"], 2)
            final_card = random.choice(JOKING_HAZARD_GAME_DATA["red"])
            random.shuffle(start_two)
            cards = start_two + [final_card]
        else:
            cards = random.sample(JOKING_HAZARD_GAME_DATA["normal"], 3)
            random.shuffle(cards)

        pics = [PIL.Image.open(io.BytesIO(x)) for x in cards]
        total_width, total_height = sum([x.width for x in pics]), max([x.height for x in pics])
        combined_pic = PIL.Image.new("RGB", (total_width, total_height))
        x_offset = 0
        for pic in pics:
            combined_pic.paste(pic, (x_offset, 0))
            x_offset += pic.width
        io_buf = io.BytesIO()
        combined_pic.save(io_buf, format="PNG")
        return MessageChain.create([Image(bytes=io_buf.getvalue())])
