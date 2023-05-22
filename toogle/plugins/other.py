from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack
from toogle.nonebot2_adapter import bot_send_message
from toogle.utils import is_admin
import toogle.plugins.others.racehorse as race_horse

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
