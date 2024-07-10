import datetime
import io
import os
import json
import random
import threading
import time

import requests
import PIL.Image
from mysql import connector
from matplotlib import pyplot as plt

from toogle.configs import config, proxies
from toogle.message import Image
from toogle.utils import draw_pic_text, pic_max_resize, text2img
from toogle.sql import SQLConnection


thread_lock = threading.Lock()


def get_buff(**params):
    url = "https://buff.163.com/api/market/goods"

    params.update(
        {
            "game": "csgo",
        }
    )
    params = params

    try:
        cookies = open("data/buff_cookie", "r").read().strip()
    except Exception as e:
        return "未配置buff cookie"

    headers = {"cookie": cookies}
    try:
        res = requests.get(url, params=params, headers=headers, proxies=proxies).json()
    except Exception as e:
        return "请求失败"
    if res["code"] != "OK":
        raise Exception("请求失败")

    items = res["data"]["items"]

    res = [
        (
            f"{item['name']}\n买: ¥{item['sell_min_price']:<10} 卖: ¥{item['buy_max_price']:<10}\nID: {item['id']}",
            item["goods_info"]["icon_url"],
            item["goods_info"]["info"]["tags"]["rarity"]["internal_name"],
            item["id"],
        )
        for item in items
        if float(item["sell_min_price"]) > 0
    ]
    # text, pic_url, grade, id
    return res


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
            get_weapon_grade_color(grade),
        )
        generate_pic.paste(bar, (7, 50))  # type: ignore
        res_pic.paste(generate_pic, (0, index * 180))  # type: ignore
    img_bytes = io.BytesIO()
    res_pic.save(img_bytes, format="PNG")
    return img_bytes.getvalue()


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
    headers = {"cookie": open("data/buff_cookie", "r").read().strip()}

    res = requests.get(url, params=params, headers=headers, proxies=proxies)
    price_history = res.json()["data"]["price_history"]
    plt.figure(figsize=(8, 3))
    plt.plot([x[1] for x in price_history])
    pic_buf = io.BytesIO()
    plt.savefig(pic_buf, format="png")
    price_history_graph = pic_max_resize(PIL.Image.open(pic_buf), 800, 300)
    plt.close()

    # get order history
    url = f"https://buff.163.com/api/market/goods/bill_order"
    params = {
        "game": "csgo",
        "goods_id": weapon_id,
    }
    res = requests.get(url, params=params, headers=headers, proxies=proxies).json()

    order_history = [
        f"{datetime.datetime.fromtimestamp(int(x['buyer_pay_time'])).strftime('%Y-%m-%d')}  ¥{x['price']}"
        for x in res["data"]["items"]
    ]

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
        params["max_paintwear"] = max_paint_wear
    res = requests.get(url, params=params, headers=headers, proxies=proxies).json()
    first_sell = res["data"]["items"][0]
    weapon_pic_url = first_sell["img_src"]
    weapon_name = res["data"]["goods_infos"][str(weapon_id)]["name"]
    weapon_price = first_sell["price"]
    weapon_wear = first_sell["asset_info"]["paintwear"]

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
        PIL.Image.open(requests.get(weapon_pic_url, stream=True).raw),
        750,
        300,
        hard_limit=True,
    )
    weapon_margin = (
        int((800 - 40 - weapon_pic.size[0]) / 2),
        int((300 - weapon_pic.size[1]) / 2),
    )
    res_pic.paste(
        weapon_pic, (20 + weapon_margin[0], 120 + weapon_margin[1]), weapon_pic
    )

    text_pic = text2img(
        f"成交记录:\n" + "\n".join(order_history),
        max_size=(800, 800),
    )
    res_pic.paste(PIL.Image.open(io.BytesIO(text_pic)), (50, 700))

    img_bytes = io.BytesIO()
    res_pic.save(img_bytes, format="PNG")
    return img_bytes.getvalue()


def get_case(case_name):
    thread_lock.acquire()
    cache_path = "data/csgo_case_data.json"
    if os.path.isfile(cache_path):
        with open(cache_path, "r") as f:
            case_infos = json.load(f)
        if case_name not in case_infos:
            case_info = get_case_info(case_name)
            case_infos[case_name] = case_info
            with open(cache_path, "w") as f:
                json.dump(case_infos, f, ensure_ascii=False, indent=2)
    else:
        case_info = get_case_info(case_name)
        case_infos = {}
        case_infos[case_name] = case_info
        with open(cache_path, "w") as f:
            json.dump(case_infos, f, ensure_ascii=False, indent=2)
    thread_lock.release()
    return case_infos[case_name]


def search_case(name):
    cache_path = "data/csgo_case_name.json"
    if os.path.isfile(cache_path):
        with open(cache_path, "r") as f:
            case_infos = json.load(f)
        if name in case_infos:
            return case_infos[name]
    else:
        case_infos = {}

    url = "https://buff.163.com/api/market/goods"

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

    headers = {"cookie": cookies}

    try:
        res = requests.get(url, params=params, headers=headers, proxies=proxies)
        res = res.json()
    except Exception as e:
        raise Exception("请求失败")
    if res["code"] != "OK":
        raise Exception("请求失败")

    items = res["data"]["items"]
    res = [(x["market_hash_name"], x["name"]) for x in items]

    case_infos[name] = res
    thread_lock.acquire()
    with open(cache_path, "w") as f:
        json.dump(case_infos, f, ensure_ascii=False, indent=2)
    thread_lock.release()

    return res


def get_case_info(case_name, unusual_only=False):
    url = "https://buff.163.com/api/market/csgo_container"

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

    headers = {"cookie": cookies}

    try:
        res = requests.get(url, params=params, headers=headers, proxies=proxies)
        res = res.json()
    except Exception as e:
        raise Exception("请求失败")
    if res["code"] != "OK":
        raise Exception("请求失败")

    unusual_content = []

    if unusual_only:
        return res["data"]["items"]
    elif res["data"]["has_unusual"]:
        unusual_content = get_case_info(case_name, unusual_only=True)

    case_content, now_rarity = [], None
    raw_content = unusual_content + res["data"]["items"]
    for item in raw_content:
        rarity = item["goods"]["tags"]["rarity"]["internal_name"]
        item_dict = {
            "name": item["localized_name"],
            "eng_name": item["goods"]["market_hash_name"],
            "item_id": item["goods_id"],
            "internal_name": item["goods"]["tags"]["weapon"]["internal_name"] if 'weapon' in item["goods"]["tags"] else "other",
            "pic": item["goods"]["original_icon_url"],
            "min_price": item["min_price"],
            "max_price": item["max_price"],
            "rarity": rarity,
            "category": item["goods"]["tags"]["category"]["internal_name"],
        }
        if not now_rarity or rarity != now_rarity:
            now_rarity = rarity
            case_content.append([item_dict])
        else:
            case_content[-1].append(item_dict)

    return case_content


def random_weapon(case_content, no_unusal=False):
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
    total_probability = sum(rarity_probability[: len(case_content)])
    random_num = random.random() * total_probability
    for i, content in enumerate(case_content):
        random_num -= rarity_probability[i]
        if random_num <= 0:
            item_result = random.choice(content)
            break
    else:
        item_result = random.choice(case_content[len(case_content) - 1])

    if "印花" in item_result["name"]:
        template_index = 0
        wear_result = 0
        stattrack = False
        final_name = f"{item_result['name']}"
    else:
        template_index = random.randint(0, 999)
        random_num = random.random() * sum(wear_probability)
        for i, wear in enumerate(wear_probability):
            random_num -= wear
            if random_num <= 0:
                wear_result = (
                    random.random() * (wear_content[i + 1] - wear_content[i])
                    + wear_content[i]
                )
                break
        else:
            raise Exception("随机失败")

        stattrack = random.random() < 0.1
        final_name = f"{item_result['name']} {'（StatTrak™）' if stattrack else ''}| ({wear_name[i]})"

    if no_unusal and (
        "knife" in item_result["category"] or "glove" in item_result["category"]
    ):
        return random_weapon(case_content, no_unusal=True)

    return {
        **item_result,
        "stattrack": 1 if stattrack else 0,
        "name": final_name,
        "template_index": template_index,
        "wear": wear_result,
    }


def open_case_animation(item_result, case_content, debug=False):
    frame_buff = [random_weapon(case_content, no_unusal=True) for _ in range(8)]

    gif_frames = []
    init_offset = random.randint(0, 60)
    offset = init_offset
    momentum, deacc, is_end = 70, 0.4, False
    icon_width = 150
    out_start_time = time.time()
    while momentum > 0:
        start_time = time.time()

        frame_pic = PIL.Image.new("RGBA", (750, 200), (255, 255, 255))
        center_bar = PIL.Image.new("RGBA", (4, 180), (120, 120, 120))
        for i in range(0, 7):
            weapon_pic = PIL.Image.new("RGBA", (icon_width, 170), (255, 255, 255))
            weapon_icon = Image.buffered_url_pic(frame_buff[i]["pic"], return_PIL=True)
            weapon_icon = pic_max_resize(weapon_icon, icon_width, 150)  # type: ignore
            weapon_pic.paste(weapon_icon, (0, 0), weapon_icon)
            weapon_bar = PIL.Image.new(
                "RGBA",
                (150, 20),
                get_weapon_grade_color(frame_buff[i]["rarity"]),
            )
            weapon_pic.paste(weapon_bar, (0, icon_width))
            frame_pic.paste(weapon_pic, (i * icon_width - round(offset), 0))
        if offset > icon_width:
            del_weapon = int(offset / icon_width)
            frame_buff = frame_buff[del_weapon:] + [
                random_weapon(case_content, no_unusal=True) for _ in range(del_weapon)
            ]
            if (
                momentum / 2 * (momentum / deacc) - init_offset <= icon_width * 3
                and not is_end
            ):
                frame_buff[5] = item_result
                is_end = True
            offset -= icon_width * del_weapon
        frame_pic.paste(center_bar, (373, 10))

        gif_frames.append(frame_pic)
        offset += momentum
        momentum -= deacc
        if debug:
            print(momentum, (time.time() - start_time) * 1000)

    # print(item_result)
    final_pic = compose_weapon_list(
        [
            [
                f"{x['name']}\n磨损: {x['wear']:.6f} 模板: {x['template_index']}\n价格: ¥{x['min_price']} - ¥{x['max_price']}",
                x["pic"],
                x["rarity"],
                x["item_id"],
            ]
            for x in [item_result]
        ]
    )
    final_pic = PIL.Image.open(io.BytesIO(final_pic))
    result_pic = PIL.Image.new("RGBA", (750, 200), (255, 255, 255))
    result_pic.paste(final_pic, (0, 0))

    img_bytes = io.BytesIO()
    gif_frames[0].save(
        img_bytes,
        format="GIF",
        save_all=True,
        append_images=gif_frames[1:]
        + [gif_frames[-1] for _ in range(10)]
        + [result_pic for _ in range(150)],
        optimize=True,
        duration=40,
        # loop=1,
    )
    if debug:
        print("use time: ", (time.time() - out_start_time) * 1000, "ms")
    return img_bytes.getvalue()


def get_weapon_skin_id(weapon_eng, update=False):
    skin_name = weapon_eng.split("|")[1].split("(")[0].strip()

    if update:
        uri = "https://raw.githubusercontent.com/kgns/weapons/master/addons/sourcemod/configs/weapons/weapons_english.cfg"
        raw_data = requests.get(uri, proxies=proxies).text.split("\n")[2:]
        skin_data = {}
        for index, line in enumerate(raw_data):
            if index % 5 == 0 and index < len(raw_data) - 4:
                skin_data[line.split('"')[1]] = {
                    "index": raw_data[index + 2].split('"')[-2],
                    "weapons": raw_data[index + 3].split('"')[-2],
                }
        open("data/csgo_weapon_skin.json", "w").write(
            json.dumps(skin_data, indent=2, ensure_ascii=False)
        )
    else:
        skin_data = json.loads(open("data/csgo_weapon_skin.json").read())

    if skin_name in skin_data:
        return skin_data[skin_name]["index"]
    else:
        return 0


def update_csgo_server_data(
    steam_id, weapon_eng, weapon_code, wear, stattrack, template
):
    connection = connector.connect(
        host=config.get("CSGO_MYSQL_HOST"),
        user=config.get("CSGO_MYSQL_USER"),
        passwd=config.get("CSGO_MYSQL_PASSWD"),
        database="ToogleCS",
    )
    cursor = connection.cursor()
    if "knife" in weapon_code:
        weapon_name = "knife"
    else:
        weapon_name = "".join(weapon_code.split("weapon_")[1:])
    skin_index = get_weapon_skin_id(weapon_eng, update=False)

    command = (f"SELECT * FROM weapons WHERE steamid LIKE '{steam_id}'")
    cursor.execute(command)
    user = cursor.fetchall()
    if user:
        command = (
            f"UPDATE weapons SET"
            f"`{weapon_name}`='{skin_index}',"
            f"`{weapon_name}_float`='{wear}',"
            f"`{weapon_name}_trak`='{1 if stattrack else 0}',"
            f"`{weapon_name}_seed`='{template}'"
            f"WHERE steamid LIKE '%{steam_id}'"
        )
    else:
        command = (
            f"INSERT INTO weapons (steamid, {weapon_name}, {weapon_name}_float, {weapon_name}_trak, {weapon_name}_seed)"
            f"VALUES ('{steam_id}', {skin_index}, {wear}, {stattrack}, {template})"
        )
    try:
        cursor.execute(command)
        connection.commit()
        return True
    except Exception as e:
        connection.rollback()
        return False


class Weapon:
    def __init__(
        self,
        item_id,
        pic_url,
        name,
        rarity,
        category,
        wear=0,
        template=0,
        stattrack=False,
    ) -> None:
        self.item_id = item_id
        self.pic_url = pic_url
        self.name = name
        self.rarity = rarity
        self.category = category

    @staticmethod
    def from_id(item_id):
        pass
