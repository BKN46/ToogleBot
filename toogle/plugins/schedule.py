import datetime
import json
import os
import time
from typing import Union

import bs4
import requests

from toogle.economy import get_balance, give_balance
from toogle.message import Image, MessageChain, Plain, At
from toogle.message_handler import MESSAGE_HISTORY, MessageHandler, MessageHistory, MessagePack
from toogle.scheduler import ScheduleModule, all_schedule, get_job_name, load_manual_schedular, remove_job
from toogle.plugins.compose.daily_news import download_daily
from toogle.nonebot2_adapter import bot_send_message
from toogle.configs import config
from toogle.utils import SETU_RECORD_PATH, get_main_groups, is_admin, is_admin_group, modify_json_file


# class DailyNews(ScheduleModule):
#     name="每日新闻"
#     hour=9
#     minute=30
#     second=0

#     async def ret(self):
#         pic_path = download_daily()
#         message = MessageChain.create([Image(path=pic_path)])
#         for group in get_main_groups():
#             bot_send_message(int(group), message)


# class HealthyTips(ScheduleModule):
#     name="提肛喝水小助手"
#     hour="10-21"
#     minute=0
#     second=0

#     async def ret(self):
#         message = MessageChain.plain("提肛！喝水！拉伸！")
#         for group in config.get('HEALTHCARE_GROUP_LIST', []):
#             bot_send_message(int(group), message)


class DailySetuRanking(ScheduleModule):
    name="每日色图排行"
    hour=0
    minute=0
    second=0

    trigger = r"^色图排行$"

    async def ret(self, message: Union[MessagePack, None]):
        all_data = json.load(open(SETU_RECORD_PATH, 'r'))
        if message:
            if not is_admin(message.member.id):
                return MessageChain.plain("没有权限", quote=message.as_quote())
            group_data = all_data.get(str(message.group.id), {})
            ranking = sorted(group_data.items(), key=lambda x: x[1], reverse=True)
            message_list = [Plain("今日色图贡献排行榜：\n")]
            for i, (k, v) in enumerate(ranking):
                message_list += [
                    Plain(f"{i+1}. {k}: {v}张\n"),
                ]
                if i >= 10:
                    message_list += [Plain("...")]
                    break
            setu_list = MESSAGE_HISTORY.get(f"setu_{message.group.id}", windows=2000)
            if setu_list:
                bot_send_message(int(message.group.id), MessageHistory.seq_as_forward(setu_list))
            return MessageChain(message_list)

        for group in config.get('NSFW_LIST', []):
            group_data = all_data.get(str(group), {})
            if len(group_data) == 0:
                continue
            ranking = sorted(group_data.items(), key=lambda x: x[1], reverse=True)
            message_list = [Plain("今日色图贡献排行榜：\n")]
            for i, (k, v) in enumerate(ranking):
                message_list += [
                    Plain(f"{i+1}. "),
                    At(k),
                    Plain(f": {v}张\n"),
                ]
                if i >= 10:
                    message_list += [Plain("...")]
                    break

            if len(ranking) > 0:
                bot_send_message(int(group), MessageChain(message_list))

            setu_list = MESSAGE_HISTORY.get(f"setu_{group}", windows=2000)
            if setu_list:
                # bot_send_message(int(group), MessageHistory.seq_as_forward(setu_list))
                MESSAGE_HISTORY.delete(f"setu_{group}")

        with modify_json_file('setu_record_alltime') as alltime_data:
            for group_id, group_data in all_data.items():
                alltime_data[group_id] = {
                    member_id: alltime_data.get(group_id, {}).get(member_id, 0) + member_cnt
                    for member_id, member_cnt in group_data.items()
                }
        json.dump({}, open(SETU_RECORD_PATH, 'w'), indent=2, ensure_ascii=False)


# class ScheduleTest(ScheduleModule):
#     name="测试定时任务"
#     second=0

#     async def ret(self):
#         pass

class MembershipSchedule(ScheduleModule):
    name="会员业务定时任务"
    month="*"
    day=1
    hour=0
    minute=0
    second=0

    async def ret(self, message_pack: Union[MessagePack, None]):
        with modify_json_file('afdian') as d:
            for qq, info in d.items():
                time_due = datetime.datetime.strptime(info['time_due'], "%Y-%m-%d %H:%M:%S")
                if time_due < datetime.datetime.now():
                    del d[qq]
                    continue
                else:
                    trade_plan = info['trade_plan']
                    balance_left = get_balance(int(qq))
                    target_balance = 3000 if trade_plan == "大黄狗大会员" else 500
                    if balance_left < target_balance:
                        give_balance(int(qq), target_balance - balance_left)


class ScheduledMonitor(ScheduleModule):
    name="定时监测"
    minute="*/5"
    second=0

    last_monitor_time = datetime.datetime.now()
    with modify_json_file('monitor_send') as record:
        send_list = record

    async def ret(self, message_pack: Union[MessagePack, None]):
        send_infos = {
            'earth_quake': self.get_earth_quake(),
        }
        
        for send_title, send_content in send_infos.items():
            if not send_content:
                continue
            for group, info in self.send_list.items():
                if isinstance(info, str) and info == send_title:
                    bot_send_message(int(group), MessageChain.plain(send_content)) # TODO: add other form of sending
                elif isinstance(info, dict) and send_title == info.get('function', ''):
                    pass
                
        self.last_monitor_time = datetime.datetime.now()


    def get_earth_quake(self):
        url = "https://www.ceic.ac.cn/speedsearch?time=1"
        res = requests.get(url, verify=False)
        print(res.text, file=open('test/earth_quake.html', 'w'))
        bs = bs4.BeautifulSoup(res.text, 'html.parser')
        table = bs.find('table', {'class': 'speed-table1'})
        if not table:
            return ''
        res = []
        for tr in table.find_all('tr'): # type: ignore
            tds = tr.find_all('td')
            if len(tds) < 6:
                continue
            level = tds[0].text
            happen_time = datetime.datetime.strptime(tds[1].text, '%Y-%m-%d %H:%M:%S')
            location = tds[5].text
            if happen_time > self.last_monitor_time:
                res.append(f"{level}级地震，发生在{happen_time}，位于{location}")
        if len(res) > 0:
            return '===== 地震提醒 ======\n' + '\n'.join(res) + '\n ==================='
        return ''


    def get_bilibili_update(self, mid):
        url = "https://api.bilibili.com/x/space/wbi/arc/search"
        header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
        }
        query = {
            "mid": mid,
            "pn": 1,
            "ps": 30,
            "order": "pubdate",
            "platform": "web",
            "wts": int(time.time()),
        }
        res = requests.get(url, headers=header, params=query)     

        output_res = []
        vlist = res.json()['data']['list']['vlist']
        for video in vlist:
            vtime = datetime.datetime.fromtimestamp(video['created'])
            if vtime < self.last_monitor_time:
                break
            link = f"https://www.bilibili.com/video/{video['bvid']}"
            output_res.append(f"{video['author']}发布了《{video['title']}》{vtime}\n{link}")
        if output_res:
            return '\n'.join(output_res)


class CreateSchedule(MessageHandler):
    name="创建定时"
    trigger = r"^(创建|我的|删除|全部)定时(可触发|)(单次|)"
    white_list = False
    readme = "创建定时任务"

    async def ret(self, message: MessagePack) -> MessageChain:
        if not is_admin(message.member.id) and not is_admin_group(message.group.id):
            return MessageChain.plain("没有权限", quote=message.as_quote())

        msg = message.message.asDisplay()[4:].strip()

        if message.message.asDisplay().startswith("删除"):
            return MessageChain.plain(self.del_schedule(message.group.id, message.member.id, int(msg)))
        elif message.message.asDisplay().startswith("我的"):
            return MessageChain.plain(self.my_schedule(message.group.id, message.member.id))
        elif message.message.asDisplay().startswith("全部"):
            if not is_admin(message.member.id):
                return MessageChain.plain("没有权限", quote=message.as_quote())
            return MessageChain.plain(all_schedule())

        if msg.startswith("可触发"):
            is_programmable = True
            msg = msg[3:].strip()
        else:
            is_programmable = False

        if msg.startswith("单次"):
            single_time = True
            msg = msg[2:].strip()
        else:
            single_time = False

        if len(msg.split('\n')) < 1:
            return MessageChain.plain("没有内容")

        crond_text = msg.split('\n')[0].split()
        send_text = '\n'.join(msg.split('\n')[1:])

        if len(crond_text) < 6:
            return MessageChain.create([Plain("crondtab格式不正确，为空格分隔：年 月 日 时 分 秒，空则为*")])

        timer_header = [
            "year",
            "month",
            "day",
            "hour",
            "minute",
            "second",
        ]
        timer_info = {
            k: crond_text[i]
            for i, k in enumerate(timer_header) if crond_text[i]!='*'
        }

        if 'minute' not in timer_info or 'second' not in timer_info:
            return MessageChain.create([Plain("不支持秒/分钟级重复！")])
        
        self.save_schedule(
            send_text,
            is_programmable,
            single_time,
            message.group.id,
            message.member.id,
            timer_info,
        )
        
        return MessageChain.plain("创建成功！", quote=message.as_quote())
    

    def save_schedule(self, text, is_programmable, single_time, group_id, creator_id, time):
        json_path = 'data/schedule.json'
        if not os.path.isfile(json_path):
            with open(json_path, 'w') as f:
                f.write('[]')
        schedules = json.load(open(json_path, 'r'))
        item = {
            'text': text,
            'program': is_programmable,
            'single_time': single_time,
            'group_id': group_id,
            'creator_id': creator_id,
            'time': time,
        }
        schedules.append(item)
        json.dump(schedules, open(json_path, 'w'), indent=4, ensure_ascii=False)
        load_manual_schedular(item)


    def my_schedule(self, group_id, creator_id):
        json_path = 'data/schedule.json'
        if not os.path.isfile(json_path):
            with open(json_path, 'w') as f:
                f.write('[]')
        schedules = json.load(open(json_path, 'r'))
        schedules = [s for s in schedules if s['creator_id']==creator_id]
        text = f"共{len(schedules)}个定时任务：\n" + '\n'.join([
            f"{i+1}. [to {s['group_id']}] {s['text']} | {s['time']}"
            for i, s in enumerate(schedules)
        ])
        return text
    

    def del_schedule(self, group_id, creator_id, index):
        json_path = 'data/schedule.json'
        if not os.path.isfile(json_path):
            with open(json_path, 'w') as f:
                f.write('[]')
        schedules = json.load(open(json_path, 'r'))
        if index < 1 or index > len(schedules):
            return "序号不正确"
        if not remove_job(get_job_name(schedules[index-1])):
            return "删除失败"
        del schedules[index-1]
        json.dump(schedules, open(json_path, 'w'), indent=4, ensure_ascii=False)
        return "删除成功"
