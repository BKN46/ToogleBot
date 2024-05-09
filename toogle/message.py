import io
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
    
    def to_dict(self) -> dict:
        res = {}
        for x in dir(self):
            if not x.startswith("_") and not callable(getattr(self, x)) and getattr(self, x):
                if isinstance(getattr(self, x), Element):
                    res[x] = getattr(self, x).to_dict()
                else:
                    try:
                        if len(getattr(self, x)) < 50:
                            res[x] = getattr(self, x)
                        else:
                            res[x] = getattr(self, x)[:50] + "..."
                    except Exception as e:
                        res[x] = "[Error in parse]"

        res.update({"type": self.__class__.__name__})
        return res


class Group:
    def __init__(self, id: int, name: str) -> None:
        self.id = id
        self.name = name

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name}


class Member:
    def __init__(self, id: int, name: str) -> None:
        self.id = id
        self.name = name

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name}


class Quote(Element):
    def __init__(self, id: int, sender_id: int, target_id: int, group_id: int, message: 'MessageChain') -> None:
        self.id = id
        self.sender_id = sender_id
        self.target_id = target_id
        self.group_id = group_id
        self.message = message

    def asDisplay(self) -> str:
        return f"\n[Quote origin #{self.id} '{self.message.asDisplay()}' from {self.sender_id} in {self.group_id}]\n"


class At(Element):
    def __init__(self, target: int) -> None:
        self.target = target

    def asDisplay(self) -> str:
        return f"@{self.target}"


class AtAll(Element):
    def asDisplay(self) -> str:
        return f"@all"


class Plain(Element):
    def __init__(self, text: str) -> None:
        self.text = text

    def asDisplay(self) -> str:
        return self.text


class Image(Element):
    def __init__(
        self,
        id: Optional[str] = None,
        path: Optional[str] = None,
        url: Optional[str] = None,
        bytes: Optional[bytes] = None,
        base64: Optional[str] = None,
        image: Optional[PIL.Image.Image] = None,
    ) -> None:
        self.id = id
        self.base64 = base64
        if bytes:
            self.base64 = get_base64_encode(bytes)
        if image:
            img_bytes = io.BytesIO()
            image.save(img_bytes, format="PNG")
            self.base64 = get_base64_encode(img_bytes.getvalue())
        self.path = path
        self.url = url

    def asDisplay(self) -> str:
        return "[图片]"

    def getBase64(self) -> str:
        if self.base64:
            return self.base64
        image_bytes = self.getBytes()
        self.base64 = get_base64_encode(image_bytes)
        return self.base64
    
    def compress(self, max_height=500, max_width=700) -> "Image":
        image_bytes = self.getBytes()
        image = PIL.Image.open(io.BytesIO(image_bytes))
        if image.height > max_height or image.width > max_width:
            image.thumbnail((max_width, max_height))
            image_bytes = io.BytesIO()
            image.save(image_bytes, format="PNG")
            new_base64 = get_base64_encode(image_bytes.getvalue())
        else:
            new_base64 = self.base64
        return Image(base64=new_base64)

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
    def buffered_url_pic(pic_url, return_PIL=False):
        buffer_path = "data/buffer/"
        all_buffer = os.listdir(buffer_path)

        trans_url = pic_url.replace("://", "_").replace("/", "_")

        if trans_url in all_buffer:
            if not return_PIL:
                return Image.fromLocalFile(buffer_path + trans_url)
            else:
                return PIL.Image.open(buffer_path + trans_url)

        pil_image = PIL.Image.open(requests.get(pic_url, stream=True).raw)
        pil_image.save(buffer_path + trans_url, format="PNG")
        if not return_PIL:
            return Image.fromLocalFile(buffer_path + trans_url)
        else:
            return pil_image

    @staticmethod
    def fromLocalFile(path: str) -> "Image":
        return Image(path=path)


class ForwardMessage(Element):
    def __init__(
        self,
        node_list: Optional[list],
        sender_id: Optional[int],
        time: Optional[int],
        message: 'MessageChain'
    ) -> None:
        self.node_list = node_list or []
        self.sender_id = sender_id
        self.time = time
        self.message = message
        print(repr(self.asDisplay()), file=open("debug.log", "a"))

    def asDisplay(self) -> str:
        msgs = ", ".join([x['message'].asDisplay() for x in self.node_list])

        return f"[Forward origin from {self.sender_id} [{msgs}]]"


class MessageChain:
    def __init__(self, message_list: Sequence[Element], no_interval=False) -> None:
        self.root = message_list
        self.no_interval = no_interval

    def asDisplay(self) -> str:
        return "".join(i.asDisplay() for i in self.root)

    def get(self, t):
        return [item for item in self.root if isinstance(item, t)]

    def get_quote(self) -> Optional[int]:
        quotes = self.get(Quote)
        return quotes[0].id if quotes else None # type:ignore

    @staticmethod
    def create(message_list: List, no_interval=False) -> "MessageChain":
        return MessageChain(message_list, no_interval)
    
    @staticmethod
    def plain(text: str, no_interval=False, quote=None) -> "MessageChain":
        if quote:
            return MessageChain([quote, Plain(text)], no_interval=no_interval)
        return MessageChain([Plain(text)], no_interval=no_interval)
    
    def __add__(self, message: "MessageChain") -> "MessageChain":
        return MessageChain(self.root + message.root, no_interval=self.no_interval) # type: ignore

    def __repr__(self) -> str:
        return repr(self.root)
    
    def to_dict(self) -> dict:
        return {"root": [x.to_dict() for x in self.root], "no_interval": self.no_interval}
