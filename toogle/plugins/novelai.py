from toogle.message import At, Image, Member, MessageChain, Plain, Quote
from toogle.message_handler import MessageHandler, MessagePack
from toogle.plugins.pic.novelai import (get_ai_generate, get_balance,
                                        get_base64_encode)
from toogle.sql import DatetimeUtils, SQLConnection


class GetAICompose(MessageHandler):
    trigger = r"^.ai\s"
    thread_limit = True
    # white_list = True
    readme = "获取NovelAI生成图片，注意输入文本必须英文"

    async def ret(self, message: MessagePack) -> MessageChain:
        # return MessageChain.create([Plain(f"NovelAI接口变化，功能暂时维护")])
        user = SQLConnection.get_user(message.member.id)
        content_str = (
            message.message.asDisplay()[3:]
            .replace("\n", "")
            .replace("[图片]", "")
            .strip()
        )
        if content_str == "balance":
            balance = get_balance()
            return MessageChain.create(
                [Plain(f"大黄狗在 novelai.net 余额还剩 {balance} anlas\n折合{int(balance/5)}张图")]
            )
        if all(
            [
                user,
                DatetimeUtils.is_today(user[2]), # type: ignore
                not user[1] > 5 # type: ignore
            ]
        ):
            return MessageChain.create([Plain(f"每天运势/老婆/NTR/AI生成只能一次")])
        try:
            images = message.message.get(Image)
            if images:
                image_byte = images[0].getBytes() # type: ignore
                # return MessageChain.create([Plain(content_str)])
                jpeg_byte = get_ai_generate(content_str, image_byte=image_byte)
            else:
                jpeg_byte = get_ai_generate(content_str)
            res_message = MessageChain.create([Image(bytes=jpeg_byte)])
            SQLConnection.update_user(
                message.member.id, f"last_luck='{DatetimeUtils.get_now_time()}'"
            )
            return res_message
        except Exception as e:
            return MessageChain.create([Plain(f"生成过程中好像出现了问题:\n{repr(e)}")])
