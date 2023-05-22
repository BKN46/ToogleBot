import io
import os
import json
import random
import threading

import requests
import PIL.Image
from matplotlib import pyplot as plt

from toogle.configs import config
from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack
from toogle.plugins.compose.stock import get_search, render_report
from toogle.utils import draw_pic_text, pic_max_resize, text2img

proxies = {
    'http': config.get('REQUEST_PROXY_HTTP', ''),
    'https': config.get('REQUEST_PROXY_HTTPS', ''),
}

thread_lock = threading.Lock()

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
            "quality": "normal",
        }
        other_param = {}
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
            elif text.startswith("最大磨损") and len(text) > 4:
                other_param['max_paint_wear'] = float(text[4:])
            elif text.startswith("价格降序") and len(text) > 2:
                extra_param['sort_by'] = "price.desc"
            elif "刀" in text or "匕首" in text:
                extra_param['quality'] = "unusual"
                return False
            elif "手套" in text:
                extra_param['quality'] = "unusual"
                return False
            else:
                return False
            return True
        
        search_content = " ".join([x for x in search_content.split() if not add_param(x)])
        res_raw = CSGOBuff.get_buff(search=search_content, **extra_param)

        if len(res_raw) <= 0:
            return MessageChain.plain("无搜索结果")
        elif len(res_raw) == 1:
            res_pic = CSGOBuff.get_weapon_detail(res_raw[0][3], **other_param)
            return MessageChain.create([Image(bytes=res_pic)])
        else:
            res_pic = CSGOBuff.compose_weapon_list(res_raw)
            return MessageChain.create([Image(bytes=res_pic)])

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

        res = [
            (
                f"{item['name']}\n买: ¥{item['sell_min_price']:<10} 卖: ¥{item['buy_max_price']:<10}",
                item['goods_info']['icon_url'],
                item['goods_info']['info']['tags']['rarity']['internal_name'],
                item['id'],
            )
            for item in items
            if float(item['sell_min_price']) > 0
        ]
        # text, pic_url, grade, id
        return res
    
    @staticmethod
    def get_weapon_grade_color(grade_name):
        grade_color = {
            "contraband": "#e4ae39",
            "ancient": "#eb4b4b",
            "legendary": "#d32ce6",
            "mythical": "#8847ff",
            "rare": "#4b69ff",
            "uncommon": "#5e98d9",
            "common": "#b0c3d9",
        }
        for k, v in grade_color.items():
            if k in grade_name:
                return v
        return "#b0c3d9"

    @staticmethod
    def compose_weapon_list(res_list, word_size=20):
        res_pic = PIL.Image.new(
            "RGBA",
            (600, 180 * len(res_list) + 20),
            (255, 255, 255),
        )
        for index, weapon in enumerate(res_list):
            text, pic_url, grade, weapon_id = weapon
            pic = PIL.Image.open(requests.get(pic_url, stream=True).raw)
            generate_pic = draw_pic_text(
                pic,
                text,
                pic_size=(220, 220),
                padding=(20, 0),
                max_size=(600, 200),
                word_padding=(0, 60),
                word_size=word_size,
                byte_mode=False,
            )
            bar = PIL.Image.new(
                "RGBA",
                (10, 120),
                CSGOBuff.get_weapon_grade_color(grade),
            )
            generate_pic.paste(bar, (7, 50)) # type: ignore
            res_pic.paste(generate_pic, (0, index * 180)) # type: ignore
        img_bytes = io.BytesIO()
        res_pic.save(img_bytes, format="PNG")
        return img_bytes.getvalue()

    @staticmethod
    def get_weapon_detail(weapon_id, max_paint_wear=0):
        # price history
        url = f"https://buff.163.com/api/market/goods/price_history/buff"
        params = {
            "game": "csgo",
            "goods_id": weapon_id,
            "currency": "CNY",
            "days": 30,
            "buff_price_type": 2,
        }
        headers = {
            "cookie": open("data/buff_cookie", "r").read().strip()
        }

        res = requests.get(url, params=params, headers=headers, proxies=proxies)
        price_history = res.json()['data']['price_history']
        plt.plot([x[1] for x in price_history])
        pic_buf = io.BytesIO()
        plt.savefig(pic_buf, format='png')
        price_history_graph = pic_max_resize(
            PIL.Image.open(pic_buf), 800, 800
        )
        plt.close()

        # get first trade
        url = f"https://buff.163.com/api/market/goods/sell_order"
        params = {
            "game": "csgo",
            "goods_id": weapon_id,
            "page_num": 1,
            "sort_by": "price.asc",
            "allow_tradable_cooldown": 1,
        }
        if max_paint_wear:
            params['max_paintwear'] = max_paint_wear
        res = requests.get(url, params=params, headers=headers, proxies=proxies).json()
        first_sell = res['data']['items'][0]
        weapon_pic_url = first_sell['img_src']
        weapon_name = res['data']['goods_infos'][str(weapon_id)]['name']
        weapon_price = first_sell['price']
        weapon_wear = first_sell['asset_info']['paintwear']

        res_pic = PIL.Image.new(
            "RGBA",
            (800, 1000),
            (255, 255, 255),
        )
        res_pic.paste(price_history_graph, (10, 400))

        text_pic = text2img(
            f"{weapon_name}\n¥{weapon_price}\n磨损: {weapon_wear}",
            max_size=(800, 100),
        )
        res_pic.paste(PIL.Image.open(io.BytesIO(text_pic)), (10, 10))

        weapon_pic = pic_max_resize(
            PIL.Image.open(requests.get(weapon_pic_url, stream=True).raw), 750, 300
        )
        res_pic.paste(weapon_pic, (20, 150), weapon_pic)

        img_bytes = io.BytesIO()
        res_pic.save(img_bytes, format="PNG")
        return img_bytes.getvalue()


class CSGORandomCase(MessageHandler):
    name = "CSGO开箱"
    trigger = r"^.betcs\s"
    thread_limit = True
    readme = "CSGO开箱模拟"
    interval = 120

    async def ret(self, message: MessagePack) -> MessageChain:
        search_content = message.message.asDisplay()[6:].strip()
        try:
            open_num = int(search_content.split()[-1])
            if open_num > 10:
                return MessageChain.plain("最多一次开10个箱子")
            search_content = ' '.join(search_content.split()[:-1])
        except Exception as e:
            open_num = 1
        case_search = CSGORandomCase.search_case(search_content)

        if len(case_search) <= 0:
            return MessageChain.plain("未搜索到相关箱子")
        elif len(case_search) > 1:
            return MessageChain.plain("搜索到多个箱子：\n" + "\n".join([x[1] for x in case_search]))

        case_info = CSGORandomCase.get_case(case_search[0][0])
        weapons = [CSGORandomCase.random_weapon(case_info) for _ in range(open_num)]

        # text, pic_url, grade, weapon_id
        render_list = [[
            f"{x['name']}\n磨损: {x['wear']:.6f} 模板: {x['template_index']}\n价格: ¥{x['min_price']} - ¥{x['max_price']}",
            x['pic'],
            x['rarity'],
            x['item_id'],
        ] for x in weapons]

        res_pic = CSGOBuff.compose_weapon_list(render_list)
        return MessageChain.create([Image(bytes=res_pic)])


    @staticmethod
    def get_case(case_name):
        thread_lock.acquire()
        cache_path = "data/csgo_case_data.json"
        if os.path.isfile(cache_path):
            with open(cache_path, "r") as f:
                case_infos = json.load(f)
            if case_name not in case_infos:
                case_info = CSGORandomCase.get_case_info(case_name)
                case_infos[case_name] = case_info
                with open(cache_path, "w") as f:
                    json.dump(case_infos, f, ensure_ascii=False, indent=2)
        else:
            case_info = CSGORandomCase.get_case_info(case_name)
            case_infos = {}
            case_infos[case_name] = case_info
            with open(cache_path, "w") as f:
                json.dump(case_infos, f, ensure_ascii=False, indent=2)
        thread_lock.release()
        return case_infos[case_name]

    @staticmethod
    def search_case(name):
        cache_path = "data/csgo_case_name.json"
        if os.path.isfile(cache_path):
            with open(cache_path, "r") as f:
                case_infos = json.load(f)
            if name in case_infos:
                return case_infos[name]
        else:
            case_infos = {}

        url = 'https://buff.163.com/api/market/goods'

        params = {
            "game": "csgo",
            "page_num": 1,
            "search": name,
            "category": "csgo_type_weaponcase",
        }

        try:
            cookies = open("data/buff_cookie", "r").read().strip()
        except Exception as e:
            raise Exception("未配置buff cookie")

        headers = {
            "cookie": cookies
        }

        try:
            res = requests.get(url, params=params, headers=headers, proxies=proxies)
            res = res.json()
        except Exception as e:
            raise Exception("请求失败")
        if res["code"] != 'OK':
            raise Exception("请求失败")

        items = res["data"]["items"]
        res =  [(x['market_hash_name'], x['name']) for x in items]
    
        case_infos[name] = res
        thread_lock.acquire()
        with open(cache_path, "w") as f:
            json.dump(case_infos, f, ensure_ascii=False, indent=2)
        thread_lock.release()

        return res

    @staticmethod
    def get_case_info(case_name, unusual_only=False):
        url = 'https://buff.163.com/api/market/csgo_container'

        params = {
            "container": case_name,
            "is_container": 1,
            "container_type": "weaponcase",
        }

        if unusual_only:
            params.update({"unusual_only": 1})

        try:
            cookies = open("data/buff_cookie", "r").read().strip()
        except Exception as e:
            raise Exception("未配置buff cookie")

        headers = {
            "cookie": cookies
        }

        try:
            res = requests.get(url, params=params, headers=headers, proxies=proxies)
            res = res.json()
        except Exception as e:
            raise Exception("请求失败")
        if res["code"] != 'OK':
            raise Exception("请求失败")
        
        unusual_content = []

        if unusual_only:
            return res["data"]["items"]
        elif res["data"]["has_unusual"]:
            unusual_content = CSGORandomCase.get_case_info(case_name, unusual_only=True)

        case_content, now_rarity = [], None
        raw_content = unusual_content + res["data"]["items"]
        for item in raw_content:
            rarity = item["goods"]["tags"]["rarity"]["internal_name"]
            item_dict = {
                "name": item["localized_name"],
                "item_id": item["goods_id"],
                "pic": item["goods"]["original_icon_url"],
                "min_price": item["min_price"],
                "max_price": item["max_price"],
                "rarity": rarity,
            }
            if not now_rarity or rarity != now_rarity:
                now_rarity = rarity
                case_content.append([item_dict])
            else:
                case_content[-1].append(item_dict)

        return case_content

    @staticmethod
    def random_weapon(case_content):
        rarity_probability = [
            0.0026,
            0.0064,
            0.032,
            0.1598,
            0.7992,
        ]
        cobblestone_rarity_probability = [
            0.00026,
            0.00128,
            0.0064,
            0.032,
            0.1598,
            0.7992,
        ]
        wear_probability = [
            0.03,
            0.24,
            0.33,
            0.24,
            0.16,
        ]
        wear_content = [
            0,
            0.07,
            0.15,
            0.38,
            0.45,
            1,
        ]
        wear_name = [
            "崭新出厂",
            "略有磨损",
            "久经沙场",
            "破损不堪",
            "战痕累累",
        ]

        if len(case_content) == 6:
            rarity_probability = cobblestone_rarity_probability
        total_probability = sum(rarity_probability[:len(case_content)])
        random_num = random.random() * total_probability
        for i, content in enumerate(case_content):
            random_num -= rarity_probability[i]
            if random_num <= 0:
                item_result = random.choice(content)
                break
        else:
            item_result = random.choice(case_content[len(case_content) - 1])

        template_index = random.randint(0, 999)
        random_num = random.random() * sum(wear_probability)
        for i, wear in enumerate(wear_probability):
            random_num -= wear
            if random_num <= 0:
                wear_result = random.random() * (wear_content[i + 1] - wear_content[i]) + wear_content[i]
                break
        else:
            raise Exception("随机失败")
        
        stattrack = random.random() < 0.1

        return {
            **item_result,
            "name": f"{item_result['name']} {'（StatTrak™）' if stattrack else ''}| ({wear_name[i]})",
            "template_index": template_index,
            "wear": wear_result,
        }

