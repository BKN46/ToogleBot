import json
import random

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import requests

from toogle.configs import config, interval_limiter
from toogle.economy import has_balance
from toogle.message import Image, Member, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack, get_user_name
from toogle.plugins.gpt import GetOpenAIConversation
from toogle.plugins.online_ai import GetDoubaoCompose
from toogle.plugins.remake.remake import get_remake
from toogle.sql import DatetimeUtils, SQLConnection
from toogle.utils import is_admin


class GetRemake(MessageHandler):
    name = "科学remake"
    trigger = r"^/remake"
    # white_list = True
    readme = "随机remake，数据来源自世界银行"
    price = 10
    
    prompt_setting = '请根据remake结果，生成一段remake人生小故事，以第三人称视角，主要考虑收入在国内的对应水平，尽量贴切写实，不要涉及具体数字、不要提预期寿命，字数在200字左右。'
    draw_prompt_setting = '请根据人生描述，生成一个给绘图AI使用的绘图提示词，描述主人公在30岁时的照片，风格写实。'

    async def ret(self, message: MessagePack) -> MessageChain:
        # return MessageChain.create([Plain("由于敏感词封禁问题，remake暂时维护升级，未来会转换为图片形式")])
        msg = message.message.asDisplay()
        user = SQLConnection.get_user(message.member.id)
        if msg.split()[-1].startswith("topd"):
            res = "Remake世界排行:\n"
            res += "\n".join(
                [
                    f"$$$ 第{i+1}名 {x[3]}分 $$$ {x[2]} {x[4]}{x[7]}{x[8]}\n种子: #{x[0]}"
                    for i, x in enumerate(SQLConnection.get_top_remake()) # type: ignore
                ]
            )
            return MessageChain.create([Image.text_image(res)])
        elif msg.split()[-1].startswith("top"):
            res = "Remake世界排行:\n"
            res += "\n".join(
                [
                    f"第{i+1}名 {float(x[3]):.3f}分 {x[2]} {x[4]}{x[7]}{x[8]}"
                    for i, x in enumerate(SQLConnection.get_top_remake()) # type: ignore
                ]
            )
            return MessageChain.create([Image.text_image(res)])
        elif msg.split()[-1].startswith("lowd"):
            res = "Remake倒数世界排行:\n"
            res += "\n".join(
                [
                    f"$$$ 第{i+1}名 {x[3]}分 $$$ {x[2]} {x[4]}{x[7]}{x[8]}\n种子: #{x[0]}"
                    for i, x in enumerate(SQLConnection.get_low_remake()) # type: ignore
                ]
            )
            return MessageChain.create([Image.text_image(res)])
        elif msg.split()[-1].startswith("low"):
            res = "Remake倒数世界排行:\n"
            res += "\n".join(
                [
                    f"第{i+1}名 {float(x[3]):.3f}分 {x[2]} {x[4]}{x[7]}{x[8]}"
                    for i, x in enumerate(SQLConnection.get_low_remake()) # type: ignore
                ]
            )
            return MessageChain.create([Image.text_image(res)])
        elif msg.split()[-1].startswith("#"):
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
            story_res = GetOpenAIConversation.get_chat(
                res[0],
                settings=self.prompt_setting,
                model=config.get("GPTModelLarge", ""),
                url=config.get("GPTUrl", ""),
            )
            text_res = '\n人生故事: ' + story_res

            try:
                basic_info = f"{res[1]['nation']}{res[1]['race']}{res[1]['sexual']}"
                draw_prompt = GetOpenAIConversation.get_chat(
                    f'{basic_info}\n{story_res}',
                    settings=self.draw_prompt_setting,
                    model=config.get("GPTModelLarge", ""),
                    url=config.get("GPTUrl", ""),
                )
                pic_bytes = GetDoubaoCompose.generate_image(
                    f"{draw_prompt}",
                )
                return MessageChain.create([message.as_quote(), Image.text_image(res[0]), Image(bytes=pic_bytes), Plain(text_res)])
            except Exception as e:
                return MessageChain.create([message.as_quote(), Image.text_image(res[0]), Plain(text_res), Plain(f"\nremake图片生成失败: {repr(e)}")])
        else:
            return MessageChain.create([message.as_quote(), Plain("一天只能remake一次～")], no_charge=True)
