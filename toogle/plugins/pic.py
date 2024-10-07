import io
import math
import os
import random
import tempfile
from typing import Optional

import PIL.FontFile
import PIL.Image
import PIL.ImageSequence
import PIL.ImageDraw
import PIL.ImageFont

from toogle.message import At, Image, Member, MessageChain, Plain, Quote
from toogle.message_handler import MessageHandler, MessagePack
from toogle.nonebot2_adapter import bot_send_message
from toogle.sql import SQLConnection
from toogle.utils import create_path, is_admin
import toogle.plugins.compose.tarrot as tarrot
from toogle.plugins.gpt import GetOpenAIConversation
from toogle.configs import config

create_path('data/qutu')
create_path('data/long_img')
create_path('data/history_img')

qutu_path = "data/qutu/"

class GetQutu(MessageHandler):
    name = "趣图"
    trigger = r"^#qutu#"
    white_list = True
    thread_limit = True
    readme = "随机获取趣图\n#qutu#为随机获取\n#qutu#all查看所有趣图\n#qutu#[数字] 来选择发送指定趣图"

    async def ret(self, message: MessagePack) -> MessageChain:
        message_str = message.message.asDisplay()
        if message_str == "#qutu#":
            path = qutu_path
            files = [path + x for x in os.listdir(path)]
            file = random.choice(files)
            print(file)
            return MessageChain.create([Image.fromLocalFile(file)])
        elif message_str == "#qutu#all":
            return MessageChain.create(
                [GetQutu.get_all_pic(qutu_path)]
            )
        else:
            index = int(message_str[6:])
            path = qutu_path
            files = [path + x for x in os.listdir(path)]
            file = files[index - 1]
            return MessageChain.create([Image.fromLocalFile(file)])

    @staticmethod
    def get_all_pic(IMAGES_PATH, text_filter="", x_size=128, y_size=128):
        IMAGES_FORMAT = [
            ".jpg",
            ".JPG",
            ".png",
            ".PNG",
            ".gif",
            ".GIF",
            ".mirai",
        ]  # 图片格式
        IMAGE_SAVE_PATH = "data/tmp.jpg"  # 图片转换后的地址
        font_path = "toogle/plugins/compose/fonts/AaRunXing.ttf"
        font = PIL.ImageFont.truetype(font_path, 15)

        # 获取图片集地址下的所有图片名称
        image_names = [
            name
            for name in os.listdir(IMAGES_PATH)
            for item in IMAGES_FORMAT
            if os.path.splitext(name)[1] == item and text_filter in name
        ]
        IMAGE_NUM = len(image_names)
        if IMAGE_NUM > 200:
            IMAGE_NUM = 200
        IMAGE_SIZE = (x_size, y_size)
        IMAGE_COLUMN = math.ceil(math.sqrt(IMAGE_NUM))
        IMAGE_ROW = math.ceil(IMAGE_NUM / IMAGE_COLUMN)

        def image_compose():
            to_image = PIL.Image.new(
                "RGB", (IMAGE_COLUMN * IMAGE_SIZE[0], IMAGE_ROW * IMAGE_SIZE[1])
            )  # 创建一个新图
            # 循环遍历，把每张图片按顺序粘贴到对应位置上
            draw = PIL.ImageDraw.Draw(to_image)
            for y in range(1, IMAGE_ROW + 1):
                for x in range(1, IMAGE_COLUMN + 1):
                    if (y - 1) * IMAGE_COLUMN + x > IMAGE_NUM:
                        break
                    from_image = PIL.Image.open(
                        IMAGES_PATH + image_names[IMAGE_COLUMN * (y - 1) + x - 1]
                    ).resize((IMAGE_SIZE[0], IMAGE_SIZE[1]), PIL.Image.ANTIALIAS) # type: ignore
                    to_image.paste(
                        from_image, ((x - 1) * IMAGE_SIZE[0], (y - 1) * IMAGE_SIZE[1])
                    )
                    draw.text(
                        ((x - 1) * IMAGE_SIZE[0], (y - 1) * IMAGE_SIZE[1]),
                        str((y - 1) * (IMAGE_ROW) + x + y - 2),
                        (200, 0, 0),
                        font,
                    )
            return to_image.save(IMAGE_SAVE_PATH)  # 保存新图

        image_compose()
        return Image.fromLocalFile(IMAGE_SAVE_PATH)


class LongTu(MessageHandler):
    name = "随机龙图"
    trigger = r"^(随机龙图|所有龙图|删龙图|存龙图|指定龙图)"
    thread_limit = True
    readme = "存龙图"
    interval = 30
    price = 3

    async def ret(self, message: MessagePack) -> MessageChain:
        IMAGES_PATH = "data/long_img/"  # 图片集地址
        if message.message.asDisplay() == "随机龙图":
            files = [IMAGES_PATH + x for x in os.listdir(IMAGES_PATH)]
            file = random.choice(files)
            return MessageChain.create([Image.fromLocalFile(file)])
        elif message.message.asDisplay() == "所有龙图":
            return MessageChain.create(
                [
                    GetQutu.get_all_pic(IMAGES_PATH),
                    Plain(f"一共{len(os.listdir(IMAGES_PATH))}张龙图"),
                ]
            )
        elif message.message.asDisplay().startswith("指定龙图"):
            num = int(message.message.asDisplay().strip().split()[-1])
            files = [IMAGES_PATH + x for x in os.listdir(IMAGES_PATH)]
            file = files[num]
            return MessageChain.create([Image.fromLocalFile(file)])
        elif message.message.asDisplay().startswith("删龙图"):
            user = SQLConnection.get_user(message.member.id)
            if user[1] > 5:  # type: ignore
                files = [IMAGES_PATH + x for x in os.listdir(IMAGES_PATH)]
                del_files = []
                for num in message.message.asDisplay().strip().split()[1:]:
                    del_files.append(files[int(num)])
                for pic in del_files:
                    os.remove(pic)
                return MessageChain.create([Plain(f"哗啦啦，删掉了{len(del_files)}张龙图")])
            else:
                return MessageChain.create([Plain(f"你也配？")])
        else:
            pics = message.message.get(Image)
            for image in pics:
                image_file_name = f"{image.id}".replace("{", "").replace("}", "")  # type: ignore
                image.save(IMAGES_PATH + image_file_name) # type: ignore
            return MessageChain.create([Plain(f"搞定, 存了{len(pics)}张龙图")])


class HistoryTu(MessageHandler):
    name = "黑历史"
    trigger = r"^(记史|存黑历史|黑历史|删黑历史)"
    thread_limit = True
    readme = "群史官"

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        group_id = str(message.group.id)
        IMAGES_PATH = f"data/history_img/"  # 图片集地址
        if group_id not in os.listdir(IMAGES_PATH):
            os.mkdir(f"{IMAGES_PATH}{group_id}/")
        IMAGES_PATH = f"{IMAGES_PATH}{group_id}/"  # 图片集地址
        message_content = message.message.asDisplay()
        if message_content.startswith("黑历史"):
            at = message.message.get(At)
            if at:
                text_filter = f"{at[0].target}|||" # type: ignore
                message_content = MessageChain.create([
                    i for i in message.message.root if type(i) != At
                ]).asDisplay().strip()
            else:
                text_filter = ""
            if "随机" in message_content:
                files = [IMAGES_PATH + x for x in os.listdir(IMAGES_PATH) if text_filter in x]
                file = random.choice(files)
                return MessageChain.create([Image.fromLocalFile(file)])
            elif message_content == "黑历史":
                return MessageChain.create([
                    GetQutu.get_all_pic(IMAGES_PATH, text_filter=text_filter, x_size=200, y_size=100),
                    Plain(f"一共{len(os.listdir(IMAGES_PATH))}张黑历史"),
                ])
            else:
                try:
                    num = int(message.message.asDisplay().strip().split()[-1])
                except Exception as e:
                    return
                files = [IMAGES_PATH + x for x in os.listdir(IMAGES_PATH) if text_filter in x]
                if not 0 <= num < len(files):
                    return MessageChain.plain(f"黑历史范围: 0 - {len(files) - 1}", quote=message.as_quote())
                file = files[num]
                return MessageChain.create([Image.fromLocalFile(file)])

        if message_content.startswith("删黑历史"):
            if not is_admin(message.member.id):
                return MessageChain.plain(f"你也配？")
            images: Optional[List[Image]] = message.message.get(Image) # type: ignore
            if images:
                del_cnt = 0
                files = [IMAGES_PATH + x for x in os.listdir(IMAGES_PATH)]
                for img in images:
                    img_file_name = img.id.replace("{", "").replace("}", "")
                    for f in files:
                        if img_file_name in f:
                            os.remove(f)
                            del_cnt += 1
                            break
                return MessageChain.plain(f"删黑历史成功: {del_cnt}张", quote=message.as_quote())
            else:
                files = [IMAGES_PATH + x for x in os.listdir(IMAGES_PATH)]
                del_files = []
                try:
                    for num in message_content[4:].strip().split():
                        del_files.append(files[int(num)])
                    pics = [Image(bytes=open(i, 'rb').read()) for i in del_files]
                    for pic in del_files:
                        os.remove(pic)
                    return MessageChain.create([Plain(f"哗啦啦，删掉了{len(del_files)}张黑历史:")] + pics)
                except Exception as e:
                    return MessageChain.plain(f"删黑历史失败: {e}\n{str(del_files)}")

        else:
            pics = message.message.get(Image)
            at = message.message.get(At)
            for image in pics:
                image_file_name = f"{image.id}".replace("{", "").replace("}", "") # type: ignore
                if os.path.exists(IMAGES_PATH + image_file_name):
                    os.remove(IMAGES_PATH + image_file_name)
                if at:
                    image_file_name = f"{at[0].target}|||{image_file_name}" # type: ignore
                image.save(IMAGES_PATH + image_file_name) # type: ignore
            return MessageChain.create([Plain(f"搞定, 存了{len(pics)}张黑历史")])


class Tarrot(MessageHandler):
    name = "塔罗牌"
    trigger = r"^塔罗 (.*)"
    thread_limit = True
    readme = "随机塔罗牌"
    interval = 600
    price = 10

    async def ret(self, message: MessagePack) -> MessageChain:
        tarrot_question = message.message.asDisplay()[3:].strip()
        tarrot_spread = tarrot_question
        if not tarrot_spread:
            return MessageChain.create([Plain("请描述你想要占卜的，或直接指定牌阵：\n" + ", ".join(tarrot.TARROT_SPREADS.keys()))])
        if tarrot_spread not in tarrot.TARROT_SPREADS:
            for spread in tarrot.TARROT_SPREADS:
                if spread in tarrot_spread:
                    tarrot_spread = spread
                    break
            else:
                if any([i in tarrot_spread for i in ["运势", "运气"]]):
                    tarrot_spread = "身心灵"
                elif any([i in tarrot_spread for i in ["恋爱", "爱情", "喜欢", "对象"]]):
                    tarrot_spread = "恋爱圣三角"
                elif any([i in tarrot_spread for i in ["不", "还是"]]):
                    tarrot_spread = "圣三角"
                elif any([i in tarrot_spread for i in ["之后", "之前", "过去", "未来", "今", "人生"]]):
                    tarrot_spread = "时间之箭"
                elif any([i in tarrot_spread for i in ["简单"]]):
                    tarrot_spread = "单张"
                elif any([i in tarrot_spread for i in ["应该", "怎么"]]):
                    tarrot_spread = "二则一"
                elif any([i in tarrot_spread for i in ["指引", "指导"]]):
                    tarrot_spread = "四元素"
                elif any([i in tarrot_spread for i in ["成绩", "结果"]]):
                    tarrot_spread = "大十字"
                else:
                    tarrot_spread = "万能"
        header = f"{message.member.name} {tarrot_question}[{tarrot_spread}]"

        pic_bytes, deck = tarrot.get_tarrot(tarrot_spread, header, return_deck=True)

        try:
            res = GetOpenAIConversation.get_chat(
                f"请帮忙解释一下这个塔罗牌阵，不需要逐牌解释，只需要输出最终300字以内总结：求卜者的问题是 {tarrot_question}，使用{tarrot_spread}牌阵，翻开塔罗牌依次为{'、'.join(deck[1:])}", # type: ignore
                model="deepseek-chat",
                url = "https://api.deepseek.com"
            )
            return MessageChain.create([message.as_quote(), Image(bytes=pic_bytes), Plain(f"塔罗牌解:\n{res}")]) # type: ignore
        except Exception as e:
            return MessageChain.create([message.as_quote(), Image(bytes=pic_bytes), Plain(f"Deepseek出现问题，暂无解牌")]) # type: ignore


class ReverseGIF(MessageHandler):
    name = "反转GIF"
    trigger = r"^反转GIF|^反转gif"
    thread_limit = True
    readme = "反转GIF"

    async def ret(self, message: MessagePack) -> MessageChain:
        pics = message.message.get(Image)
        if not pics:
            return MessageChain.plain("没看到图", quote=message.as_quote())
        pic = pics[0]
        with tempfile.NamedTemporaryFile(dir="data", suffix=".gif") as temp:
            pic.save(temp.name)
            im = PIL.Image.open(temp.name)
            frames = [frame.copy() for frame in PIL.ImageSequence.Iterator(im)]
            frames.reverse()
            frames[0].save(temp.name, save_all=True, append_images=frames[1:])
            pic_bytes = open(temp.name, "rb").read()
        return MessageChain.create([message.as_quote(), Image(bytes=pic_bytes)])
