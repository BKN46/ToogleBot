import datetime
import io
import os
import re
import time
from typing import Union

import requests
import PIL.Image, PIL.ImageDraw, PIL.ImageFont
from matplotlib import pyplot as plt

from toogle.configs import config
from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack
from toogle.plugins.compose.stock import get_search, render_report
from toogle.plugins.others import baidu_index
from toogle.plugins.others.weather import get_rainfall_graph
from toogle.utils import is_admin

proxies = {
    'http': config.get('REQUEST_PROXY_HTTP', ''),
    'https': config.get('REQUEST_PROXY_HTTPS', ''),
}


class AStock(MessageHandler):
    name = "A股详情查询"
    trigger = r"^财报\s"
    thread_limit = True
    readme = "A股财报查询"

    async def ret(self, message: MessagePack) -> MessageChain:
        search_content = message.message.asDisplay()[2:].strip()
        search_list = get_search(search_content)
        if len(search_list) == 0:
            return MessageChain.create([Plain("没有搜到对应 A股/港股/美股 上市公司")])
        elif len(search_list) > 1:
            res_text = f"存在多个匹配，请精确搜索:\n" + f"\n".join(
                [f"{x[2]} {x[1]}" for x in search_list]
            )
            return MessageChain.create([Plain(res_text)])
        else:
            img_bytes = render_report(search_list[0][0])
            return MessageChain.create([Image(bytes=img_bytes)])


class BaiduIndex(MessageHandler):
    name = "百度指数"
    trigger = r"^百度指数\s"
    thread_limit = True
    interval = 600
    readme = "百度指数查询" 

    async def ret(self, message: MessagePack) -> MessageChain:
        search_content = message.message.asDisplay()[4:].strip()
        res = baidu_index.search_index(search_content)
        if isinstance(res, bytes):
            return MessageChain.create([message.as_quote(), Image(bytes=res)])
        else:
            return MessageChain.create([message.as_quote(), Plain(str(res))])


class GetRainfallWeatherGraph(MessageHandler):
    name = "全国降水天气预告图"
    trigger = r"^全国降水$"
    thread_limit = True
    interval = 600
    readme = "全国降水天气预告图" 

    async def ret(self, message: MessagePack) -> MessageChain:
        rainfall = get_rainfall_graph()
        if isinstance(rainfall, bytes):
            return MessageChain.create([Image(bytes=rainfall)])
        else:
            return MessageChain.create([Plain(str(rainfall))])


class HealthCalculator(MessageHandler):
    name = "健康计算器"
    trigger = r"^(\d{1,3}岁)?(男|m|M|女|f|F)?(\d{1,3}cm)(\d{1,3}kg)$"
    thread_limit = True
    interval = 600
    readme = "健康计算器" 

    async def ret(self, message: MessagePack) -> Union[MessageChain, None]:
        message_content = message.message.asDisplay()
        re_match = re.match(self.trigger, message_content)
        if re_match:
            age, sex, height, weight = re_match.groups()
            age = int(age.replace('岁', '')) if age else 0
            sex_is_male = True if sex in ['男', 'm', 'M'] else False
            height = int(height[:-2])
            weight = int(weight[:-2])
        else:
            return

        res_str = ""

        bmi = weight / (height / 100) ** 2
        status = "偏瘦" if bmi < 18.5 else "正常" if bmi < 24 else "偏胖" if bmi < 28 else "肥胖"
        res_str += f"体重指数(BMI): {bmi:.3f} ({status})\n"

        if age:
            max_heartbeat_rate = 205.8 - 0.685 * age
            anaerobic_heartbeat_rate = max_heartbeat_rate * 0.85
            aerobic_heartbeat_rate = max_heartbeat_rate * 0.7
            res_str += f"最大心率: {max_heartbeat_rate:.1f}BPM\n"
            res_str += f"无氧运动心率: {anaerobic_heartbeat_rate:.1f}BPM\n"
            res_str += f"有氧运动心率: {aerobic_heartbeat_rate:.1f}BPM\n"

        if age and sex:
            bmr = 10 * weight + 6.25 * height - 5 * age + (5 if sex_is_male else 161)
            res_str += f"基础代谢率(BMR): {bmr:.2f}千卡/天\n"

            est_bodyfat_rate = 1.2 * bmi + 0.23 * age - 5.4 - (10.8 if sex_is_male else 0)
            res_str += f"估算体脂率: {est_bodyfat_rate:.2f}%\n"

        return MessageChain.plain(res_str)
