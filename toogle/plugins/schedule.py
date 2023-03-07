import datetime

from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack
from toogle.scheduler import ScheduleModule
from toogle.plugins.compose.daily_news import download_daily
from toogle.nonebot2_adapter import bot_send_group
from toogle.configs import config


class DailyNews(ScheduleModule):
    name="每日新闻"
    hour=9
    minute=30
    second=0

    async def ret(self):
        pic_path = download_daily()
        message = MessageChain.create([Image(path=pic_path)])
        for group in config.get('MAIN_GROUP', []):
            await bot_send_group(int(group), message)


class ScheduleTest(ScheduleModule):
    name="测试定时任务"
    hour=0
    minute=0
    second=0

    async def ret(self):
        pass
        # message = MessageChain.plain("测试定时任务")
