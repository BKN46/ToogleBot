import json
import random

import PIL.Image
import requests

from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack
from toogle.plugins.compose.luck import get_luck_pic, max_resize
from toogle.sql import DatetimeUtils, SQLConnection


class GetLuck(MessageHandler):
    name = "每日运势"
    trigger = r"^#luck#"
    # white_list = True
    thread_limit = True
    readme = "获取运势"

    async def ret(self, message: MessagePack) -> MessageChain:
        user = SQLConnection.get_user(message.member.id)
        # return MessageChain.create([Plain("Luck功能敏感时期暂时维护")])
        if not user or not DatetimeUtils.is_today(user[2]) or user[1] > 5:
            try:
                res = MessageChain.create([get_luck_pic(message.member)])
            except Exception as e:
                return MessageChain.create([Plain(f"获取setu出错：\n{repr(e)}")])
            SQLConnection.update_user(
                message.member.id, f"last_luck='{DatetimeUtils.get_now_time()}'"
            )
            return res
        else:
            return MessageChain.create([Plain("每天运势/老婆只能一次")])


class GetSetu(MessageHandler):
    name = "色图"
    trigger = r"^#setu#"
    white_list = True
    thread_limit = True
    readme = "获取setu,#setu#后以空格分隔tag"

    async def ret(self, message: MessagePack) -> MessageChain:
        global LAST_ST_RAW
        member = message.member
        group = message.group
        keywords = message.message.asDisplay()[6:].split(" ")
        url = "https://api.lolicon.app/setu/v2"
        params = {
            "tag": keywords,
            "r18": "r18" in keywords,
        }
        res = requests.get(url, params=params)
        LAST_ST_RAW = res.text
        res_dict = json.loads(res.text)
        # return Plain(res.text)
        if len(res_dict["data"]) > 0:
            print(res.text)
            path = "/root/repos/qqbot_graia/tmp/setu_tmp.png"
            send_pic = random.choice(res_dict["data"])
            url = send_pic["urls"]["original"].replace(
                "https://i.pixiv.cat/", "https://pixiv.runrab.workers.dev/"
            )
            im = PIL.Image.open(requests.get(url, stream=True).raw)
            max_resize(im, max_width=1000, max_height=1000).save(path)
            res = Image.fromLocalFile(path)
            return MessageChain.create([res, Plain("\nPID: " + str(send_pic["pid"]))])
        else:
            res = Plain("没搜到啊！")
            return MessageChain.create([res])
