from typing import List, Sequence, Optional

import requests

from toogle.utils import get_base64_encode

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
        base64: Optional[str] = None,
    ) -> None:
        self.id = id
        self.base64 = base64
        self.path = path
        self.url = url

    def asDisplay(self) -> str:
        return "[图片]"

    def getBase64(self) -> str:
        if self.path:
            image_bytes = open(self.path, 'rb').read()
        elif self.url:
            image_bytes = requests.get(self.url).raw
        else:
            image_bytes = b''
        self.base64 = get_base64_encode(image_bytes)
        return self.base64

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
