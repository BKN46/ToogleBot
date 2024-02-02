import json
import random

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import requests

from toogle.message import Image, Member, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack, get_user_name
from toogle.plugins.remake.remake import get_remake
from toogle.sql import DatetimeUtils, SQLConnection


class GetRemake(MessageHandler):
    name = "科学remake"
    trigger = r"^/remake"
    # white_list = True
    readme = "随机remake，数据来源自世界银行"

    async def ret(self, message: MessagePack) -> MessageChain:
        # return MessageChain.create([Plain("由于敏感词封禁问题，remake暂时维护升级，未来会转换为图片形式")])
        user = SQLConnection.get_user(message.member.id)
        if message.message.asDisplay().split()[-1].startswith("topd"):
            res = "Remake世界排行:\n"
            res += "\n".join(
                [
                    f"$$$ 第{i+1}名 {x[3]}分 $$$ {x[2]} {x[4]}{x[7]}{x[8]}\n种子: #{x[0]}"
                    for i, x in enumerate(SQLConnection.get_top_remake()) # type: ignore
                ]
            )
            return MessageChain.create([Image.text_image(res)])
        elif message.message.asDisplay().split()[-1].startswith("top"):
            res = "Remake世界排行:\n"
            res += "\n".join(
                [
                    f"第{i+1}名 {x[3]}分 {x[2]} {x[4]}{x[7]}{x[8]}"
                    for i, x in enumerate(SQLConnection.get_top_remake()) # type: ignore
                ]
            )
            return MessageChain.create([Image.text_image(res)])
        elif message.message.asDisplay().split()[-1].startswith("lowd"):
            res = "Remake倒数世界排行:\n"
            res += "\n".join(
                [
                    f"$$$ 第{i+1}名 {x[3]}分 $$$ {x[2]} {x[4]}{x[7]}{x[8]}\n种子: #{x[0]}"
                    for i, x in enumerate(SQLConnection.get_low_remake()) # type: ignore
                ]
            )
            return MessageChain.create([Image.text_image(res)])
        elif message.message.asDisplay().split()[-1].startswith("low"):
            res = "Remake倒数世界排行:\n"
            res += "\n".join(
                [
                    f"第{i+1}名 {x[3]}分 {x[2]} {x[4]}{x[7]}{x[8]}"
                    for i, x in enumerate(SQLConnection.get_low_remake()) # type: ignore
                ]
            )
            return MessageChain.create([Image.text_image(res)])
        elif message.message.asDisplay().split()[-1].startswith("#"):
            seed = message.message.asDisplay().split("#")[-1]
            try:
                res = get_remake(message.member.name, seed=seed)
            except Exception as e:
                res = get_remake("", seed=seed)
            return MessageChain.create([Image.text_image(res[0])])
        elif (
            not user
            or not user[4]
            or not DatetimeUtils.is_today(user[4])
            or user[1] > 5
        ):
            try:
                res = get_remake(get_user_name(message))
                SQLConnection.insert(
                    "remake_data",
                    {
                        **res[1],
                        "group": str(message.group.id),
                        "user_id": str(message.member.id),
                    },
                )
            except Exception as e:
                res = get_remake(str(message.member.id))
                SQLConnection.insert(
                    "remake_data", {**res[1], "user_id": str(message.member.id)}
                )
                # res = [str(res[1])]
            SQLConnection.update_user(
                message.member.id, f"last_remake='{DatetimeUtils.get_now_time()}'"
            )
            return MessageChain.create([Image.text_image(res[0])])
        else:
            return MessageChain.create([Plain("一天只能remake一次～")])
