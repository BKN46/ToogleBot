import datetime
import os
import pickle
import random
import re
from functools import reduce
import time
from typing import Optional

from toogle.message import At, MessageChain, Plain, Quote
from toogle.message_handler import RECALL_HISTORY, MessageHandler, MessagePack
from toogle.utils import create_path
from toogle.configs import interval_limiter

LOTTERY_PATH = "data/lottery/"
create_path(LOTTERY_PATH)

try:
    SWEAR_DATA = open('data/swear.txt', 'r').readlines()
except Exception as e:
    SWEAR_DATA = []


class HelpMeSelect(MessageHandler):
    name = "随机选择"
    trigger = r"(^(是|应该)(.+还是.+))|(^(.+)不\5.*)"
    readme = "随机选项"
    interval = 30

    async def ret(self, message: MessagePack) -> MessageChain:
        match_str = re.match(self.trigger, message.message.asDisplay())
        if match_str and match_str.group(3):
            proc_str = HelpMeSelect.str_prune(match_str.group(3))
            sel_list = proc_str.split("还是")
            common_prefix = HelpMeSelect.longestCommonPrefix(sel_list)
            return MessageChain.plain(random.choice(sel_list)[len(common_prefix) :])
        elif match_str and match_str.group(5):
            proc_str = HelpMeSelect.str_prune(match_str.group(5))
            return MessageChain.plain(random.choice([proc_str, f"不{proc_str}"]))
        else:
            raise Exception("No match!")

    @staticmethod
    def str_prune(strs: str) -> str:
        end_ignore = ["?", "？", "呢", "捏"]
        for end_chr in end_ignore:
            while strs.endswith(end_chr):
                strs = strs[:-1]
        return strs

    @staticmethod
    def longestCommonPrefix(strs) -> str:
        if not strs:
            return ""

        def lcp(str1: str, str2: str):
            length = min(len(str1), len(str2))
            idx = 0
            while idx < length and str1[idx] == str2[idx]:
                idx += 1
            return str1[:idx]

        return reduce(lcp, strs)


class NowTime(MessageHandler):
    name = "世界时间"
    time_mapping = {
        "夏威夷": -10,
        "阿拉斯加": -9,
        "太平洋标准": -8,
        "加州": -8,
        "洛杉矶": -8,
        "美西": -8,
        "西海岸": -8,
        "美国西部": -8,
        "北美山区标准": -7,
        "得克萨斯": -6,
        "墨西哥": -6,
        "美中": -6,
        "美国中部": -6,
        "东海岸": -5,
        "美东": -5,
        "波士顿": -5,
        "纽约": -5,
        "美国东部": -5,
        "巴西": -4,
        "阿根廷": -3,
        "欧洲西部": 0,
        "西欧": 0,
        "格林威治标准": 0,
        "英国": 0,
        "西班牙": 0,
        "葡萄牙": 0,
        "欧洲中部": 1,
        "法国": 1,
        "德国": 1,
        "挪威": 1,
        "瑞典": 1,
        "瑞士": 1,
        "意大利": 1,
        "欧洲东部": 2,
        "东欧": 2,
        "以色列": 2,
        "乌克兰": 2,
        "加里宁格勒": 2,
        "俄罗斯": 3,
        "莫斯科": 3,
        "萨马拉": 4,
        "阿联酋": 4,
        "海湾标准": 4,
        "阿塞拜疆": 5,
        "巴基斯坦": 5,
        "印度": 5.5,
        "鄂木斯克": 6,
        "泰国": 7,
        "越南": 7,
        "老挝": 7,
        "北京": 8,
        "台湾": 8,
        "香港": 8,
        "新加坡": 8,
        "伊尔库茨克": 8,
        "菲律宾": 8,
        "东京": 9,
        "日本": 9,
        "韩国": 9,
        "朝鲜": 9,
        "雅库茨克": 9,
        "海参崴": 10,
        "悉尼": 10,
        "澳大利亚": 10,
        "所罗门群岛": 11,
        "新西兰": 12,
    }
    tz_direct_mapping = {
        # "GMT": 0,
        # "PST": -8,
        # "MST": -7,
        # "CST": -6,
        # "EST": -5,
        # "AST": -4,
        **{f"UTC{'+' if i>0 else ''}{i if i!= 0 else ''}": i for i in range(-12, 13)}
    }
    tz_reg_list = "|".join([f"{k}" for k, v in time_mapping.items()])
    tz_direct_reg_list = "|".join([f"{k}" for k, v in tz_direct_mapping.items()])
    trigger = f".*({tz_reg_list})时间.*"
    readme = "快速查询世界当前时间"

    async def ret(self, message: MessagePack) -> MessageChain:
        message_content = message.message.asDisplay()
        tz_str = re.match(self.trigger, message_content).group(1)  # type: ignore
        time_shift = self.time_mapping.get(tz_str)
        if not tz_str:
            tz_str = re.match(self.trigger, message_content).group(2)  # type: ignore
            time_shift = self.tz_direct_mapping.get(tz_str)

        time_zone = datetime.timezone(datetime.timedelta(hours=time_shift))  # type: ignore
        now_time = datetime.datetime.now(tz=time_zone)
        dst_delta = now_time.dst()
        dst_str = f"(夏令时)" if dst_delta else ""
        time_str = now_time.strftime("%Y年%m月%d日 %H:%M:%S")
        time_res = f"现在{tz_str}时间(UTC{'+' if time_shift > 0 else ''}{time_shift})是\n{time_str}{dst_str}"  # type: ignore
        return MessageChain.create([Plain(time_res)])


class Swear(MessageHandler):
    name = "骂人"
    trigger = r"^骂我$"
    white_list = False
    thread_limit = False
    interval = 300
    readme = "找喷"

    async def ret(self, message: MessagePack) -> MessageChain:
        if SWEAR_DATA:
            return MessageChain.plain(random.choice(SWEAR_DATA).strip())
        else:
            return MessageChain.plain("因为藏话数据库没有加载，所以我只能先说一句你妈死了。")


class Lottery(MessageHandler):
    name = "抽奖"
    trigger = r"^(发起抽奖|查看抽奖|参与抽奖|抽([0-9])+人\s(.*)$)"
    white_list = False
    thread_limit = False
    readme = "发起抽奖/参与抽奖"

    """ lottery dict
    {
        'group': str,
        'creator': str,
        'draw_list': list[str],
    }
    """

    async def ret(self, message: MessagePack) -> MessageChain:
        message_content = message.message.asDisplay()
        lottery_list = [x.replace(".pickle", "") for x in os.listdir(LOTTERY_PATH)]
        if message_content.startswith("发起抽奖"):
            lottery_name = message_content[4:].strip()
            if lottery_name in lottery_list:
                return MessageChain.create([Plain(f"[{lottery_name}]抽奖已存在")])
            lottery_dict = {
                "group": str(message.group.id),
                "creator": str(message.member.id),
                "draw_list": [],
            }
            lottery_path = f"{LOTTERY_PATH}{lottery_name}.pickle"
            pickle.dump(lottery_dict, open(lottery_path, "wb"))
            return MessageChain.create([Plain(f"成功创建[{lottery_name}]抽奖")])

        elif message_content.startswith("查看抽奖"):
            lottery_name = message_content[4:].strip()
            if lottery_name not in lottery_list:
                return MessageChain.create([Plain(f"[{lottery_name}]抽奖不存在")])
            lottery_path = f"{LOTTERY_PATH}{lottery_name}.pickle"
            lottery_dict = pickle.load(open(lottery_path, "rb"))
            lottery_member_num = len(lottery_dict["draw_list"])
            res = (
                f"[{lottery_name}]由{lottery_dict['creator']}创建\n"
                f"抽奖名单共{lottery_member_num}人：\n" + "\n".join(lottery_dict["draw_list"])
            )
            return MessageChain.create([Plain(res)])

        elif message_content.startswith("参与抽奖"):
            lottery_name = message_content[4:].strip()
            if not lottery_name:
                return MessageChain.create([Plain(f"请填写要参与的抽奖名称！")])
            if lottery_name not in lottery_list:
                return MessageChain.create([Plain(f"[{lottery_name}]抽奖不存在")])
            lottery_path = f"{LOTTERY_PATH}{lottery_name}.pickle"
            lottery_dict = pickle.load(open(lottery_path, "rb"))
            member_id = str(message.member.id)
            if member_id in lottery_dict.get("draw_list"):
                return MessageChain.create([Plain(f"你已经在[{lottery_name}]抽奖名单中")])
            lottery_dict["draw_list"].append(member_id)
            pickle.dump(lottery_dict, open(lottery_path, "wb"))
            return MessageChain.create([Plain(f"成功参与[{lottery_name}]抽奖")])

        elif message_content.startswith("抽"):
            re_match = re.search(self.trigger, message_content)
            number = int(re_match.group(2))  # type: ignore
            lottery_name = re_match.group(3)  # type: ignore
            if lottery_name not in lottery_list:
                return MessageChain.create([Plain(f"[{lottery_name}]抽奖不存在")])

            lottery_path = f"{LOTTERY_PATH}{lottery_name}.pickle"
            lottery_dict = pickle.load(open(lottery_path, "rb"))

            if str(message.member.id) != lottery_dict["creator"]:
                return MessageChain.create([Plain(f"你不是[{lottery_name}]抽奖的创建人")])

            lottery_member_num = len(lottery_dict["draw_list"])
            if lottery_member_num < number:
                return MessageChain.create(
                    [
                        Plain(
                            f"[{lottery_name}]抽奖名单人数不足，需{number}人，现有{lottery_member_num}人"
                        )
                    ]
                )

            lucky_list = random.sample(lottery_dict["draw_list"], number)
            at_list = []
            for x in lucky_list:
                at_list += [
                    Plain(f"{x} "),
                    At(target=int(x)),
                    Plain(f"\n"),
                ]
            os.remove(lottery_path)
            return MessageChain.create(
                [
                    Plain(
                        f"[{lottery_name}]抽奖共{lottery_member_num}人，抽{number}人\n中奖名单为：\n"
                    )
                ]
                + at_list
            )

        return MessageChain.create([Plain(f"[抽奖]未知错误")])


class SeeRecall(MessageHandler):
    name = "反撤回"
    trigger = r"撤回什么了"
    white_list = False
    thread_limit = False
    readme = "查看撤回记录"

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        recall_history = RECALL_HISTORY.get(message.group.id)
        if not recall_history:
            return MessageChain.create([Plain(f"最近没有撤回记录")])

        recall_message_pack = recall_history[-1]
        if time.time() - recall_message_pack.time > 60 * 10:
            return MessageChain.create([Plain(f"十分钟内没有撤回记录")])

        combined_msg_pack = [recall_message_pack]
        last_time = recall_message_pack.time
        for msg in recall_history[::-1]:
            if msg.id == recall_message_pack.id:
                continue
            elif last_time - msg.time > 30:
                break
            else:
                combined_msg_pack.append(msg)
                last_time = msg.time
        
        t_shift = lambda x : datetime.datetime.fromtimestamp(x.time).strftime("%Y-%m-%d %H:%M:%S")
        res_raw = [
            [
                Plain(
                    f"[{t_shift(msg_pack)}]{msg_pack.member.name}({msg_pack.member.id})撤回了一条消息：\n"
                )
            ] + msg_pack.message.root + [Plain("\n")] # type: ignore
            for msg_pack in combined_msg_pack
        ]
        res = []
        for x in res_raw:
            res += x
        
        return MessageChain.create(res)

