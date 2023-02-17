from apscheduler.schedulers.asyncio import AsyncIOScheduler

from toogle.nonebot2_adapter import bot_send_group

scheduler = AsyncIOScheduler()

# scheduler.add_job(send_daily_news, "cron", minute=0, hour=9, args=[app])
# scheduler.add_job(app.sendGroupMessage, "cron", **timer_data, args=[group, message])
class ScheduleModule:
    name = "BKN的机器人定时组件"
    trigger = r""
    readme = "这是一个BKN的机器人定时组件"
    white_list = False
    thread_limit = False
    interval = 0

    year = -1
    month = -1
    week = -1
    day_of_week = -1
    day = -1
    hour = -1
    minute = -1
    second = 0

    async def ret(self):
        pass

    def regist(self):
        time_dict = {
            x: self.__getattribute__(x) for x in [
                'year',
                'month',
                'week',
                'day_of_week',
                'day',
                'hour',
                'minute',
                'second',
            ] if self.__getattribute__(x) >= 0
        }
        scheduler.add_job(
            self.ret,
            'cron',
            **time_dict
        )


def schedular_start():
    scheduler.start()
