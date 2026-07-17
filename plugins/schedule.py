import asyncio
import datetime
import json
from typing import Union

import requests

from configs import config
from plugins.others.weibo import get_save_old_otaku
from toogle.adapter import bot_send_message
from toogle.economy import get_balance, give_balance
from toogle.logger import logger
from toogle.message import At, ForwardMessage, Image, MessageChain, Plain
from toogle.message_handler import MESSAGE_HISTORY, MessageHandler, MessageHistory, MessagePack
from toogle.scheduler import (
    PROJECT_ROOT,
    ScheduleModule,
    create_manual_schedule,
    list_schedule_jobs,
    read_manual_schedules,
    remove_manual_schedule,
)
from toogle.utils import SETU_RECORD_PATH, is_admin, is_admin_group, modify_json_file


class DailySetuRanking(ScheduleModule):
    name="每日色图排行"
    hour=0
    minute=0
    second=0

    trigger = r"^色图排行$"

    async def ret(self, message_pack: Union[MessagePack, None]):
        with open(SETU_RECORD_PATH, "r", encoding="utf-8") as record_file:
            all_data = json.load(record_file)
        if message_pack:
            if not is_admin(message_pack.member.id):
                bot_send_message(int(message_pack.group.id), MessageChain.plain("没有权限", quote=message_pack.as_quote()))
                return
            group_data = all_data.get(str(message_pack.group.id), {})
            ranking = sorted(group_data.items(), key=lambda x: x[1], reverse=True)
            message_list = [Plain("今日色图贡献排行榜：\n")]
            for i, (k, v) in enumerate(ranking):
                message_list += [
                    Plain(f"{i+1}. {k}: {v}张\n"),
                ]
                if i >= 10:
                    message_list += [Plain("...")]
                    break
            setu_list = MESSAGE_HISTORY.get(f"setu_{message_pack.group.id}", windows=2000)
            if setu_list:
                bot_send_message(int(message_pack.group.id), MessageHistory.seq_as_forward(setu_list))
            bot_send_message(int(message_pack.group.id), MessageChain(message_list))
            return

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
                MESSAGE_HISTORY.delete(f"setu_{group}")

        with modify_json_file('setu_record_alltime') as alltime_data:
            for group_id, group_data in all_data.items():
                alltime_data[group_id] = {
                    member_id: alltime_data.get(group_id, {}).get(member_id, 0) + member_cnt
                    for member_id, member_cnt in group_data.items()
                }
        with open(SETU_RECORD_PATH, "w", encoding="utf-8") as record_file:
            json.dump({}, record_file, indent=2, ensure_ascii=False)


class MembershipSchedule(ScheduleModule):
    name="会员业务定时任务"
    month="*"
    day=1
    hour=0
    minute=0
    second=0

    async def ret(self, message_pack: Union[MessagePack, None]):
        await asyncio.to_thread(self._refresh_memberships)

    @staticmethod
    def _refresh_memberships():
        with modify_json_file('afdian') as d:
            for qq, info in d.items():
                time_due = datetime.datetime.strptime(info['time_due'], "%Y-%m-%d %H:%M:%S")
                if time_due < datetime.datetime.now():
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
    earthquake_url = "https://www.ceic.ac.cn/data/data.json"

    def __init__(self):
        self.last_monitor_time = datetime.datetime.now()

    async def ret(self, message_pack: Union[MessagePack, None]):
        send_list = self._load_subscriptions()
        enabled_sources = {
            info
            for subscribe_list in send_list.values()
            if isinstance(subscribe_list, list)
            for info in subscribe_list
            if isinstance(info, str)
        }
        source_functions = {
            "earth_quake": self.get_earth_quake,
            "save_old_otaku": self.get_save_old_otaku,
        }
        selected_sources = [
            (name, function)
            for name, function in source_functions.items()
            if name in enabled_sources
        ]
        source_results = await asyncio.gather(
            *(
                self._run_source(name, function)
                for name, function in selected_sources
            )
        )
        send_infos = {
            name: result
            for (name, _), result in zip(selected_sources, source_results)
        }

        for send_title, send_content in send_infos.items():
            if not send_content:
                continue
            for group, subscribe_list in send_list.items():
                if not isinstance(subscribe_list, list):
                    logger.warning("Invalid monitor subscription list for group %s", group)
                    continue
                for info in subscribe_list:
                    if isinstance(info, str) and info == send_title:
                        bot_send_message(int(group), send_content)

        self.last_monitor_time = datetime.datetime.now()

    async def _run_source(self, name, function):
        try:
            return await asyncio.to_thread(function)
        except Exception:
            logger.exception("Scheduled monitor source failed: %s", name)
            return None

    @staticmethod
    def _load_subscriptions() -> dict:
        path = PROJECT_ROOT / "data" / "monitor_send.json"
        if not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("monitor_send.json must contain an object")
        return payload

    def get_save_old_otaku(self):
        res = []
        info = get_save_old_otaku(time_limit=self.last_monitor_time.timestamp())
        if not info:
            return None
        for create_time, msg, pic_url_list, detail_page, comments, key_info in info:
            res.append(MessageChain.create([
                Plain(f"{key_info}\n{create_time}\n"),
                Plain(f"{msg}\n{detail_page}"),
            ] + [
                Image(url=url) for url in pic_url_list
            ]))
            res.append(MessageChain.create([Plain(f'{comments[0]}条评论:\n\n' + '\n\n'.join(comments[1]))]))
        return ForwardMessage.get_quick_forward_message(res, people_name='拯救大龄二次元')


    def get_earth_quake(self):
        try:
            res = requests.get(
                self.earthquake_url,
                headers={"User-Agent": "ToogleBot earthquake monitor"},
                timeout=(5, 15),
            )
            res.raise_for_status()
            data = res.json()
            if not isinstance(data, list):
                raise ValueError("earthquake response must be a list")
            recent_after = datetime.datetime.now() - datetime.timedelta(minutes=30)
            matched = [
                item
                for item in data
                if datetime.datetime.strptime(item["time"], "%Y-%m-%d %H:%M:%S")
                > recent_after
                and float(item["magnitude"]) > 4.0
            ]
        except (requests.RequestException, KeyError, TypeError, ValueError):
            logger.exception("Failed to fetch earthquake monitor data")
            return None
        messages = [
            f"{item['magnitude']}级地震，发生在{item['time']}，位于{item['location']}"
            for item in matched
        ]
        if messages:
            return MessageChain.plain(
                "===== 地震提醒 ======\n"
                + "\n".join(messages)
                + "\n ==================="
            )
        return None


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
            try:
                index = int(msg)
            except ValueError:
                return MessageChain.plain("序号必须是整数")
            return MessageChain.plain(self.del_schedule(message.member.id, index))
        elif message.message.asDisplay().startswith("我的"):
            return MessageChain.plain(self.my_schedule(message.group.id, message.member.id))
        elif message.message.asDisplay().startswith("全部"):
            if not is_admin(message.member.id):
                return MessageChain.plain("没有权限", quote=message.as_quote())
            return MessageChain.plain(list_schedule_jobs())

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

        if not msg:
            return MessageChain.plain("没有内容")

        crond_text = msg.split('\n')[0].split()
        send_text = '\n'.join(msg.split('\n')[1:])

        if len(crond_text) != 6:
            return MessageChain.create([Plain("crondtab格式不正确，为空格分隔：年 月 日 时 分 秒，空则为*")])
        if not send_text.strip():
            return MessageChain.plain("定时内容不能为空")

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

        try:
            self.save_schedule(
                send_text,
                is_programmable,
                single_time,
                message.group.id,
                message.member.id,
                timer_info,
            )
        except ValueError as exc:
            return MessageChain.plain(f"定时配置无效：{exc}")

        return MessageChain.plain("创建成功！", quote=message.as_quote())


    def save_schedule(self, text, is_programmable, single_time, group_id, creator_id, time):
        return create_manual_schedule(
            text=text,
            program=is_programmable,
            single_time=single_time,
            group_id=group_id,
            creator_id=creator_id,
            time_config=time,
        )


    def my_schedule(self, group_id, creator_id):
        schedules = read_manual_schedules()
        schedules = [s for s in schedules if s['creator_id']==creator_id]
        text = f"共{len(schedules)}个定时任务：\n" + '\n'.join([
            f"{i+1}. [to {s['group_id']}] {s['text']} | {s['time']}"
            for i, s in enumerate(schedules)
        ])
        return text


    def del_schedule(self, creator_id, index):
        schedules = [
            item
            for item in read_manual_schedules()
            if item["creator_id"] == creator_id
        ]
        if index < 1 or index > len(schedules):
            return "序号不正确"
        if not remove_manual_schedule(schedules[index - 1]["id"]):
            return "删除失败"
        return "删除成功"
