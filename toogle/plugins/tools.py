import datetime
import io
import os
import time

import requests
import PIL.Image, PIL.ImageDraw, PIL.ImageFont
from matplotlib import pyplot as plt

from toogle.configs import config
from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack
from toogle.plugins.compose.stock import get_search, render_report
from toogle.plugins.others import baidu_index
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
        datetoday = datetime.datetime.now().strftime("%Y%m%d")
        pic_name = f"rainfall_{datetoday}.gif"
        if os.path.exists(f"data/{pic_name}"):
            return MessageChain.create([Image(path=f"data/{pic_name}")])
        else:
            for x in os.listdir("data"):
                if x.startswith("rainfall_"):
                    os.remove(f"data/{x}")

        t = int(time.time() * 1000)
        url = "https://weather.cma.cn/api/channel"
        params = {
            "id": "d3236549863e453aab0ccc4027105bad,339,92,45",
            "_": t
        }
        res = requests.get(url, params=params)
        try:
            rainfall_pic = res.json()['data'][1]['image']
        except Exception as e:
            return MessageChain.plain("获取国家气象局预报数据失败")
        
        rainfall_pic = "https://weather.cma.cn" + rainfall_pic.split("?")[0]
        pics = [
            rainfall_pic.replace("000002400", x)
            for x in ["000002400", "000004800", "000007200", "000009600", "000012000", "000014400", "000016800"]
        ]
        try:
            gif_frames = [
                Image.buffered_url_pic(x, return_PIL=True)
                for x in pics
            ]
        except Exception as e:
            if is_admin(message.member.id):
                return MessageChain.plain("\n".join(pics))
            return MessageChain.plain("获取国家气象局预报数据失败")

        img_bytes = io.BytesIO()
        gif_frames[0].save(
            img_bytes,
            format="GIF", # type: ignore
            save_all=True, # type: ignore
            append_images=gif_frames[1:], # type: ignore
            optimize=True, # type: ignore
            duration=1000, # type: ignore
            loop=0, # type: ignore
        )
        open(f"data/{pic_name}", "wb").write(img_bytes.getvalue())

        # return MessageChain.create([Image(url=x) for x in pics])
        return MessageChain([Image(bytes=img_bytes.getvalue())])
