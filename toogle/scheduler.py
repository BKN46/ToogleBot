import datetime
import json
import os
import traceback

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from nonebot_plugin_apscheduler import scheduler as nonebot_scheduler
import nonebot

from toogle.nonebot2_adapter import bot_send_message, WORK_QUEUE

native_scheduler = AsyncIOScheduler()

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

    async def ret_wrapper(self, **kwargs):
        try:
            await self.ret()
            nonebot.logger.success(f"[Schedule][{self.name}] done") # type: ignore
        except Exception as e:
            print(
                f"{'*'*20}\n[{datetime.datetime.now().strftime('%Y-%m-%d, %H:%M:%S')}]"
                f"[{self.name}] {repr(e)}\n"
                f"\n{'*'*20}\n{traceback.format_exc()}",
                file=open("schedule_err.log", "a"),
            )

    def regist(self, scheduler):
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
            ] if isinstance(self.__getattribute__(x), str) or self.__getattribute__(x) >= 0
        }
        scheduler.add_job(
            self.ret_wrapper,
            'cron',
            kwargs={'name': self.name},
            **time_dict
        )
        nonebot.logger.success(f"[Schedule][{self.name}] registed!") # type: ignore


def schedule_time_to_str(time_dict):
    return '_'.join([f"{v}" for k, v in time_dict.items()])


def schedular_start():
    jobs = native_scheduler.get_jobs()
    for job in jobs:
        nonebot.logger.success(f"[Schedule][{job.kwargs.get('name')}] trigger: {job.trigger}") # type: ignore
    native_scheduler.start()


def reload_manual_schedular():
    json_path = 'data/schedule.json'
    if not os.path.exists(json_path):
        return
    schedular_list = json.load(open(json_path, 'r'))
    for item in schedular_list:
        jobs = nonebot_scheduler.get_jobs()
        if get_job_name(item) in [job.name for job in jobs]:
            continue
        load_manual_schedular(item)


def remove_job(name):
    jobs = nonebot_scheduler.get_jobs()
    for job in jobs:
        if job.name == name:
            nonebot_scheduler.remove_job(job.id)
            return True
    return False


def get_job_name(item):
    send_group = item['group_id']
    creator_id = item['creator_id']
    text = item['text']
    time = item['time']
    return f"{creator_id}_{send_group}_{text}_{schedule_time_to_str(time)}"


def load_manual_schedular(item):
    send_group = item['group_id']
    creator_id = item['creator_id']
    text = item['text']
    is_programmable = item['program']
    time = item['time']

    tmp_module = ScheduleModule()
    tmp_module.name = get_job_name(item)
    for k, v in time.items():
        tmp_module.__setattr__(k, v)

    async def ret():
        await bot_send_message(send_group, text)
    
    tmp_module.ret = ret
    tmp_module.regist(nonebot_scheduler)
