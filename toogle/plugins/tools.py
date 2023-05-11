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
    interval = 30

    async def ret(self, message: MessagePack) -> MessageChain:
        search_content = message.message.asDisplay()[5:].strip()

        extra_param = {
            "page_num": 1,
            "sort_by": "price.asc",
        }
        def add_param(text: str):
            if text == "普通":
                extra_param['quality'] = "normal"
            elif text == "普通刀":
                extra_param['quality'] = "unusual"
            elif text == "暗金":
                extra_param['quality'] = "strange"
            elif text == "暗金刀":
                extra_param['quality'] = "unusual_strange"
            elif text == "纪念品":
                extra_param['quality'] = "tournament"
            elif text == "隐秘":
                extra_param['rarity'] = "ancient_weapon"
            elif text == "保密":
                extra_param['rarity'] = "legendary_weapon"
            elif text == "受限":
                extra_param['rarity'] = "mythical_weapon"
            elif text.startswith("pg") and len(text) > 2:
                extra_param['page_num'] = int(text[2:])
            elif text.startswith("最低") and len(text) > 2:
                extra_param['min_price'] = int(text[2:])
            elif text.startswith("最高") and len(text) > 2:
                extra_param['max_price'] = int(text[2:])
            elif text.startswith("价格降序") and len(text) > 2:
                extra_param['sort_by'] = "price.desc"
            else:
                return False
            return True
        
        search_content = " ".join([x for x in search_content.split() if not add_param(x)])
        res = CSGOBuff.get_buff(search=search_content, **extra_param)
        return MessageChain.plain(res)

    @staticmethod
    def get_buff(**params):
        url = 'https://buff.163.com/api/market/goods'

        params.update({
            "game": "csgo",
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
