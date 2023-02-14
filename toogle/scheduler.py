from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

# scheduler.add_job(send_daily_news, "cron", minute=0, hour=9, args=[app])
# scheduler.add_job(app.sendGroupMessage, "cron", **timer_data, args=[group, message])
class ScheduleModule:
    name = "BKN的聊天机器人组件"
    trigger = r""
    readme = "这是一个BKN的聊天机器人组件"
    white_list = False
    thread_limit = False
    interval = 0

    async def ret(self):
        pass

    def regist(self, handler):
        scheduler.add_job(self.ret)

