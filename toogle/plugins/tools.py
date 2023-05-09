import requests

from toogle.configs import config
from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack
from toogle.plugins.compose.stock import get_search, render_report

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

class CSGOBuff(MessageHandler):
    name = "CSGO Buff饰品查询"
    trigger = r"^.csgo\s"
    thread_limit = True
    readme = "CSGO Buff饰品查询"

    async def ret(self, message: MessagePack) -> MessageChain:
        search_content = message.message.asDisplay()[5:].strip()
        res = CSGOBuff.get_buff(search=search_content)
        return MessageChain.plain(res)

    @staticmethod
    def get_buff(**params):
        url = 'https://buff.163.com/api/market/goods'

        params.update({
            "game": "csgo",
            "page_num": 1,
            "sort_by": "price.asc",
        })
        params = params

        try:
            cookies = open("data/buff_cookie", "r").read().strip()
        except Exception as e:
            return "未配置buff cookie"

        headers = {
            "cookie": cookies
        }
        try:
            res = requests.get(url, params=params, headers=headers, proxies=proxies).json()
        except Exception as e:
            return "请求失败"
        if res["code"] != 'OK':
            raise Exception("请求失败")

        items = res["data"]["items"]

        res_text = "\n".join([f"¥{item['sell_min_price']:<10} {item['name']}" for item in items])
        return "搜索结果:\n" + res_text
