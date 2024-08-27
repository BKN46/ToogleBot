import datetime
import json
import os
import traceback
from typing import Union

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from nonebot_plugin_apscheduler import scheduler as nonebot_scheduler
from nonebot.message import handle_event
import nonebot
from poyo import parse_string
from toogle.message import MessageChain
from toogle.message_handler import MessagePack
from toogle.configs import config

from toogle.nonebot2_adapter import bot_send_message, WORK_QUEUE, get_event, PluginWrapper, plugin_run, toogle2nb

native_scheduler = AsyncIOScheduler()
copied_plugin_list = []

class ScheduleModule:
    name = "BKN的机器人定时组件"
    trigger = r""
    readme = "这是一个BKN的机器人定时组件"
    white_list = False
    thread_limit = False
    to_me_trigger = False
    interval = 0
    ignore_quote = False
    price = 0

    single_time = False

    year = -1
    month = -1
    week = -1
    day_of_week = -1
    day = -1
    hour = -1
    minute = -1
    second = 0

    async def ret(self, message_pack: Union[MessagePack, None]):
        pass

    async def ret_wrapper(self, **kwargs):
        try:
            await self.ret(None)
            if self.single_time:
                remove_job(self.name)
                json_path = 'data/schedule.json'
                if not os.path.isfile(json_path):
                    with open(json_path, 'w') as f:
                        f.write('[]')
                schedules = json.load(open(json_path, 'r'))
                schedules = [x for x in schedules if get_job_name(x) != self.name]
                json.dump(schedules, open(json_path, 'w'), indent=4, ensure_ascii=False)
                nonebot.logger.success(f"[Schedule][{self.name}] done and been removed") # type: ignore
                del self
            else:
                nonebot.logger.success(f"[Schedule][{self.name}] done") # type: ignore
        except Exception as e:
            err_info = (
                f"{'*'*20}\n[{datetime.datetime.now().strftime('%Y-%m-%d, %H:%M:%S')}]"
                f"[{self.name}] {repr(e)}\n"
                f"\n{'*'*20}\n{traceback.format_exc()}"
            )
            print(
                err_info,
                file=open("log/schedule_err.log", "a"),
            )
            bot_send_message(
                int(config.get("ADMIN_LIST", [0])[0]),
                err_info,
                friend=True
            )

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
            ] if isinstance(self.__getattribute__(x), str) or self.__getattribute__(x) >= 0
        }
        nonebot_scheduler.add_job(
            self.ret_wrapper,
            'cron',
            kwargs={'name': self.name},
            name=self.name,
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
    single_time = item['single_time']
    text = item['text']
    is_programmable = item['program']
    time = item['time']

    tmp_module = ScheduleModule()
    tmp_module.name = get_job_name(item)
    if single_time:
        tmp_module.single_time = True
    for k, v in time.items():
        tmp_module.__setattr__(k, v)

    if not is_programmable:
        async def ret(message_pack: Union[MessagePack, None]):
            bot_send_message(send_group, text)
    else:
        async def ret(message_pack: Union[MessagePack, None]):
            bot = nonebot.get_bot()
            nb_message = toogle2nb(MessageChain.plain(text))
            event = get_event(bot, send_group, creator_id, nb_message)
            # await handle_event(bot, event)
            message_pack = PluginWrapper.get_message_pack(event, nb_message)
            if not message_pack:
                bot_send_message(send_group, "定时任务出现未知错误")
                return
            for plugin in copied_plugin_list:
                if plugin.plugin.is_trigger(message_pack):
                    await plugin_run(plugin.plugin, message_pack)
                    return
    
    tmp_module.ret = ret
    tmp_module.regist()
    return tmp_module


def all_schedule():
    jobs = nonebot_scheduler.get_jobs()
    res = ""
    for job in jobs:
        res += f"{job.name}\n"
    return res
