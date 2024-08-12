import datetime
import json
import os
import pickle
import random
import re
from functools import reduce
import time
from typing import Optional

from toogle.message import At, MessageChain, Plain, Quote
from toogle.message_handler import RECALL_HISTORY, USER_INFO, MessageHandler, MessagePack
from toogle.utils import create_path, is_admin, modify_json_file
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
    interval = 10
    price = 2

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        match_str = re.match(self.trigger, message.message.asDisplay())
        if match_str and match_str.group(3):
            proc_str = HelpMeSelect.str_prune(match_str.group(3))
            sel_list = proc_str.split("还是")
            common_prefix = HelpMeSelect.longestCommonPrefix(sel_list)
            if len(common_prefix) == len(sel_list[0]):
                return MessageChain.plain("那你问我？", quote=message.as_quote())
            return MessageChain.plain(random.choice(sel_list)[len(common_prefix) :], quote=message.as_quote())
        elif match_str and match_str.group(5):
            proc_str = HelpMeSelect.str_prune(match_str.group(5))
            if proc_str in ["时", "贱", "烦", "好", "动", "敢", "不", "行"]:
                return
            return MessageChain.plain(random.choice([proc_str, f"不{proc_str}"]), quote=message.as_quote())
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
        # "北京": 8,
        # "台湾": 8,
        # "香港": 8,
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
        "GMT": 0,
        "PDT": -7,
        "PST": -8,
        "BST": 1,
        "CET": 1,
        "MST": -7,
        "CST": -6,
        "EST": -5,
        "AST": -4,
        **{f"UTC{'+' if i>0 else ''}{i if i!= 0 else ''}": i for i in range(-12, 13)}
    }
    tz_reg_list = "|".join([f"{k}" for k, v in time_mapping.items()])
    tz_direct_reg_list = "|".join([f"{k}" for k, v in tz_direct_mapping.items()])
    trigger = f".*({tz_reg_list}|{tz_direct_reg_list})时间.*"
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

        if not is_admin(message.member.id):
            return MessageChain.plain(f"你没有权限", quote=message.as_quote())

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


class Vote(MessageHandler):
    name = "投票"
    trigger = r"^(发起投票|查看投票|结束投票|所有投票)( .+)|^[【\[](.*?)[】\]]我投(.+)"
    white_list = False
    thread_limit = False
    readme = (
        f"使用方式:\n"
        f"发起投票 xxx\n"
        f"[xxx]我投xxx"
        f"查看投票 xxx\n"
        f"结束投票 xxx\n"
    )

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        message_content = message.message.asDisplay()
        reg_group = re.match(self.trigger, message_content).groups() # type: ignore
        if reg_group[0]:
            cmd = reg_group[0]
            vote_name = reg_group[1].strip() if reg_group[1] else ""
            if cmd == "发起投票":
                with modify_json_file(f"vote/{message.group.id}") as d:
                    if vote_name in d and d[vote_name]["open"]:
                        return MessageChain.create([Plain(f"[{vote_name}]投票已存在且开启")])
                    d[vote_name] = {
                        "creator": message.member.id,
                        "open": True,
                        "options": {},
                    }
                return MessageChain.plain(f"发起投票成功!\n输入以下内容参与投票:\n[{vote_name}]我投xxx")
            elif cmd == "所有投票":
                with modify_json_file(f"vote/{message.group.id}") as d:
                    res = "所有投票：\n" + "\n".join(d.keys())
                return MessageChain.create([Plain(res)])
            elif cmd == "查看投票":
                with modify_json_file(f"vote/{message.group.id}") as d:
                    if vote_name not in d:
                        fuzz_match = [x for x in d if vote_name in x]
                        if len(fuzz_match) == 1:
                            vote_name = fuzz_match[0]
                        else:
                            return MessageChain.create([Plain(f"[{vote_name}]投票不存在")])
                    vote_dict = d[vote_name]
                res = (
                    f"[{vote_name}]由{vote_dict['creator']}创建\n"
                    f"{'参与方式: [' + vote_name + ']我投xxx' if vote_dict['open'] else '(已关闭)'}\n"
                    f"投票选项：\n" + Vote.render_result(vote_dict["options"])
                )
                return MessageChain.create([Plain(res)])
            elif cmd == "结束投票":
                with modify_json_file(f"vote/{message.group.id}") as d:
                    if vote_name not in d:
                        return MessageChain.create([Plain(f"[{vote_name}]投票不存在")])
                    vote_dict = d[vote_name]
                    if vote_dict["creator"] != message.member.id:
                        return MessageChain.create([Plain(f"你不是[{vote_name}]投票的创建人")])
                    if not vote_dict["open"]:
                        return MessageChain.create([Plain(f"[{vote_name}]投票已结束")])
                    res = (
                        f"[{vote_name}]投票已结束\n"
                        f"最终投票选项：\n" + Vote.render_result(vote_dict["options"])
                    )
                    d[vote_name]["open"] = False
                return MessageChain.create([Plain(res)])
        else:
            vote_name = reg_group[2].strip()
            vote_option = reg_group[3].strip()
            with modify_json_file(f"vote/{message.group.id}") as d:
                if vote_name not in d or not d[vote_name]["open"]:
                    return MessageChain.create([Plain(f"[{vote_name}]投票不存在或已结束")])
                if vote_option not in d[vote_name]["options"]:
                    d[vote_name]["options"][vote_option] = []
                if str(message.member.id) in d[vote_name]["options"][vote_option]:
                    return MessageChain.create([Plain(f"你已经投过票了")])
                d[vote_name]["options"][vote_option].append(str(message.member.id))
            return MessageChain.create([Plain(f"投票成功")])
        return MessageChain.plain(f"未知错误{reg_group}")


    @staticmethod
    def render_result(options) -> str:
        res = ""
        options = {k: v for k, v in sorted(options.items(), key=lambda x: len(x[1]), reverse=True)}
        for k, v in options.items():
            res += f"【{k}】{len(v)}人\n"
            res += "    " + ", ".join(v) + "\n"
        return res


class EatWhat(MessageHandler):
    name = "吃什么"
    trigger = r"^今?天?(早上|早餐|午餐|中午|晚上|晚餐|今晚|)吃(什么|了.{1,200})$"
    white_list = False
    thread_limit = False
    readme = (
        f"随机选择吃什么\n"
        f"例如: \"早上吃什么\" 或是 \"吃什么\"\n"
        f"可以通过例如 \"吃了面包\" 或是 \"早上吃了热干面 甜豆腐脑\""
        f"\n来记录饮食，增加选项，可通过空格同时记录多个\n"
        f"重复记录会调整出现权重"
    )

    meal_dict = {
        "早上": "breakfast",
        "早餐": "breakfast",
        "中午": "lunch",
        "午餐": "lunch",
        "晚餐": "dinner",
        "今晚": "dinner",
        "晚上": "dinner",
        "": "default",
    }
    
    censor_content = [
        "屎", "粪", "尿", "史", "大便", "精液", "精", "屁", "屌", "逼", "鸡巴", "鸡鸡", "鸡儿", "垃圾"
    ]

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        message_content = message.message.asDisplay()
        meal = re.match(self.trigger, message_content).group(1) # type: ignore
        food = re.match(self.trigger, message_content).group(2) # type: ignore
        id_str = str(message.member.id)
        with modify_json_file(f"eat_what.json") as d:
            if id_str not in d:
                d[id_str] = {}
                for k, v in EatWhat.meal_dict.items():
                     d[id_str][v] = []

            if food != "什么":
                if not meal:
                    return
                foods = [x.strip() for x in food[1:].split(" ")]
                for censor in EatWhat.censor_content:
                    if censor in foods:
                        # return MessageChain.create([message.as_quote(), Plain(f"你{meal}吃{censor}?")])
                        return MessageChain.create([message.as_quote(), Plain(f"已成功记史")])

                d[id_str][EatWhat.meal_dict[meal]] += foods
                food_str = "、".join(foods)
                return MessageChain.create([message.as_quote(), Plain(f"成功记录{meal}吃了{food_str}")])
            else:
                all_food = []
                if meal:
                    all_food = [
                        *d[id_str][EatWhat.meal_dict[meal]],
                        *d[id_str]["default"],
                        *d["default"][EatWhat.meal_dict[meal]],
                        *d["default"]["default"],
                    ]
                else:
                    all_food = [
                        *d[id_str]["breakfast"],
                        *d[id_str]["lunch"],
                        *d[id_str]["dinner"],
                        *d[id_str]["default"],
                        *d["default"]["breakfast"],
                        *d["default"]["lunch"],
                        *d["default"]["dinner"],
                        *d["default"]["default"],
                    ]

                eat_food = random.sample(all_food, 2 if len(all_food) > 2 else 1)
                return MessageChain.create([message.as_quote(), Plain(f"{meal}吃{'或者'.join(eat_food)}")])


class UpdatePersonalInfo(MessageHandler):
    name = "更新群聊个人信息"
    trigger = r"^\.nick (.*)$"
    white_list = False
    thread_limit = False
    readme = "更新群聊个人信息，包括昵称、所在地等\n格式：.nick 昵称|所在地\n例如：.nick BKN|北京"

    """
    {
        "id": 0,
        "nickname": "",
        "place": "",  
    }
    """
    async def ret(self, message: MessagePack) -> MessageChain:
        info = message.message.asDisplay()[5:].strip().split("|")
        if len(info) < 2:
            return MessageChain.create([Plain("格式错误")])
        nickname = info[0]
        place = info[1] if len(info) > 1 else ""
        member_id = message.member.id
        if is_admin(message.member.id) and len(info) >= 4:
            member_id = info[2]
        
        if message.group.id not in USER_INFO:
            USER_INFO[str(message.group.id)] = {}

        USER_INFO[str(message.group.id)][str(member_id)] = {
            "id": member_id,
            "nickname": nickname,
            "place": place,
        }

        json.dump(USER_INFO, open("data/user_info.json", "w"), indent=2, ensure_ascii=False)
        return MessageChain.create([Plain("成功更新个人信息")])
