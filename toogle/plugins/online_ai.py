from typing import Optional
from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack, WaitCommandHandler
from toogle.nonebot2_adapter import bot_send_message
from toogle.plugins.compose.novelai import get_ai_generate, get_balance
import toogle.economy as economy
import toogle.plugins.compose.midjourney as midjourney
from toogle.sql import DatetimeUtils, SQLConnection


class GetAICompose(MessageHandler):
    name = "AI画图"
    trigger = r"^\.ai\s"
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


class GetMidjourney(MessageHandler):
    name = "Midjourney生成图片"
    trigger = r"^\.midjourney\s"
    thread_limit = True
    price = 30
    interval = 300
    readme = "获取Midjourney生成图片"

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        content = message.message.asDisplay()[11:].strip()
        
        if content == "balance":
            remain = midjourney.get_balance()
            return MessageChain.create([Plain(f"剩余API次数: {remain['remaining_amount']}")])

        bot_send_message(
            message,
            MessageChain.create([message.as_quote(), Plain("收到，正在生成中，预计10-60s")])
        )

        try:
            generate_res = midjourney.generate_image(content)
            image_id = generate_res["image_id"]
            pic_url = generate_res["image_url"]
        except Exception as e:
            return MessageChain.create([message.as_quote(), Plain(f"生成过程出现问题:\n{repr(e)}\n{generate_res}")]) # type: ignore

        bot_send_message(
            message,
            MessageChain.create([
                message.as_quote(),
                Image(url=pic_url),
                Plain(f"图片ID: {image_id}\n可输入操作: [重新生成] [放大1/2/3/4] [变化1/2/3/4]")
            ])
        )
        multi_select = True
        
        single_variations = "|".join(midjourney.VARIATIONS.keys())
        
        re_str = f"^(.+\n)?(重新生成|放大[1-4]|变化[1-4]|{single_variations})$"
        while True:
            waiter = WaitCommandHandler(message.group.id, message.member.id, re_str, timeout=120)
            waiter_res = await waiter.run()
            if waiter_res:
                if economy.get_balance(message.member.id) < self.price:
                    return MessageChain.create([Plain("GB余额不足")])
                instruct = waiter_res.message.asDisplay().strip()
                if '\n' in instruct:
                    image_id = instruct.split('\n')[0]
                    instruct = instruct.split('\n')[1]
                if instruct.startswith("放大"):
                    if not multi_select:
                        bot_send_message(message, MessageChain.create([Plain("非法操作")]))
                        continue
                    try:
                        generate_res = midjourney.upsample_image(image_id, int(instruct[-1]))
                        image_id = generate_res["image_id"]
                        pic_url = generate_res["image_url"]
                        multi_select = False
                    except Exception as e:
                        return MessageChain.create([message.as_quote(), Plain(f"生成过程出现问题:\n{repr(e)}")])
                elif instruct.startswith("重新生成"):
                    if not multi_select:
                        bot_send_message(message, MessageChain.create([message.as_quote(), Plain("非法操作")]))
                        continue
                    try:
                        generate_res = midjourney.reroll_image(image_id)
                        image_id = generate_res["image_id"]
                        pic_url = generate_res["image_url"]
                        multi_select = True
                    except Exception as e:
                        return MessageChain.create([message.as_quote(), Plain(f"生成过程出现问题:\n{repr(e)}")])
                elif instruct.startswith("变化"):
                    if not multi_select:
                        bot_send_message(message, MessageChain.create([message.as_quote(), Plain("非法操作")]))
                        continue
                    try:
                        generate_res = midjourney.varient_image(image_id, int(instruct[-1]))
                        image_id = generate_res["image_id"]
                        pic_url = generate_res["image_url"]
                        multi_select = True
                    except Exception as e:
                        return MessageChain.create([message.as_quote(), Plain(f"生成过程出现问题:\n{repr(e)}")])
                else:
                    if multi_select:
                        bot_send_message(message, MessageChain.create([message.as_quote(), Plain("非法操作")]))
                        continue
                    try:
                        generate_res = midjourney.varient_image(image_id, variation=instruct)
                        image_id = generate_res["image_id"]
                        pic_url = generate_res["image_url"]
                        multi_select = True
                    except Exception as e:
                        return MessageChain.create([Plain(f"生成过程出现问题:\n{repr(e)}")])
                instructs = f"[重新生成] [放大1/2/3/4] [变化1/2/3/4]" if multi_select else " ".join([f"[{x}]" for x in midjourney.VARIATIONS.keys()])
                bot_send_message(
                    waiter_res,
                    MessageChain.create([
                        waiter_res.as_quote(),
                        Image(url=pic_url),
                        Plain(f"图片ID: {image_id}\n可输入操作: {instructs}")
                    ])
                )
                economy.take_balance(message.member.id, self.price)
            else:
                # bot_send_message(message, MessageChain.create([message.as_quote(), Plain("退出Midjourney模式")]))
                break
