import random
import math
import os

import PIL.Image, PIL.FontFile, PIL.ImageFont, PIL.ImageDraw

from toogle.message_handler import MessagePack, MessageHandler
from toogle.message import MessageChain, Plain, Quote, Member
from toogle.message import Image

from toogle.sql import SQLConnection

qutu_path = "data/qutu/"

class GetQutu(MessageHandler):
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
        font_path = "toogle/plugins/pic/AaRunXing.ttf"
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
                    ).resize((IMAGE_SIZE[0], IMAGE_SIZE[1]), PIL.Image.ANTIALIAS)
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
    trigger = r"^(随机龙图|所有龙图|删龙图|存龙图|指定龙图)"
    thread_limit = True
    readme = "存龙图"

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
                if image.path:  # type: ignore
                    os.system(f"cp {image.path} {IMAGES_PATH}{image_file_name}")  # type: ignore
                elif image.url:  # type: ignore
                    with open(f"{IMAGES_PATH}{image_file_name}", "wb") as f:  # type: ignore
                        image_byte = image.getBase64()  # type: ignore
                        f.write(image_byte)
            return MessageChain.create([Plain(f"搞定, 存了{len(pics)}张龙图")])
