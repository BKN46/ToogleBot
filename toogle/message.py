import os
from typing import List, Optional, Sequence

import PIL.Image
import requests

from toogle.utils import (create_path, get_base64_encode, read_base64_pic,
                          text2img)

create_path('data/buffer')

class Element:
    def asDisplay(self) -> str:
        return ""


class Group:
    def __init__(self, id: int, name: str) -> None:
        self.id = id
        self.name = name


class Member:
    def __init__(self, id: int, name: str) -> None:
        self.id = id
        self.name = name


class Quote(Element):
    def __init__(self) -> None:
        pass

    def asDisplay(self) -> str:
        return f"[Quote origin]"


class At(Element):
    def __init__(self, target: int) -> None:
        self.target = target

    def asDisplay(self) -> str:
        return f"@{self.target}"


class Plain(Element):
    def __init__(self, text: str) -> None:
        self.text = text

    def asDisplay(self) -> str:
        return self.text


class Image(Element):
    id: Optional[str] = None
    base64: Optional[str] = None
    url: Optional[str] = None
    path: Optional[str] = None

    def __init__(
        self,
        id: Optional[str] = None,
        path: Optional[str] = None,
        url: Optional[str] = None,
        bytes: Optional[bytes] = None,
        base64: Optional[str] = None,
    ) -> None:
        self.id = id
        self.base64 = base64
        if bytes:
            self.base64 = get_base64_encode(bytes)
        self.path = path
        self.url = url

    def asDisplay(self) -> str:
        return "[图片]"

    def getBase64(self) -> str:
        image_bytes = self.getBytes()
        self.base64 = get_base64_encode(image_bytes)
        return self.base64

    def getBytes(self) -> bytes:
        if self.base64:
            image_bytes = read_base64_pic(self.base64)
        elif self.path:
            image_bytes = open(self.path, "rb").read()
        elif self.url:
            image_bytes = requests.get(self.url).content
        else:
            image_bytes = b""
        return image_bytes

    def save(self, path: str):
        image_bytes = self.getBytes()
        with open(path, "wb") as f:
            f.write(image_bytes)

    @staticmethod
    def text_image(text: str, **kwargs) -> "Image":
        return Image(bytes=text2img(text, **kwargs))

    @staticmethod
    def buffered_url_pic(pic_url) -> "Image":
        buffer_path = "data/buffer/"
        all_buffer = os.listdir(buffer_path)

        trans_url = pic_url.replace("://", "_").replace("/", "_")

        if trans_url in all_buffer:
            return Image.fromLocalFile(buffer_path + trans_url)

        PIL.Image.open(requests.get(pic_url, stream=True).raw).save(buffer_path + trans_url)
        return Image.fromLocalFile(buffer_path + trans_url)

    @staticmethod
    def fromLocalFile(path: str) -> "Image":
        return Image(path=path)


class MessageChain:
    def __init__(self, message_list: Sequence[Element]) -> None:
        self.root = message_list

    def asDisplay(self) -> str:
        return "".join(i.asDisplay() for i in self.root)

    def get(self, t):
        return [item for item in self.root if isinstance(item, t)]

    @staticmethod
    def create(message_list: List) -> "MessageChain":
        return MessageChain(message_list)
    
    @staticmethod
    def plain(text: str) -> "MessageChain":
        return MessageChain([Plain(text)])
