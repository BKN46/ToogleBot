import asyncio
from curses.ascii import isalpha
import datetime
import hashlib
import io
import json
import os
import pickle
import random
import re
import time
from typing import List, Optional, Union

import PIL.Image
import bs4
import requests

from toogle import utils
from toogle.message import At, ForwardMessage, Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack
from toogle.nonebot2_adapter import bot_send_message
import toogle.plugins.others.gf2 as girlsfrontline2
from toogle.plugins.others.magnet import do_magnet_parse, do_magnet_preview, parse_size
from toogle.plugins.others.steam import source_server_info
from toogle.plugins.others import tarkov as Tarkov
from toogle.plugins.others.minecraft import MCRCON
from toogle.sql import SQLConnection
from toogle.utils import SFW_BLOOM, detect_pic_nsfw, is_admin, modify_json_file
from toogle.configs import config, proxies
import toogle.plugins.others.racehorse as race_horse
import toogle.plugins.others.csgo as CSGO
import toogle.plugins.others.baseball as baseball
import toogle.plugins.others.milkywayidle as Milkywayidle

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
                bot_send_message(message.group.id, MessageChain.plain(msg))
            elif isinstance(msg, bytes):
                bot_send_message(message.group.id, MessageChain.create([Image(bytes=msg)]))

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


class BaseballGame(MessageHandler):
    name = "模拟棒球比赛"
    trigger = r"^\.baseball|.bb 注册球员|.bb 我的球员"
    thread_limit = True
    readme = "模拟棒球"

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        message_content = message.message.asDisplay()
        if message_content == ".baseball":
            if not is_admin(message.member.id):
                return MessageChain.plain("无权限", quote=message.as_quote())
            team1 = baseball.Team(message.group.name[:5] + "队")
            with modify_json_file("baseball_players.json") as players:
                players = [v for k, v in players.items() if v['group'] == message.group.id]
                for player in players:
                    team1.add_player(baseball.Player.from_json(player['data']))
            team1.team_balance()
            team2 = baseball.Team.get_random_team()
            game = baseball.Game(team1, team2)
            
            bot_send_message(message.group.id, ForwardMessage.get_quick_forward_message([
                MessageChain.plain(f"比赛开始\n{team1.name} VS {team2.name}"),
                MessageChain.plain(f"{team1.show()}"),
                MessageChain.plain(f"{team2.show()}"),
            ]))

            msg_buffer = []
            for turn in game.game():
                if turn == 'turn':
                    msg = game.show() + "\n" + '\n'.join(game.logs)
                    msg_buffer.append(MessageChain.plain(msg))
                    game.logs.clear()
                elif turn == "round":
                    await asyncio.sleep(120)
                    # time.sleep(60)
                    bot_send_message(message.group.id, ForwardMessage.get_quick_forward_message([MessageChain.plain(game.now_turn())] + msg_buffer)) # type: ignore
                    msg_buffer.clear()
            bot_send_message(message.group.id, MessageChain.plain("比赛结束" + '\n'.join(game.logs)))
            
            # update players data
            with modify_json_file("baseball_players.json") as players:
                for player in team1.players:
                    if player.name in players:
                        players[player.name]['data'] = player.to_json()

        elif message_content.startswith(".bb 注册球员"):
            player_name = message_content[9:].strip()
            if not player_name:
                return MessageChain.plain("请输入球员名", quote=message.as_quote())
            with modify_json_file("baseball_players.json") as players:
                if player_name in players:
                    return MessageChain.plain("球员已存在")
                player = baseball.Player(player_name)
                players[player_name] = {
                    "name": player_name,
                    "user": message.member.id,
                    "group": message.group.id,
                    "data": player.to_json(),
                }
            return MessageChain.plain("球员注册成功", quote=message.as_quote())
        elif message_content.startswith(".bb 我的球员"):
            with modify_json_file("baseball_players.json") as players:
                player_list = [v for k, v in players.items() if v['user'] == message.member.id]
                if not player_list:
                    return MessageChain.plain("你还没有球员，输入「.bb 注册球员 #球员名#」来注册一个", quote=message.as_quote())
                player = baseball.Player.from_json(player_list[0]['data'])
                return MessageChain.plain(player.get_data(), quote=message.as_quote())


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


class TarkovSearch(MessageHandler):
    name = "塔科夫查询"
    trigger = r"^\.tarkov|^tk |^tkq |^tkm |^tka |^tkhelp$|^tkgoons$|^tkc |^tktb|^tkboss|^tkb|^tkreload"
    thread_limit = True
    readme = f"塔科夫查询\n"\
        f".tarkov #物品名# 查询物品\n"\
        f".tarkovpve #物品名# 查询PVE物品\n"\
        f"tk #物品名# 快速查询PVE物品\n"\
        f"tkreload 更新塔科夫数据\n"\
        f"tkq #任务名# 查询任务\n"\
        f"tka #弹药名# 查询弹药\n"\
        f"tkb #弹药名# #护甲等级# #护甲耐久# #护甲材质# 模拟弹药穿甲\n"\
        f"tkc #出售价格# #成本价# #数量# 快速利润计算\n"\
        f"tkm #地图名# 查询地图\n"\
        f"tkboss 查询全地图BOSS刷率\n"\
        f"tkhelp 相关网站\n"\
        f"tkgoons 查询三狗位置"

    async def ret(self, message: MessagePack) -> Union[MessageChain, None]:
        message_content = message.message.asDisplay()
        if message_content.startswith("tk "):
            search_content = message_content[3:].strip()
            res = Tarkov.search_item(search_content, market=True, pve=True)
            return MessageChain.plain(res)
        elif message_content.startswith("tkq "):
            search_content = message_content[4:].strip()
            res = Tarkov.search_quest(search_content)
            return MessageChain.plain(res) # type: ignore
        elif message_content.startswith("tka "):
            search_content = message_content[4:].strip()
            res = Tarkov.search_ammo(search_content)
            return MessageChain.plain(res)
        elif message_content.startswith("tkb "):
            search_content = message_content[4:].strip().split()
            if len(search_content) < 4:
                return MessageChain.plain("参数错误")
            res = Tarkov.get_tarkov_ballistic_test(' '.join(search_content[:-3]), int(search_content[-3]), int(search_content[-2]), search_content[-1])
            return MessageChain.plain(res)
        elif message_content.startswith("tktb"):
            return MessageChain.plain(Tarkov.get_tieba_main())
        elif message_content.startswith("tkc "):
            return MessageChain.plain(Tarkov.parse_calculator(message_content))
        elif message_content.startswith("tkhelp"):
            return MessageChain.plain(Tarkov.get_sites())
        elif message_content.startswith("tkboss"):
            return MessageChain.plain(Tarkov.get_tarkov_api_boss_spawn_rate())
        elif message_content.startswith("tkgoons"):
            return MessageChain.plain(Tarkov.get_tarkov_goons())
        elif message_content.startswith("tkreload"):
            Tarkov.reload_tarkov_static_data()
            return MessageChain.plain("数据已更新")
        elif message_content.startswith("tkm "):
            search_content = message_content[4:].strip()
            search_map = Tarkov.MAP_INFO.get(search_content)
            if search_map:

                return MessageChain.create([
                    # Image(url=search_map['AIPMC地图']),
                    Plain('\n'.join([f"{k}: {v}" for k, v in search_map.items()])),
                ])
            else:
                return MessageChain.plain("未找到地图信息")
        elif message_content.startswith(".tarkov"):
            search_content = message_content[7:].strip()
            if search_content.startswith("pve"):
                pve = True
                search_content = search_content[3:].strip()
            else:
                pve = False
            res = Tarkov.search_item(search_content, pve=pve)
            return MessageChain.plain(res)


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


class MinecraftRCON(MessageHandler):
    name = "Minecraft服务器RCON"
    trigger = r"^\.mc "
    thread_limit = True
    readme = "Minecraft服务器RCON命令"
    
    async def ret(self, message: MessagePack) -> MessageChain:
        content = message.message.asDisplay()[4:].strip()
        if not is_admin(message.member.id):
            return MessageChain.plain("无权限", quote=message.as_quote())
        res = MCRCON.send_single(config.get("MCRCON_HOST"), int(config.get("MCRCON_PORT") or 25575), config.get("MCRCON_PASSWORD"), content)
        return MessageChain.plain(res)


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


class MarvelSnapZone(MessageHandler):
    name = "漫威终极逆转Snap工具"
    trigger = r"^\.snap "
    thread_limit = True
    readme = "漫威终极逆转Snap工具"
    
    if os.path.exists("data/snap_cards.json"):
        cards_data = json.load(open("data/snap_cards.json", "r"))
    else:
        cards_data = []


    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        content = message.message.asDisplay()[6:].strip()
        if content.isdigit():
            deck = [int(x) for x in content]
            if sum(deck) != 12:
                return MessageChain.plain("卡牌总数应为12", quote=message.as_quote())
            res = self.calcualte_cost_jam_rate(deck)
            return MessageChain.plain(res, quote=message.as_quote())
        else:
            res = self.get_snap_card_data(content.lower())
            return MessageChain.plain(res, quote=message.as_quote())

    def calcualte_cost_jam_rate(self, seq: List[int], iters=10000):
        jam = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
        waste = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
        for _ in range(iters):
            deck = []
            for i in range(6):
                deck += [i+1 for _ in range(seq[i])]

            draw = lambda x: [deck.pop(random.randrange(len(deck))) for _ in range(x)]
            hand = draw(3)

            for rnd in range(6):
                hand += draw(1)
                play = [hand.pop(x) for x in utils.dp_backpack_algorithm(rnd + 1, hand)]
                if len(play) == 0:
                    jam[rnd + 1] += 1
                    waste[rnd + 1] += rnd + 1
                else:
                    waste[rnd + 1] += rnd + 1 - sum(play)
        
        res = "回合 / 卡手率 / 平均费用浪费\n"
        for i in range(6):
            res += f" {i+1}  / {jam[i+1] / iters:^7.2%} / {waste[i+1] / iters:^6.2f}\n"
        return res


    def get_snap_card_data(self, name: str):
        if not name:
            return "请输入卡牌名称"

        cards = []
        for card in self.cards_data:
            if name == card.get('name', '').lower() or name == card.get('originalName', '').lower():
                cards = [card]
                break
            if name in card.get('name', '').lower() or name in card.get('originalName', '').lower():
                cards.append(card)

        if not cards:
            return f"卡牌{name}不存在"
        elif len(cards) > 10:
            return f"找到了太多卡牌，请输入更精确的名称"
        elif len(cards) > 1:
            return f"你是不是要找:\n" + "\n".join([f"{x['name']} / {x['originalName']}" for x in cards])

        card = cards[0]

        zh_name = card['name']
        en_name = card['originalName'].replace(" ", "-").lower()
        cost, power = card['cost'], card['power']
        desc = re.sub('<.*?>', '', card['description'])

        url = f"https://marvelsnapzone.com/cards/{en_name}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
        }
        res = requests.get(url, headers=headers)

        bs = bs4.BeautifulSoup(res.text, "html.parser")
        
        info = {}
        for t in bs.findAll('div', {'class': 'item-name'}):
            info[t.text] = t.parent.find('div', {'class': 'item-value'}).text.strip()
            
        for t in bs.findAll('div', {'class': 'name'}):
            info[t.text] = t.parent.find('div', {'class': 'info'}).text.replace('\n',' ').strip()

        if not info:
            return f"卡牌{name}不存在"

        return (
            f"卡牌名称: {card['name']} {card['originalName']}\n"
            f"卡牌属性: {cost}费 {power}攻\n"
            f"卡牌描述: {desc}\n"
            f"卡牌来源: {info.get('Source', 'null')}\n"
            # f"卡牌发布时间: {info.get('Release Date', 'null')}\n"
            f"===============\n"
            f"统计量: {info.get('# of Games', 'null')}场/{info.get('# of Cubes', 'null')}分\n"
            # f"变种使用率: {info.get('Used if Owned', 'null')}\n"
            f"卡牌排名: {info.get('Ranking', 'null')}\n"
            f"胜率贡献值: {info.get('Total Meta Share', 'null')}\n"
            f"分数贡献值: {info.get('Total Cube Share', 'null')}\n"
            f"携带胜率: {info.get('Win Rate on Draw', 'null')}\n"
            f"使用胜率: {info.get('Win Rate on Play', 'null')}\n"
            f"携带分数贡献: {info.get('Cube Rate on Draw', 'null')}\n"
            f"使用分数贡献: {info.get('Cube Rate on Play', 'null')}\n"
        )


class ZLibDownload(MessageHandler):
    name = "电子书下载"
    trigger = r"^.zlib "
    thread_limit = True
    readme = "电子书下载，来源zlib"
    
    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        host = 'https://z-library.sk'
        content = message.message.asDisplay()[6:].strip()
        start_time = time.time()
        
        url = f'{host}/s/{content}?'
        res = requests.get(url, proxies=proxies)
        soup = bs4.BeautifulSoup(res.text, 'html.parser')
        books = soup.find('div', {'class': 'col-md-12 itemFullText'}).find('div', id='searchResultBox') # type: ignore
        search_res = []
        for book in books.findAll('div', {'class': 'book-item'}): # type: ignore
            book_info = book.find('z-bookcard')
            book_title = book_info.find('div', {'slot': 'title'}).text
            book_author = book_info.find('div', {'slot': 'author'}).text
            
            search_res.append({
                'title': book_title,
                'author': book_author,
                'size': book_info.get('filesize'),
                'format': book_info.get('extension'),
                'language': book_info.get('language'),
                'year': book_info.get('year'),
                'rating': book_info.get('rating'),
                'quality': book_info.get('quality'),
                'publisher': book_info.get('publisher'),
                'download_link': f'{host}{book_info.get("download")}'
            })
            pass
        use_time = (time.time() - start_time) * 1000
        return ForwardMessage.get_quick_forward_message([
            MessageChain.plain(f'Z-lib 搜索[{content}] 耗时{use_time:.1f}ms\n{url}'),
            *[
                MessageChain.plain((
                    f"《{x['title']}》 - {x['author']}\n"
                    f"{x['format']} {x['size']}\n"
                    f"{x['publisher']} - {x['year']}年 - {x['language']}\n"
                    f"评分：{x['rating']} 质量：{x['quality']}\n"
                    f"{x['download_link']}"
                ))
                for x in search_res
            ][:20]
        ])


class GF2DataSearch(MessageHandler):
    name = "少前2快速搜索工具"
    trigger = r"^gf2 "
    thread_limit = True
    readme = "少前2快速搜索工具，搜索全部人形/武器技能词条\n可使用>来指定顺序搜索\n可使用!来指定不包含\n最后一层过滤为翻页"

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        content = message.message.asDisplay()[4:].strip()
        if content == 'reload':
            girlsfrontline2.gf2_mcc_doll_data()
            girlsfrontline2.reload_all_data()
            return MessageChain.plain("数据已更新")

        page, page_size = 0, 20
        if len(content.split('>')) > 1 and content.split('>')[-1].strip().isdigit():
            page = int(content.split('>')[-1].strip()) - 1
            content = '>'.join(content.split('>')[:-1]).strip()

        res = girlsfrontline2.general_search(content)
        res = [
            MessageChain.plain(x) for x in res
        ]
        
        if len(res) <= 0:
            return MessageChain.plain("无搜索结果", quote=message.as_quote())

        if len(res) > page_size:
            total_page = len(res) // page_size + 1
            res = res[page * page_size: (page + 1) * page_size]
            res.append(MessageChain.plain(f"第{page + 1}页 / 共{total_page}页 \n输入 gf2 {content}>{page + 2} 来查看下一页"))

        return ForwardMessage.get_quick_forward_message(res) # type: ignore


try:
    LAW_BOOK = []
    for law_type in ['刑法', '民法典', '治安管理处罚法']:
        tmp_line = ''
        for law in open(f'data/laws/{law_type}.txt', 'r').readlines():
            if re.match(r'^第.+?条', law):
                if tmp_line:
                    LAW_BOOK.append(tmp_line.strip())
                tmp_line = f'【{law_type}】{law}'
            elif law.startswith('第'):
                continue
            else:
                tmp_line += law
        if tmp_line:
            LAW_BOOK.append(tmp_line.strip())
except:
    LAW_BOOK = []


class LawQuickSearch(MessageHandler):
    name = "中国法律速查"
    trigger = r"^law "
    thread_limit = True
    readme = "法律速查，包含刑法、民法典、治安管理处罚法"

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        content = message.message.asDisplay()[4:].strip()
        if not content:
            return MessageChain.plain("请输入搜索内容", quote=message.as_quote())
        if not LAW_BOOK:
            return MessageChain.plain("数据加载失败", quote=message.as_quote())
        res = []
        for law in LAW_BOOK:
            if content in law:
                res.append(law)
        if not res:
            return MessageChain.plain("无搜索结果", quote=message.as_quote())
        
        if len(res) > 8:
            return ForwardMessage.get_quick_forward_message([MessageChain.plain(x) for x in res])

        return MessageChain.plain('\n\n'.join(res), quote=message.as_quote())


class MilkywayidleSearch(MessageHandler):
    name = "银河奶牛放置工具"
    trigger = r"^mwi(g|l) "
    thread_limit = True
    readme = "Milkywayidle银河奶牛放置速查工具"

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        content = message.message.asDisplay()
        if content.startswith("mwig "):
            content = content[5:].strip()
            res = Milkywayidle.gold_to_money(content)
            return MessageChain.plain(res, quote=message.as_quote())
        elif content.startswith("mwil "):
            content = content[4:].strip().split(' ')
            res = Milkywayidle.get_level_info(int(content[0]), int(content[1]))
            return MessageChain.plain(res, quote=message.as_quote())


class NFSWorNot(MessageHandler):
    name = "判断色图"
    trigger = r"这个色不色|^这个不色"
    thread_limit = True
    interval = 0
    readme = "图像识别判断NSFW\n使用Open-NSFW2模型，为Keras实现Yahoo Open-NSFW\n模型为ResNet使用ImageNet 1000预训练后使用NSFW数据集finetune\nOpen-NSFW文章: https://yahooeng.tumblr.com/post/151148689421/open-sourcing-a-deep-learning-solution-for\nResNet论文: https://arxiv.org/pdf/1512.03385v1"
    price = 2

    async def ret(self, message: MessagePack) -> MessageChain:
        pics = message.message.get(Image)
        
        if not pics:
            return MessageChain.plain("没看到图", quote=message.as_quote())
        
        if message.message.asDisplay().startswith("这个不色"):
            for pic in pics:
                SFW_BLOOM.add(hashlib.md5(pic.getBytes()).hexdigest())
            return MessageChain.plain("收到", quote=message.as_quote())

        res = ""
        judge = lambda x: '不色' if x < 0.1 else '还行' if x < 0.25 else '色'
        start_time = time.time()
        safe, mod, nsfw = 0, 0, 0
        for i, pic in enumerate(pics):
            rate, repeat = detect_pic_nsfw(pic.getBytes(), output_repeat=True) # type: ignore
            if rate < 0.1:
                safe += 1
            elif rate < 0.25:
                mod += 1
            else:
                nsfw += 1
            # res += f"pic{i+1} rate: {rate} ({judge(rate)})\n"
        use_time = (time.time() - start_time) * 1000
        # res += f"{len(pics)}张图片分析耗时: {use_time:.2f}ms"
        if len(pics) == 1:
            res = judge(rate)
        else:
            res += f"{safe}张不色 " if safe > 0 else ""
            res += f"{mod}张还行 " if mod > 0 else ""
            res += f"{nsfw}张色 " if nsfw > 0 else ""
        return MessageChain.plain(res, quote=message.as_quote())


class MagnetParse(MessageHandler):
    name = "磁链内容解析"
    trigger = r"magnet:\?xt=urn:[a-z0-9]+:[a-zA-Z0-9]+"
    thread_limit = True
    interval = 3600
    readme = "尝试解析磁力链接内容"
    price = 10

    async def ret(self, message: MessagePack) -> MessageChain:
        # res = do_magnet_parse(message.message.asDisplay())
        # return MessageChain.plain(res, quote=message.as_quote())
        res = do_magnet_preview(message.message.asDisplay())
        bot_send_message(message.group.id, MessageChain.plain(f"已获取磁链，正在解析中", quote=message.as_quote()))
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
                # imgs = [Image(url=x).compress(max_height=400) for x in pics_url]
                imgs = []

            if not imgs:
                return MessageChain([
                message.as_quote(),
                Plain(f"磁链内容解析成功：\n名称: {resource_name}\n大小: {resource_size}\n文件数: {resource_count}\n预览加载失败")
                ])
            else:
                return MessageChain([
                    message.as_quote(),
                    Plain(f"磁链内容解析成功：\n名称: {resource_name}\n大小: {resource_size}\n文件数: {resource_count}\n预览:\n"),
                ] + imgs)
