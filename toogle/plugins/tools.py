import datetime
import io

import requests
import PIL.Image, PIL.ImageDraw, PIL.ImageFont
from matplotlib import pyplot as plt

from toogle.configs import config
from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack
from toogle.plugins.compose.stock import get_search, render_report
from toogle.plugins.others import baidu_index

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
            return MessageChain.create([message.as_quote(), Plain(res)])
