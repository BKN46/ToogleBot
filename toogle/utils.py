import base64
import io
import os
import re
import signal
from typing import List, Tuple, Union

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont

from toogle.configs import config


def read_base64_pic(jpeg_b64_str: str) -> bytes:
    content = base64.b64decode(jpeg_b64_str)
    return content


def get_base64_encode(jpeg_btye: bytes) -> str:
    return base64.b64encode(jpeg_btye).decode("utf-8")


def set_timeout(num, callback):
    def wrap(func):
        def handle(signum, frame):
            raise RuntimeError("运行超时!")

        def to_do(*args, **kwargs):
            try:
                signal.signal(signal.SIGALRM, handle)  # 设置信号和回调函数
                signal.alarm(num)  # 设置 num 秒的闹钟
                r = func(*args, **kwargs)
                signal.alarm(0)  # 关闭闹钟
                return r
            except RuntimeError as e:
                callback()

        return to_do

    return wrap


def handle_TLE():
    raise Exception("运行超时!")


def filter_emoji(desstr, restr=""):
    # 过滤表情
    try:
        co = re.compile("[\U00010000-\U0010ffff]")
    except re.error:
        co = re.compile("[\uD800-\uDBFF][\uDC00-\uDFFF]")
    return co.sub(restr, desstr)


def create_path(path):
    if os.path.isdir(path):
        return
    else:
        os.makedirs(path)


def get_font_wrap(text: str, font: PIL.ImageFont.ImageFont, box_width: int):
    res = []
    for line in text.split("\n"):
        line_width = font.getbbox(line)[2]  # type: ignore
        while box_width < line_width:
            split_pos = int(box_width / line_width * len(line)) - 1
            while True:
                lw = font.getbbox(line[:split_pos])[2]  # type: ignore
                rw = font.getbbox(line[: split_pos + 1])[2]  # type: ignore
                if lw > box_width:
                    split_pos -= 1
                elif rw < box_width:
                    split_pos += 1
                else:
                    break
            res.append(line[:split_pos])
            line = line[split_pos:]
            line_width = font.getbbox(line)[2]  # type: ignore
        res.append(line)
    return "\n".join(res)


def text2img(
    text: str,
    font_path: str = "toogle/plugins/compose/Arial Unicode MS Font.ttf",
    word_size: int = 20,
    max_size: Tuple[int, int] = (500, 1000),
    padding: Tuple[int, int] = (20, 20),
    bg_color: Tuple[int, int, int] = (255, 255, 255),
    font_color: Tuple[int, int, int] = (20, 20, 20),
    font_height_adjust: int = 0,
) -> bytes:
    font = PIL.ImageFont.truetype(font_path, word_size)
    text = get_font_wrap(text, font, max_size[0] - 2 * padding[0])  # type: ignore
    text_width = max([font.getbbox(x)[2] for x in text.split('\n')])
    # text_height = sum([font.getbbox(x)[3] for x in text.split('\n')])  # type: ignore
    text_height = sum([font.getbbox(x)[3] + font_height_adjust for x in text.split("\n")])  # type: ignore
    # text_height = (word_size + 3) * len(text.split("\n"))

    gen_image = PIL.Image.new(
        "RGBA",
        (text_width + 2 * padding[0], min(max_size[1], text_height + 2 * padding[1])),
        bg_color,
    )
    draw = PIL.ImageDraw.Draw(gen_image)

    draw.text(
        (padding[0], padding[1]),
        text,
        font_color,
        font=font,
    )
    img_bytes = io.BytesIO()
    gen_image.save(img_bytes, format="PNG")
    return img_bytes.getvalue()


def list2img(
    input_list: List[Union[str, bytes]],
    font_path: str = "toogle/plugins/compose/Arial Unicode MS Font.ttf",
    word_size: int = 20,
    max_size: Tuple[int, int] = (500, 1000),
    padding: Tuple[int, int] = (20, 20),
    bg_color: Tuple[int, int, int] = (255, 255, 255),
    font_color: Tuple[int, int, int] = (20, 20, 20),
    font_height_adjust: int = 0,
):
    pic_list: List[PIL.Image.Image] = []
    for item in input_list:
        if isinstance(item, str):
            pic_byte = text2img(
                item,
                font_path=font_path,
                word_size=word_size,
                max_size=max_size,
                padding=padding,
                bg_color=bg_color,
                font_color=font_color,
                font_height_adjust=font_height_adjust,
            )
            pic = PIL.Image.open(io.BytesIO(pic_byte))
            pic_list.append(pic)
        elif isinstance(item, bytes):
            pic = PIL.Image.open(io.BytesIO(item))
            gen_image = PIL.Image.new(
                "RGBA",
                (pic.size[0] + 2 * padding[0], pic.size[1] + 2 * padding[1]),
                bg_color,
            )
            gen_image.paste(pic, padding)
            pic_list.append(gen_image)
    total_width = max([x.size[0] for x in pic_list])
    total_height = sum([x.size[1] for x in pic_list])
    last_y=0

    image = PIL.Image.new(
        "RGBA",
        (total_width, total_height),
        bg_color,
    )
    for item in pic_list:
        image.paste(item, (0, last_y))
        last_y += item.size[1]
    img_bytes = io.BytesIO()
    image.save(img_bytes, format="PNG")
    return img_bytes.getvalue()


if __name__ == "__main__":
    test_bytes = text2img("测试测试")
    img = PIL.Image.open(io.BytesIO(test_bytes))
    img.show()
    # open("test.png", "wb").write(test_bytes)
