import asyncio
import base64
import tempfile
import time
from pathlib import Path
from typing import List, Optional
from urllib.parse import unquote, urlparse

import requests
from configs import config
from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack, WaitCommandHandler
from toogle.adapter import bot_send_message, bot_upload_group_file
from toogle.logger import logger
from plugins.compose.novelai import get_ai_generate, get_balance
import toogle.economy as economy
import plugins.compose.midjourney as midjourney
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
    readme = "获取豆包AI生成图片/视频\n视频可选参数f、v、h、l，分别代表图像首帧生成模式、竖屏、高分辨率、长时间\n例如：/doubaov fvh一只在宇宙中飞翔的猫咪"
    
    @staticmethod
    def _headers() -> dict[str, str]:
        api_key = str(config.get("DOUBAO_API_KEY", "")).strip()
        if not api_key:
            raise RuntimeError("DOUBAO_API_KEY 未配置")
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        content = message.message.asDisplay()
        if content.startswith('/doubao '):
            try:
                image_bytes = await asyncio.to_thread(
                    self.generate_image,
                    content[8:].strip(),
                    message.message.get(Image) or [],
                    "2K",
                )
            except Exception as exc:
                logger.error(
                    "Doubao image generation failed: %s",
                    type(exc).__name__,
                )
                return MessageChain.plain(
                    "豆包图片生成失败，请稍后尝试",
                    quote=message.as_quote(),
                    no_charge=True,
                    no_interval=True,
                )
            return MessageChain.create([Image(bytes=image_bytes)])

        image_mode = "reference_image"

        content_str = '\n'.join([x.text for x in message.message.get(Plain)])
        content_str = content_str[8:].strip()

        ratio = "16:9"
        resolution = "480p"
        duration = 7
        while content_str and content_str[0] in "fvhl":
            flag = content_str[0]
            content_str = content_str[1:].strip()
            if flag == 'f':
                image_mode = "first_frame"
            elif flag == 'v':
                ratio = "9:16"
            elif flag == 'h':
                resolution = "720p"
            elif flag == 'l':
                duration = 12

        image = message.message.get(Image)
        if image:
            image = image[0]
        else:
            image = None

        start_time = time.time()
        bot_send_message(
            message,
            MessageChain.create(
                [
                    message.as_quote(),
                    Plain(
                        "收到，正在生成中\n"
                        f"{image_mode}\n{ratio} {resolution} {duration}sec\n"
                        "预计30s-3min"
                    ),
                ]
            ),
        )
        try:
            video_url, token_usage = await asyncio.to_thread(
                self.generate_video,
                content_str=content_str,
                image=image,
                image_mode=image_mode,
                resolution=resolution,
                ratio=ratio,
                duration=duration,
            )
            video_bytes = await asyncio.to_thread(self.download_video, video_url)
        except Exception as exc:
            logger.error(
                "Doubao video generation failed: %s",
                type(exc).__name__,
            )
            return MessageChain.plain(
                "豆包视频生成失败，请稍后尝试",
                quote=message.as_quote(),
                no_charge=True,
                no_interval=True,
            )

        use_time = time.time() - start_time
        video_name = self.video_file_name(video_url)
        upload_ok = False
        if message.message_type == "group" and message.group.id > 0:
            try:
                await asyncio.to_thread(
                    self.upload_group_video,
                    message.group.id,
                    video_name,
                    video_bytes,
                )
                upload_ok = True
            except Exception as exc:
                logger.error(
                    "Doubao video group-file upload failed: %s",
                    type(exc).__name__,
                )

        try:
            gif_bytes = await asyncio.to_thread(
                convert_mp4_to_gif,
                video_bytes,
                fps=24,
                loop=0,
                frame_step=2,
                max_width=480,
            )
        except Exception as exc:
            logger.error(
                "Doubao video GIF conversion failed: %s",
                type(exc).__name__,
            )
            if upload_ok:
                return MessageChain.plain(
                    "原视频已上传，但 GIF 预览生成失败",
                    quote=message.as_quote(),
                )
            return MessageChain.plain(
                "视频文件上传及 GIF 预览均失败",
                quote=message.as_quote(),
                no_charge=True,
                no_interval=True,
            )

        return MessageChain.create([
            message.as_quote(),
            Image(bytes=gif_bytes),
            Plain(
                f"用时{use_time:.2f}秒\n本次生成使用Token: {token_usage}"
                + ("\n原视频文件上传失败，仅返回 GIF 预览" if not upload_ok else "")
            )
        ], no_charge=not upload_ok)


    @classmethod
    def generate_image(
        cls,
        content_str: str,
        images: Optional[List[Image]] = None,
        size: str = "832x1248",
    ) -> bytes:
        images = images or []
        url = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
        data = {
            "model": str(config["DOUBAO_IMAGE_MODEL"]),
            "prompt": content_str,
            "size": size,
            "sequential_image_generation": "disabled",
            "stream": False,
            "response_format": "b64_json",
            "watermark": False
        }

        if len(images) > 1:
            data["image"] = [
                f"data:image/png;base64,{x.getBase64()}"
                for x in images
            ]
        elif len(images) == 1:
            data["image"] = f"data:image/png;base64,{images[0].getBase64()}"

        res = requests.post(
            url,
            json=data,
            headers=cls._headers(),
            timeout=(5, 180),
        )
        res.raise_for_status()
        try:
            b64data = res.json()['data'][0]['b64_json']
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError("豆包图片接口返回格式无效") from exc
        return base64.b64decode(b64data)

    @classmethod
    def generate_video(
        cls,
        content_str: str,
        image: Optional[Image] = None,
        image_mode = "reference_image",
        timeout = 1200,
        resolution = '480p',
        ratio = '16:9',
        duration = 7,
        fps = 24,
    ):
        # image_mode = reference_image, first_frame
        url = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
        parameters = {
            'resolution': resolution,
            'ratio': ratio,
            'duration': duration,
            'fps': fps,
            'wm': 'false',
        }
        parameters_str = ' '.join([f'--{k} {v}' for k, v in parameters.items()])
        model = str(config["DOUBAO_VIDEO_MODEL"])
        if not image:
            data = {
                "model": model,
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
            parameters_str = ' '.join([f'--{k} {v}' for k, v in parameters.items()])
            data = {
                "model": model,
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
        headers = cls._headers()
        res = requests.post(
            url,
            json=data,
            headers=headers,
            timeout=(5, 30),
        )
        res.raise_for_status()
        try:
            pic_id = res.json()['id']
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("豆包视频接口返回格式无效") from exc
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            status_res = requests.get(
                f"https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{pic_id}",
                headers=headers,
                timeout=(5, 30),
            )
            status_res.raise_for_status()
            try:
                status_json = status_res.json()
            except (TypeError, ValueError) as exc:
                raise RuntimeError("豆包视频任务接口返回格式无效") from exc
            if status_json['status'] == 'succeeded':
                video_url = status_json['content']['video_url']
                token_usage = status_json['usage']['total_tokens']
                return video_url, token_usage
            elif status_json['status'] == 'failed':
                raise RuntimeError("豆包视频生成任务失败")
            else:
                time.sleep(5)
        raise Exception("生成超时")

    @staticmethod
    def download_video(video_url: str) -> bytes:
        response = requests.get(video_url, timeout=(5, 120))
        response.raise_for_status()
        return response.content

    @staticmethod
    def video_file_name(video_url: str) -> str:
        name = Path(unquote(urlparse(video_url).path)).name
        if not name:
            return "doubao-video.mp4"
        return name if Path(name).suffix else f"{name}.mp4"

    @staticmethod
    def upload_group_video(
        group_id: int,
        file_name: str,
        video_bytes: bytes,
    ):
        suffix = Path(file_name).suffix or ".mp4"
        with tempfile.NamedTemporaryFile(
            prefix="tooglebot-doubao-",
            suffix=suffix,
            delete=False,
        ) as temp_file:
            temp_file.write(video_bytes)
            temp_path = Path(temp_file.name)
        try:
            return bot_upload_group_file(group_id, file_name, str(temp_path))
        finally:
            temp_path.unlink(missing_ok=True)
