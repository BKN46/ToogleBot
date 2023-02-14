import base64
import io
import os
import re
import signal
import urllib.parse
from typing import List, Tuple, Union
from xmlrpc.client import Boolean

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import requests

from toogle.configs import config


def read_base64_pic(jpeg_b64_str: str) -> bytes:
    content = base64.b64decode(jpeg_b64_str)
    return content


def get_base64_encode(jpeg_btye: bytes) -> str:
    return base64.b64encode(jpeg_btye).decode("utf-8")


class anti_cf_requests():
    sa_api = 'https://api.scrapingant.com/v2/general'
    scraping_ant_token = config.get("SCRIPING_ANT_TOKEN")

    @staticmethod
    def get(*args, **kwargs):
        url = args[0]
        qParams = {'url': url, 'x-api-key': anti_cf_requests.scraping_ant_token}
        reqUrl = f'{anti_cf_requests.sa_api}?{urllib.parse.urlencode(qParams)}' 
        return requests.get(reqUrl, **kwargs)

    @staticmethod
    def post(*args, content_type="application/json", **kwargs):
        url = args[0]
        qParams = {'url': url, 'x-api-key': anti_cf_requests.scraping_ant_token}
        header = {"Ant-Content-Type": content_type}
        reqUrl = f'{anti_cf_requests.sa_api}?{urllib.parse.urlencode(qParams)}' 
        return requests.post(reqUrl, **kwargs, headers=header)


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
    text_width = max([font.getbbox(x)[2] for x in text.split("\n")])
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
    last_y = 0

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


def draw_rich_text(
    text: str,
    max_size: Tuple[int, int] = (500, 1000),
    padding: Tuple[int, int] = (20, 20),
    bg_color: Tuple[int, int, int] = (255, 255, 255),
    font_color: Tuple[int, int, int] = (20, 20, 20),
    word_size: int = 20,
    font_path: str = "toogle/plugins/compose/Arial Unicode MS Font.ttf",
    byte_mode: bool = True,
    src_img: Union[None, PIL.Image.Image] = None,
    position: Tuple[int, int] = (0, 0),
):
    font = PIL.ImageFont.truetype(font_path, word_size)
    rich_content = r'(<(.*?)\s(.*?)>(.*?)<.*?/>)'
    res = re.fullmatch(rich_content, text)
    res = []
    re_list = [x for x in re.finditer(rich_content, text)]
    for i, x in enumerate(re_list):
        if i == 0 and x.span()[0] > 0:
            res.append((text[:x.span()[0]], {}))
        elif x.span()[0] > 0:
            res.append((text[re_list[i-1].span()[1]:x.span()[0]], {}))

        rich_content = x.groups()
        rich_header = rich_content[1]
        rich_param = {
            v.split("=")[0]: eval(v.split("=")[1][1:-1])
            for v in
            rich_content[2].split()
        }
        res.append((rich_content[3], rich_param))

        if i == len(re_list) - 1 and x.span()[1] < len(text) - 1:
            res.append((text[x.span()[1]:], {}))

    box_width = max_size[0] - padding[0] * 2
    lines = []

    line_res = []
    now_line = 0
    for part in res:
        if '\n' in part[0]:
            part_lines = part[0].split('\n')
            line_res[now_line].append((part_lines[0], part[1]))
            line_res += [[(x, part[1])] for x in part_lines[1:]]
            now_line += len(part_lines) - 1
        elif now_line >= len(line_res):
            line_res.append([(part[0], part[1])])
        else:
            line_res[now_line].append((part[0], part[1]))

    for line in line_res:
        tmp_box_width = box_width
        lines.append([])
        for part in line:
            part_text = part[0]
            line_width = font.getbbox(part_text)[2]  # type: ignore
            same_line = True
            while tmp_box_width < line_width:
                same_line = False
                split_pos = int(tmp_box_width / line_width * len(part_text)) - 1
                while True:
                    lw = font.getbbox(part_text[:split_pos])[2]  # type: ignore
                    rw = font.getbbox(part_text[: split_pos + 1])[2]  # type: ignore
                    if lw > tmp_box_width:
                        split_pos -= 1
                    elif rw < tmp_box_width:
                        split_pos += 1
                    else:
                        break
                if part_text[:split_pos]:
                    lines[-1].append((part_text[:split_pos], part[1]))
                tmp_box_width = box_width
                part_text = part_text[split_pos:]
                line_width = font.getbbox(part_text)[2]  # type: ignore
            tmp_box_width -= line_width
            if lines and same_line and part_text:
                lines[-1].append((part_text, part[1]))
            elif part_text:
                lines.append([(part_text, part[1])])

    total_width = box_width
    total_height = font.getbbox("X")[3] * len(lines)
    if src_img:
        gen_image = src_img
        padding = (0, 0)
    else:
        gen_image = PIL.Image.new(
            "RGBA",
            (total_width + padding[0] * 2, total_height + padding[1] * 2),
            bg_color,
        )
    image_draw = PIL.ImageDraw.Draw(gen_image)

    for y, line in enumerate(lines):
        x = 0
        y = y * font.getbbox("X")[3]
        for part in line:
            if 'fill' not in part[1]:
                part[1]['fill'] = font_color
            image_draw.text(
                (padding[0] + position[0] + x, padding[1] + position[1] + y),
                part[0],
                font=font,
                **part[1]
            )
            x += font.getbbox(part[0])[2]

    if byte_mode:
        img_bytes = io.BytesIO()
        gen_image.save(img_bytes, format="PNG")
        return img_bytes.getvalue()
    else:
        return gen_image


def is_admin(id: int) -> Boolean:
    for i in config.get("ADMIN_LIST", []):
        if id == int(i):
            return True
    return False


def get_main_groups() -> List[int]:
    return [
        int(x) for x in
        config.get("GROUP_LIST", [])
    ]


if __name__ == "__main__":
    test_bytes = text2img("测试测试")
    img = PIL.Image.open(io.BytesIO(test_bytes))
    img.show()
    # open("test.png", "wb").write(test_bytes)
