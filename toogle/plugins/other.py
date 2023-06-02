import io
import pickle
import random

import PIL.Image

from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack
from toogle.nonebot2_adapter import bot_send_message
from toogle.plugins.others.steam import source_server_info
from toogle.sql import SQLConnection
from toogle.utils import is_admin
from toogle.configs import config
import toogle.plugins.others.racehorse as race_horse
import toogle.plugins.others.csgo as CSGO

try:
    JOKING_HAZARD_GAME_DATA = pickle.load(open("data/joking_hazard.pkl", "rb"))
except Exception as e:
    JOKING_HAZARD_GAME_DATA = {}

class RaceHorse(MessageHandler):
    name = "模拟赛马"
    trigger = r"^\.racehorse"
    thread_limit = True
    readme = "赛马"

    async def ret(self, message: MessagePack) -> MessageChain:
        if not is_admin(message.member.id):
            return MessageChain.plain("无权限")
        
        race, horse = race_horse.init_race()
        for msg in race_horse.do_race(race, horse, sleep_interval=10):
            if isinstance(msg, str):
                await bot_send_message(message.group.id, MessageChain.plain(msg))
            elif isinstance(msg, bytes):
                await bot_send_message(message.group.id, MessageChain.create([Image(bytes=msg)]))

        return MessageChain.plain("比赛结束")


class JokingHazard(MessageHandler):
    name = "Joking Hazard"
    trigger = r"^\.jokinghazard"
    thread_limit = True
    readme = "氰化欢乐秀桌游 随机卡片"

    async def ret(self, message: MessagePack) -> MessageChain:
        if not JOKING_HAZARD_GAME_DATA:
            return MessageChain.plain("无数据")
        
        # byte pic data
        if random.random() <= 0.8:
            start_two = random.sample(JOKING_HAZARD_GAME_DATA["normal"], 2)
            final_card = random.choice(JOKING_HAZARD_GAME_DATA["red"])
            random.shuffle(start_two)
            cards = start_two + [final_card]
        else:
            cards = random.sample(JOKING_HAZARD_GAME_DATA["normal"], 3)
            random.shuffle(cards)

        pics = [PIL.Image.open(io.BytesIO(x)) for x in cards]
        total_width, total_height = sum([x.width for x in pics]), max([x.height for x in pics])
        combined_pic = PIL.Image.new("RGB", (total_width, total_height))
        x_offset = 0
        for pic in pics:
            combined_pic.paste(pic, (x_offset, 0))
            x_offset += pic.width
        io_buf = io.BytesIO()
        combined_pic.save(io_buf, format="PNG")
        return MessageChain.create([Image(bytes=io_buf.getvalue())])


class RandomAlbum(MessageHandler):
    name = "随机专辑"
    trigger = r"^随机专辑$"
    thread_limit = True
    readme = "随机专辑 来自人生不可不听的1001张专辑"

    async def ret(self, message: MessagePack) -> MessageChain:
        path = "data/albums.pkl"
        try:
            pics = pickle.load(open(path, "rb"))
        except Exception as e:
            return MessageChain.plain("无数据", quote=message.as_quote())
        pic = random.choice(pics)
        return MessageChain.create([Image(bytes=pic)])


class CSGOBuff(MessageHandler):
    name = "CSGO Buff饰品查询"
    trigger = r"^\.csgo\s"
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

        try:
            weapon_id = int(search_content)
            res_pic = CSGO.get_weapon_detail(weapon_id, **other_param)
            return MessageChain.create([Image(bytes=res_pic)])
        except Exception as e:
            weapon_id = 0

        res_raw = CSGO.get_buff(search=search_content, **extra_param)

        if len(res_raw) <= 0:
            return MessageChain.plain("无搜索结果")
        elif len(res_raw) == 1:
            res_pic = CSGO.get_weapon_detail(res_raw[0][3], **other_param)
            return MessageChain.create([Image(bytes=res_pic)])
        else:
            res_pic = CSGO.compose_weapon_list(res_raw)
            return MessageChain.create([Image(bytes=res_pic)])


class CSGORandomCase(MessageHandler):
    name = "CSGO开箱"
    trigger = r"^\.betcs\s"
    thread_limit = True
    readme = "CSGO开箱模拟"
    interval = 3600

    async def ret(self, message: MessagePack) -> MessageChain:
        search_content = message.message.asDisplay()[6:].strip()
        try:
            open_num = int(search_content.split()[-1])
            if open_num > 10:
                return MessageChain.create([message.as_quote(), Plain("最多一次开10个箱子")], no_interval=True)
            search_content = ' '.join(search_content.split()[:-1])
        except Exception as e:
            open_num = 1
        case_search = CSGO.search_case(search_content)

        if len(case_search) <= 0:
            return MessageChain.create([message.as_quote(), Plain("未搜索到相关箱子")], no_interval=True)
        elif len(case_search) > 1:
            return MessageChain.create([message.as_quote(), Plain("搜索到多个箱子：\n" + "\n".join([x[1] for x in case_search]))], no_interval=True)

        case_info = CSGO.get_case(case_search[0][0])

        if open_num == 1:
            item_result = CSGO.random_weapon(case_info)

            item_inventory = SQLConnection.get_user_data(message.member.id).get("csgo_inventory", [])
            item_inventory.append(item_result)
            SQLConnection.update_user_data(message.member.id, {"csgo_inventory": item_inventory})

            res_pic = CSGO.open_case_animation(item_result, case_info)
            return MessageChain.create([message.as_quote(), Image(bytes=res_pic)])

        weapons = [CSGO.random_weapon(case_info) for _ in range(open_num)]
        # text, pic_url, grade, weapon_id
        render_list = [[
            f"{x['name']}\n磨损: {x['wear']:.6f} 模板: {x['template_index']}\n价格: ¥{x['min_price']} - ¥{x['max_price']}",
            x['pic'],
            x['rarity'],
            x['item_id'],
        ] for x in weapons]

        res_pic = CSGO.compose_weapon_list(render_list)
        return MessageChain.create([message.as_quote(), Image(bytes=res_pic)])


class ToogleCSServer(MessageHandler):
    name = "CS服务器相关"
    trigger = r"^\.cs(\s|$)"
    thread_limit = True
    readme = "CS服务器相关"

    async def ret(self, message: MessagePack) -> MessageChain:
        content = message.message.asDisplay()[3:].strip()
        if content.startswith("regist"):
            content = content[6:].strip()
            if not content.startswith("STEAM_") and len(content.split(':')[-1]) != 8:
                return MessageChain.plain(f"请输入正确的Steam2 ID\n可在https://steamdb.info/calculator/查询")
            SQLConnection.update_user_data(message.member.id, {'steam2id': content})
            return MessageChain.plain(f"已绑定Steam2 ID: {content}")


        elif content.startswith("status"):
            text = source_server_info(config.get("CSGO_SERVER_HOST"), int(config.get("CSGO_SERVER_PORT") or 27015))
            return MessageChain.plain(text)

        elif content.startswith("inventory"):
            item_inventory = SQLConnection.get_user_data(message.member.id).get("csgo_inventory", [])
            if not item_inventory:
                return MessageChain.plain("你还没有库存", quote=message.as_quote())
            render_list = [[
                f"{x['name']}\n磨损: {x['wear']:.6f} 模板: {x['template_index']}\n价格: ¥{x['min_price']} - ¥{x['max_price']}",
                x['pic'],
                x['rarity'],
                x['item_id'],
            ] for x in item_inventory]
            res_pic = CSGO.compose_weapon_list(render_list)
            return MessageChain.create([message.as_quote(), Image(bytes=res_pic)])
    
        elif content.startswith("sell"):
            content = int(content[4:].strip())
            item_inventory = SQLConnection.get_user_data(message.member.id).get("csgo_inventory", [])
            if not item_inventory:
                return MessageChain.plain("你还没有库存", quote=message.as_quote())
            if content >= len(item_inventory) or content < 0:
                return MessageChain.plain("库存序号错误", quote=message.as_quote())
            tmp_item = item_inventory[content]
            item_inventory = item_inventory[:content] + item_inventory[content + 1:]
            SQLConnection.update_user_data(message.member.id, {"csgo_inventory": item_inventory})
            return MessageChain.plain(f"已出售 {tmp_item['name']}")

        elif content.startswith("equip"):
            content = int(content[5:].strip())
            steam_id = SQLConnection.get_user_data(message.member.id).get("steam2id", None)
            if not steam_id:
                return MessageChain.plain(f"请先绑定Steam2 ID, 示例:\n.tooglecs regist #你的Steam2 ID#\n\nSteam2 ID可在https://steamdb.info/calculator/查询", quote=message.as_quote())
            item_inventory = SQLConnection.get_user_data(message.member.id).get("csgo_inventory", [])
            if not item_inventory:
                return MessageChain.plain("你还没有库存", quote=message.as_quote())
            if content >= len(item_inventory) or content < 0:
                return MessageChain.plain("库存序号错误", quote=message.as_quote())
            item = item_inventory[content]
            update_res = CSGO.update_csgo_server_data(steam_id, item['eng_name'], item['internal_name'], item['wear'], item['stattrack'], item['template_index'])
            if update_res:
                return MessageChain.plain(f"已装备 {item['name']}", quote=message.as_quote())
            else:
                return MessageChain.plain(f"装备失败", quote=message.as_quote())

        help_str = (
            f".cs regist #Steam2ID# 来绑定steam\n"
            f".cs status 服务器状态查询\n"
            f".cs inventory 来查看库存\n"
            f".cs sell #序号# 来出售库存中的武器（序号从0开始）\n"
            f".cs equip #序号# 来装备库存中的武器（序号从0开始）\n"
        )
        return MessageChain.plain(help_str, quote=message.as_quote())

