import base64
import time
from typing import Literal, Optional, Union

import requests
from toogle.configs import config
from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack, WaitCommandHandler
from toogle.mirai_extend import send_group_file
from toogle.nonebot2_adapter import bot_send_message
from toogle.plugins.compose.novelai import get_ai_generate, get_balance
import toogle.economy as economy
import toogle.plugins.compose.midjourney as midjourney
from toogle.sql import DatetimeUtils, SQLConnection
from toogle.utils import convert_mp4_to_gif


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
                        bot_send_message(message, MessageChain.plain("收到，请稍等", quote=waiter_res.as_quote()))
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
                        bot_send_message(message, MessageChain.plain("收到，请稍等", quote=waiter_res.as_quote()))
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
                        bot_send_message(message, MessageChain.plain("收到，请稍等", quote=waiter_res.as_quote()))
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
                        bot_send_message(message, MessageChain.plain("收到，请稍等", quote=waiter_res.as_quote()))
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


class GetDoubaoCompose(MessageHandler):
    name = "豆包AI生成图片/视频"
    trigger = r"^/doubao(\s|v\s)"
    thread_limit = True
    price = 50
    interval = 300
    readme = "获取豆包AI生成图片/视频"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config['DOUBAO_API_KEY']}"
    }

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        content = message.message.asDisplay()
        if content.startswith('/doubao '):
            return MessageChain.create([Image(bytes=self.generate_image(content[8:].strip()))])

        image_mode="reference_image"

        content_str = '\n'.join([x.text for x in message.message.get(Plain)])
        if content_str.startswith('f'):
            image_mode = "first_frame"
            content_str = content_str[1:].strip()
        
        ratio = "16:9"
        if content_str.startswith('v'):
            ratio = "9:16"
            content_str = content_str[1:].strip()
            
        resolution = "480p"
        if content_str.startswith('h'):
            resolution = "720p"
            content_str = content_str[1:].strip()

        image = message.message.get(Image)
        if image:
            image = image[0]
        else:
            image = None
        
        start_time = time.time()
        video_url, token_usage = self.generate_video(
            content_str=content_str,
            image=image,
            image_mode=image_mode,
            resolution=resolution,
            ratio=ratio,
        )
        use_time = time.time() - start_time
        video_name = video_url.split("/")[-1].split("?")[0]
        video_bytes = requests.get(video_url).content
        gif_bytes = convert_mp4_to_gif(video_bytes, fps=24, loop=0, frame_step=2, max_width=480)

        return MessageChain.create([
            message.as_quote(),
            Image(bytes=gif_bytes),
            Plain(f"用时{use_time:.2f}秒\n本次生成使用Token: {token_usage}")
        ])
        # return MessageChain.plain(f"用时{use_time:.2f}秒\n本次生成使用Token: {token_usage}", quote=message.as_quote())


    @staticmethod
    def generate_image(content_str: str, module="doubao-seedream-4-0-250828") -> bytes:
        url = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
        data = {
            "model": module,
            "prompt": content_str,
            "size": "832x1248",
            "sequential_image_generation": "disabled",
            "stream": False,
            "response_format": "b64_json",
            "watermark": False
        }
        res = requests.post(url, json=data, headers=GetDoubaoCompose.headers)
        try:
            b64data = res.json()['data'][0]['b64_json']
        except Exception as e:
            raise Exception(f"{res.text}")
        return base64.b64decode(b64data)

    @staticmethod
    def generate_video(
        content_str: str,
        image: Optional[Image]=None,
        image_mode="reference_image",
        timeout = 1200,
        resolution = '480p',
        ratio = '16:9',
        duration = 7,
        fps = 24,
        ):
        # image_mode = reference_image, first_frame
        url = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
        parameters = {
            'rs': resolution,
            'rt': ratio,
            'dur': duration,
            'fps': fps,
            'wm': 'false',
        }
        parameters_str = ' '.join([f'--{k} {v}' for k, v in parameters.items()])
        if not image:
            data = {
                "model": "doubao-seedance-1-0-lite-t2v-250428",
                "content": [
                    {
                        "type": "text",
                        "text": f"{content_str} {parameters_str}"
                    }
                ]
            }
        else:
            pic_height, pic_width = image.get_size()
            parameters['rt'] = '21:9'
            if pic_width / pic_height < 21 / 9:
                parameters['rt'] = '16:9'
            elif pic_width / pic_height < 16 / 9:
                parameters['rt'] = '4:3'
            elif pic_width / pic_height < 4 / 3:
                parameters['rt'] = '1:1'
            elif pic_width / pic_height < 1 / 1:
                parameters['rt'] = '3:4'
            elif pic_width / pic_height < 3 / 4:
                parameters['rt'] = '9:16'
            data = {
                "model": "doubao-seedance-1-0-lite-i2v-250428",
                "content": [
                    {
                        "type": "text",
                        "text": f"{content_str} {parameters_str}"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image.getBase64()}"
                        },
                        "role": image_mode
                    }
                ]
            }
        res = requests.post(url, json=data, headers=GetDoubaoCompose.headers)
        try:
            pic_id = res.json()['id']
        except Exception as e:
            raise Exception(f"{res.text}")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            status_res = requests.get(
                f"https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{pic_id}",
                headers=GetDoubaoCompose.headers
            )
            try:
                status_json = status_res.json()
            except Exception as e:
                raise Exception(f"{status_res.text}")
            if status_json['status'] == 'succeeded':
                video_url = status_json['content']['video_url']
                token_usage = status_json['usage']['total_tokens']
                return video_url, token_usage
            elif status_json['status'] == 'failed':
                raise Exception(f"生成失败: {status_json}")
            else:
                time.sleep(5)
        raise Exception("生成超时")

