import datetime
import io
import json
import pickle
import random
import time

import PIL.Image
import requests

from toogle.message import At, Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack
from toogle.nonebot2_adapter import bot_send_message
from toogle.plugins.others.magnet import do_magnet_parse, do_magnet_preview, parse_size
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


class Diablo4Tracker(MessageHandler):
    name = "D4 event tracker"
    trigger = r"^d4boss(\snoreply|\ssub|\sunsub|)$"
    thread_limit = True
    readme = "暗黑破坏神4世界boss跟踪\n输入d4boss来获取目前世界boss情况\n输入d4boss sub来订阅世界boss提醒\n输入d4boss unsub来取消订阅世界boss提醒"

    sub_json_path = "data/d4boss.json"

    async def ret(self, message: MessagePack) -> MessageChain:
        content = message.message.asDisplay()[6:].strip()
        no_reply = False
        if content.startswith("noreply"):
            no_reply = True
        elif content.startswith("sub"):
            self.update_save(sub_group=message.group.id, sub_id=message.member.id)
            return MessageChain.plain("订阅成功")
        elif content.startswith("unsub"):
            self.update_save(sub_group=message.group.id, sub_id=message.member.id, sub=False)
            return MessageChain.plain("取消订阅成功")

        save_data = self.read_save()
        if str(message.group.id) in save_data['sub_list']:
            at_list = [At(x) for x in save_data['sub_list'][str(message.group.id)]]
        else:
            at_list = []

        try:
            res = requests.get("https://diablo4.life/api/trackers/worldBoss/reportHistory?name=&limit=25").json()['reports']
        except Exception as e:
            if no_reply:
                return MessageChain([])
            return MessageChain.plain("请求失败", quote=message.as_quote())

        unconfirmed_dict = {}

        for item in res:
            now_time = int(time.time() * 1000)
            left_time = ((item['spawnTime'] - now_time) / 1000 / 60)
            if left_time > 0 and left_time < 60 and 'status' in item and item['status'] == 'validated' and not self.time_near(item['spawnTime'], save_data['last_boss_time']):
                self.update_save(boss_time=item['spawnTime'])
                spawn_time_text = datetime.datetime.fromtimestamp(item['spawnTime'] / 1000).strftime("%Y-%m-%d %H:%M:%S")
                alert_text = (
                    f"注意世界Boss即将于{spawn_time_text}刷新\n"
                    f"BOSS：{item['name']}\n位于：{item['location']}\n"
                    f"[此消息可通过 d4boss sub 指令来订阅]\n"
                    f"[或是通过「d4boss unsub」来取消订阅]\n\n"
                )
                return MessageChain.create([Plain(alert_text)] + at_list)
            elif left_time > 0 and left_time < 60 and 'status' not in item:
                spawn_time = item['spawnTime']
                report_user = item['user']['uid']
                if spawn_time not in unconfirmed_dict:
                    unconfirmed_dict[spawn_time] = [report_user]
                else:
                    if report_user not in unconfirmed_dict[spawn_time]:
                        unconfirmed_dict[spawn_time].append(report_user)

        if unconfirmed_dict:
            sorted_unconfirmed = list(sorted(unconfirmed_dict.items(), key=lambda x: len(x[1]), reverse=True))
            if len(sorted_unconfirmed[0][1]) >=5 and not self.time_near(sorted_unconfirmed[0][0], save_data['last_boss_time']):
                self.update_save(boss_time=sorted_unconfirmed[0][0])
                spawn_time_text = datetime.datetime.fromtimestamp(sorted_unconfirmed[0][0] / 1000).strftime("%Y-%m-%d %H:%M:%S")
                alert_text = (
                    f"注意世界Boss即将于{spawn_time_text}刷新\n"
                    f"BOSS：{item['name']}\n位于：{item['location']}\n" # type: ignore
                    f"[此消息可通过「d4boss sub」指令来订阅]\n"
                    f"[或是通过「d4boss unsub」来取消订阅]\n\n"
                )
                return MessageChain.create([Plain(alert_text)] + at_list)
        
        if no_reply:
            return MessageChain([])

        try:
            last_time = requests.get("https://diablo4.life/api/trackers/worldBoss/list").json()['lastEvent']['time']
        except Exception as e:
            if no_reply:
                return MessageChain([])
            return MessageChain.plain("请求失败", quote=message.as_quote())
        spawn_time_text = datetime.datetime.fromtimestamp(last_time / 1000).strftime("%Y-%m-%d %H:%M:%S")
        next_time = datetime.datetime.fromtimestamp(last_time / 1000 + 60 * 15 + 3600 * 5).strftime("%Y-%m-%d %H:%M:%S")
        next_time_2 = datetime.datetime.fromtimestamp(last_time / 1000 + 60 * 15 + 3600 * 8).strftime("%Y-%m-%d %H:%M:%S")
        return MessageChain.plain((
            f"暂无世界Boss刷新信息\n最近一次刷新为 {spawn_time_text}\n"
            f"下次刷新可能在 {next_time} - {next_time_2}\n"
            f"可回复「d4boss sub」来订阅boss刷新信息"
        ), quote=message.as_quote())


    def read_save(self):
        try:
            with open(self.sub_json_path, "r") as f:
                return json.load(f)
        except Exception as e:
            content = {
                "last_boss_time": 0,
                "sub_list": {}
            }
            json.dump(content, open(self.sub_json_path, "w"), indent=4, ensure_ascii=False)
            return content


    def update_save(self, sub_group=None, sub_id=None, sub=True, boss_time=None):
        save_data = self.read_save()
        sub_group = str(sub_group)
        if sub_id:
            if sub_group not in save_data['sub_list'] and sub:
                save_data['sub_list'][sub_group] = [sub_id]
            elif sub and sub_id not in save_data['sub_list'][sub_group]:
                save_data['sub_list'][sub_group].append(sub_id)
            elif not sub and sub_group in save_data['sub_list'] and sub_id in save_data['sub_list'][sub_group]:
                save_data['sub_list'][sub_group].remove(sub_id)
        if boss_time:
            save_data['last_boss_time'] = boss_time
        json.dump(save_data, open(self.sub_json_path, "w"), indent=4, ensure_ascii=False)

    
    def time_near(self, time1, time2):
        return abs(time1 - time2) / 1000 / 60 < 5


class MagnetParse(MessageHandler):
    name = "磁链内容解析"
    trigger = r"magnet:\?xt=urn:[a-z0-9]+:[a-zA-Z0-9]+"
    thread_limit = True
    interval = 3600
    readme = "尝试解析磁力链接内容"

    async def ret(self, message: MessagePack) -> MessageChain:
        # res = do_magnet_parse(message.message.asDisplay())
        # return MessageChain.plain(res, quote=message.as_quote())
        res = do_magnet_preview(message.message.asDisplay())
        await bot_send_message(message.group.id, MessageChain.plain(f"已获取磁链，正在解析中", quote=message.as_quote()))
        if isinstance(res, str):
            return MessageChain.plain(res, quote=message.as_quote())
        else:
            resource_name = res['name']
            resource_size = parse_size(res['size'])
            resource_count = res['count']
            if not res['screenshots']:
                return MessageChain.plain(f"{resource_name}({resource_count}文件 {resource_size})无预览", quote=message.as_quote())

            pics_url = [x['screenshot'] for x in res['screenshots']]

            # image concat
            try:
                pics = [PIL.Image.open(requests.get(x, stream=True).raw) for x in pics_url]
                total_width, total_height = max([x.width for x in pics]), sum([x.height for x in pics])
                combined_pic = PIL.Image.new("RGB", (total_width, total_height))
                y_offset = 0
                for pic in pics:
                    combined_pic.paste(pic, (0, y_offset))
                    y_offset += pic.height
                io_buf = io.BytesIO()
                combined_pic.save(io_buf, format="PNG")
                imgs = [Image(bytes=io_buf.getvalue())]
            except Exception as e:
                imgs = [Image(url=x).compress(max_height=400) for x in pics_url]

            res_message = MessageChain([
                message.as_quote(),
                Plain(f"磁链内容解析成功：\n名称: {resource_name}\n大小: {resource_size}\n文件数: {resource_count}\n预览:\n"),
            ] + imgs)
            return res_message
