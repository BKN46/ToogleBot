import base64
import os
import re
import signal

import PIL.Image

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
                print("start alarm signal.")
                r = func(*args, **kwargs)
                print("close alarm signal.")
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
