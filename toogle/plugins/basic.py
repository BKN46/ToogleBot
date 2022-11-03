import random
import re
import datetime
from functools import reduce

from toogle.message_handler import MessagePack, MessageHandler
from toogle.message import MessageChain, Plain, Quote


class HelpMeSelect(MessageHandler):
    trigger = r"^[是|应该](.*还是.*)"
    readme = "随机选项"

    async def ret(self, message: MessagePack) -> MessageChain:
        match_str = re.match(self.trigger, message.message.asDisplay())
        if match_str:
            proc_str = HelpMeSelect.str_prune(match_str.group(1))
            sel_list = proc_str.split("还是")
            common_prefix = HelpMeSelect.longestCommonPrefix(sel_list)
            return MessageChain.create(
                [Quote(), Plain(random.choice(sel_list)[len(common_prefix) :])]
            )
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
    trigger = r"^骂我$"
    white_list = False
    thread_limit = False
    readme = "找喷"

    async def ret(self, message: MessagePack) -> MessageChain:
        return MessageChain.create([Plain("因为这个功能还在开发中，所以我只能先说一句你妈死了。")])
