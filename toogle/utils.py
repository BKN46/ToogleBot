import base64
from contextlib import contextmanager
import ctypes
import datetime
import hashlib
import io
import json
import multiprocessing
import os
import pickle
import re
import signal
import tempfile
import threading
import time
import traceback
import urllib.parse
from typing import List, Tuple, Union
from xmlrpc.client import Boolean

from PIL import UnidentifiedImageError
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import bloom_filter
import requests

import nonebot

from toogle.configs import config
from toogle.exceptions import VisibleException


if not os.path.exists("log"):
    os.makedirs("log")
if not os.path.exists("data"):
    os.makedirs("data")

PIC_BLOOM = bloom_filter.BloomFilter(max_elements=10**6, error_rate=0.01, filename='data/pic_bloom')
SFW_BLOOM = bloom_filter.BloomFilter(max_elements=10**6, error_rate=0.01, filename='data/sfw_bloom')

SETU_RECORD_PATH = "data/setu_record.json"

JSON_WRITE_LOCKS = {}

if not os.path.exists(SETU_RECORD_PATH):
    with open(SETU_RECORD_PATH, "w") as f:
        f.write("{}")

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


class TimeoutWrapper:
    def __init__(self, func, timeout: int) -> None:
        self.func = func
        self.ret = None
        self.timeout = timeout

    def run_wrapepr(self, *args, **kwargs):
        self.ret = self.func(*args, **kwargs)

    def run(self, *args, **kwargs):
        thread = threading.Thread(target=self.run_wrapepr, args=args, kwargs=kwargs)
        thread.start()
        thread.join(timeout=self.timeout)
        if thread.is_alive():
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread.ident, ctypes.py_object(SystemExit))
            raise RuntimeError("Timeout")
        return self.ret
        

def set_timeout(num, callback):
    def wrap(func):
        def to_do(*args, **kwargs):
            try:
                wrapper = TimeoutWrapper(func, num)
                wrapper.run(*args, **kwargs)
                return wrapper.ret
            except RuntimeError as e:
                callback()
        return to_do

    return wrap


def handle_TLE():
    raise VisibleException("运行超时!")


@contextmanager
def modify_json_file(name: str):
    if name.endswith('.json'):
        name = name[:-5]

    if name not in JSON_WRITE_LOCKS:
        JSON_WRITE_LOCKS[name] = threading.Lock()

    with JSON_WRITE_LOCKS[name]:
        path = f"data/{name}.json"
        # os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
        else:
            data = {}
        yield data
        with open(path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


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


def dp_backpack_algorithm(space: int, items: List[int]) -> List[int]:
        n = len(items)
        dp = [[0] * (space + 1) for _ in range(n + 1)]

        for i in range(1, n + 1):
            for j in range(1, space + 1):
                if j >= items[i - 1]:
                    dp[i][j] = max(dp[i - 1][j], dp[i - 1][j - items[i - 1]] + items[i - 1])
                else:
                    dp[i][j] = dp[i - 1][j]

        res = []
        i, j = n, space
        while i > 0 and j > 0:
            if dp[i][j] != dp[i - 1][j]:
                res.append(i - 1)
                j -= items[i - 1]
            i -= 1

        return res


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
    font_path: str = "toogle/plugins/compose/fonts/Arial Unicode MS Font.ttf",
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
        bg_color, # type: ignore
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
    font_path: str = "toogle/plugins/compose/fonts/Arial Unicode MS Font.ttf",
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
                bg_color, # type: ignore
            )
            gen_image.paste(pic, padding)
            pic_list.append(gen_image)
    total_width = max([x.size[0] for x in pic_list])
    total_height = sum([x.size[1] for x in pic_list])
    last_y = 0

    image = PIL.Image.new(
        "RGBA",
        (total_width, total_height),
        bg_color, # type: ignore
    )
    for item in pic_list:
        image.paste(item, (0, last_y))
        last_y += item.size[1]
    img_bytes = io.BytesIO()
    image.save(img_bytes, format="PNG")
    return img_bytes.getvalue()


def color_gradient(
    c1: Tuple[int, int, int],
    c2: Tuple[int, int, int],
    v: float,
    mid_c: Tuple[int, int, int] = (255, 255, 255),
) -> Tuple[int, int, int]:
    if v < 0:
        return c1
    elif v > 1:
        return c2
    elif v <= 0.5:
        return (
            int(c1[0] + (mid_c[0] - c1[0]) * v * 2),
            int(c1[1] + (mid_c[1] - c1[1]) * v * 2),
            int(c1[2] + (mid_c[2] - c1[2]) * v * 2),
        )
    else:
        return (
            int(c2[0] + (mid_c[0] - c2[0]) * (1 - v) * 2),
            int(c2[1] + (mid_c[1] - c2[1]) * (1 - v) * 2),
            int(c2[2] + (mid_c[2] - c2[2]) * (1 - v) * 2),
        )


def draw_rich_text(
    text: str,
    max_size: Tuple[int, int] = (500, 1000),
    padding: Tuple[int, int] = (20, 20),
    bg_color: Tuple[int, int, int] = (255, 255, 255),
    font_color: Tuple[int, int, int] = (20, 20, 20),
    word_size: int = 20,
    font_path: str = "toogle/plugins/compose/fonts/Arial Unicode MS Font.ttf",
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
            bg_color, # type: ignore
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


def pic_max_resize(
    img: PIL.Image.Image,
    max_width: int,
    max_height: int,
    hard_limit: bool = False,
):
    if hard_limit:
        resize_ratio = min(max_width / img.size[0], max_height / img.size[1])
        return img.resize(
            (int(img.size[0] * resize_ratio), int(img.size[1] * resize_ratio)),
            PIL.Image.ANTIALIAS, # type: ignore
        )
    else:
        if img.size[0] >= img.size[1]:
            return img.resize(
                (max_width, int(img.size[1] * max_width / img.size[0])),
                PIL.Image.ANTIALIAS, # type: ignore
            )
        else:
            return img.resize(
                (int(img.size[0] * max_height / img.size[1]), max_height),
                PIL.Image.ANTIALIAS, # type: ignore
            )


def draw_pic_text(
    pic: PIL.Image.Image,
    text: str,
    font_path: str = "toogle/plugins/compose/fonts/Arial Unicode MS Font.ttf",
    word_size: int = 17,
    pic_size: Tuple[int, int] = (300, 460),
    max_size: Tuple[int, int] = (1000, 500),
    padding: Tuple[int, int] = (20, 20),
    word_padding: Tuple[int, int] = (0, 0),
    bg_color: Tuple[int, int, int] = (255, 255, 255),
    font_color: Tuple[int, int, int] = (20, 20, 20),
    byte_mode: bool = True
):
    pic = pic_max_resize(pic, pic_size[0] - padding[0], pic_size[1] - 2 * padding[1])
    pic_size = pic.size
    text_bytes = text2img(
        text,
        font_path=font_path,
        word_size=word_size,
        max_size=(max_size[0] - pic_size[0] - padding[0], int(max_size[1] * 1.5)),
        padding=padding,
        bg_color=bg_color,
        font_color=font_color,
        font_height_adjust=6,
    )
    text_pic = PIL.Image.open(io.BytesIO(text_bytes))
    text_pic_size = text_pic.size
    gen_image = PIL.Image.new(
        "RGBA",
        (max_size[0], max(max_size[1], text_pic_size[1])),
        bg_color, # type: ignore
    )
    gen_image.paste(pic, (padding[0], padding[1]), pic)
    gen_image.paste(text_pic, (pic_size[0] + padding[0] + word_padding[0], padding[1] + word_padding[1]))

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


def is_admin_group(id: int) -> Boolean:
    for i in config.get("ADMIN_GROUP_LIST", []):
        if id == int(i):
            return True
    return False


def get_main_groups() -> List[int]:
    return [
        int(x) for x in
        config.get("GROUP_LIST", [])
    ]


def print_err(e, plugin, message_pack):
    msg = (
        f"{'*'*20}\n[{datetime.datetime.now().strftime('%Y-%m-%d, %H:%M:%S')}]"
        f"[{plugin.name}] {repr(e)}\n"
        f"[{message_pack.group.id}][{message_pack.member.id}]{message_pack.message.asDisplay()}\n"
        f"\n{'*'*20}\n{traceback.format_exc()}"
    )
    print(msg, file=open("log/err.log", "a"))
    nonebot.logger.error(f"[{plugin.name}] {repr(e)}")  # type: ignore
    return msg


def print_call(plugin, message_pack):
    msg = (
        f"{plugin.name}\t"
        f"{time.time()}\t"
        f"{message_pack.group.id}\t"
        f"{message_pack.member.id}"
    )
    print(msg, file=open("log/call.log", "a"))
    return msg


if __name__ == "__main__":
    test_bytes = text2img("测试测试")
    img = PIL.Image.open(io.BytesIO(test_bytes))
    img.show()
    # open("test.png", "wb").write(test_bytes)
