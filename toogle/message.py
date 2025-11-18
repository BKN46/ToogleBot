import io
import os
import pickle
import time
from typing import List, Optional, Sequence, Tuple, Union

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

    def __str__(self) -> str:
        return self.text

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
        cache: bool = False,
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
        self.cache = cache

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
        sender_name: Optional[str],
        message_id: Optional[int],
        message: 'MessageChain'
    ) -> None:
        self.node_list = node_list or []
        self.sender_id = sender_id
        self.sender_name = sender_name
        self.message_id = message_id
        self.time = time
        self.message = message
        # pickle.dump(self, open("debug_forward.pkl", "wb"))
        # print(repr(self.asDisplay()), file=open("debug.log", "a"))

    def asDisplay(self) -> str:
        msgs = ", ".join([x['message'].asDisplay() for x in self.node_list])

        return f"[Forward origin from {self.sender_id} [{msgs}]]"

    def get(self, t, forward_layer=-1):
        res = []
        for item in self.node_list:
            res += item['message'].get(t, forward_layer=forward_layer)
        return res
    
    @staticmethod
    def get_node_list(node_list: List[Tuple[int, int, str, 'MessageChain']]) -> List[dict]:
        '''
        param:
            node_list: [(senderId, time, senderName, messageChain)]
        '''
        return [
            {
                "sender": x[0],
                "time": x[1],
                "senderName": x[2],
                "message": x[3],
            }
            for x in node_list
        ]
    
    @staticmethod
    def get_quick_forward_message(message_list: List[Union['MessageChain', Tuple[int, str, 'MessageChain']]], people_name="QQ用户", forward_name="转发消息", forward_brief="转发消息") -> "MessageChain":
        if not isinstance(message_list[0], tuple):
            message_list = [(0, people_name, x) for x in message_list] # type: ignore
    
        res = MessageChain([ForwardMessage(
            ForwardMessage.get_node_list([
                (x[0], int(time.time()), x[1], x[2]) # type: ignore
                for x in message_list
            ]),
            0,
            int(time.time()),
            forward_name,
            0,
            MessageChain.plain(forward_brief),
        )])

        return res

    def add(self, message_chain: 'MessageChain', sender_id=0, sender_name="QQ用户"):
        self.node_list.append({
            "sender": sender_id,
            "time": int(time.time()),
            "senderName": sender_name,
            "message": message_chain
        })


class Xml(Element):
    def __init__(self, xml: str) -> None:
        self.xml = xml

    def asDisplay(self) -> str:
        return f"[xml message]"
    
    @staticmethod
    def get_default_xml(title, content, brief="大黄狗卡片", pic_url="http://placekitten.com/100/100", url="www.baidu.com") -> "Xml":
        template = f'''<?xml version="1.0" encoding="utf-8"?>
<msg templateID="12345" action="web" brief="{brief}" serviceID="1" url="{url}">
 <item layout="2">
  <title>{title}</title>
        <summary>{content}</summary>
        <picture cover="{pic_url}"/>
 </item>
</msg>'''
        return Xml(template)

class MessageChain:
    def __init__(self, message_list: Sequence[Element], no_interval=False, no_charge=False) -> None:
        self.root = message_list
        self.no_interval = no_interval
        self.no_charge = no_charge

    def asDisplay(self) -> str:
        return "".join(i.asDisplay() for i in self.root)

    def get(self, t, ignore_forawrd=False, forward_layer=-1):
        res = []
        for item in self.root:
            if isinstance(item, t):
                res.append(item)
            elif isinstance(item, ForwardMessage) and not ignore_forawrd and forward_layer != 0:
                res += item.get(t, forward_layer=forward_layer-1)
        return res

    def get_quote(self) -> Optional[int]:
        quotes = self.get(Quote)
        return quotes[0].id if quotes else None # type:ignore

    @staticmethod
    def create(message_list: List, no_interval=False, no_charge=False) -> "MessageChain":
        return MessageChain(message_list, no_interval, no_charge)
    
    @staticmethod
    def plain(text: str, no_interval=False, quote=None, no_charge=False) -> "MessageChain":
        if quote:
            return MessageChain([quote, Plain(text)], no_interval=no_interval)
        return MessageChain([Plain(text)], no_interval=no_interval, no_charge=no_charge)
    
    def __add__(self, message: "MessageChain") -> "MessageChain":
        return MessageChain(self.root + message.root, no_interval=self.no_interval) # type: ignore

    def __repr__(self) -> str:
        return repr(self.root)
    
    def to_dict(self) -> dict:
        return {"root": [x.to_dict() for x in self.root], "no_interval": self.no_interval}
    
    @staticmethod
    def to_mirai(
        message: 'MessageChain',
        length_limit: int = 0,
        depth_limit = 3,
    ) -> List:
        message_list = []
        for item in message.root:
            if isinstance(item, Plain):
                message_list.append({
                    "type": "Plain",
                    "text": item.text
                })
            elif isinstance(item, Quote):
                message_list.append({
                    "type": "Quote",
                    "id": item.id,
                    "groupId": item.group_id,
                    "senderId": item.sender_id,
                    "targetId": item.target_id,
                    "origin": MessageChain.to_mirai(item.message, length_limit=length_limit, depth_limit=depth_limit-1) if depth_limit > 0 else [{
                        "type": "Plain",
                        "text": "[引用消息]"
                    }],
                })
            elif isinstance(item, Image):
                if item.url:
                    message_list.append({
                        "type": "Image",
                        "url": item.url,
                    })
                else:
                    message_list.append({
                        "type": "Image",
                        "base64": item.getBase64(),
                    })
            elif isinstance(item, At):
                message_list.append({
                    "type": "At",
                    "target": item.target,
                })
            elif isinstance(item, AtAll):
                message_list.append({
                    "type": "AtAll",
                })
            elif isinstance(item, ForwardMessage):
                if depth_limit > 0:
                    message_list.append({
                        "type": "Forward",
                        "display": {
                            "title": "聊天记录",
                            "brief": "[聊天记录]",
                            "source": "聊天记录",
                            "preview": [
                                x["message"].asDisplay()
                                for x in item.node_list[:4]
                            ],
                            "summary": f"查看{len(item.node_list)}条转发消息"
                        },
                        "nodeList": [
                            {
                                "senderId": int(x["sender"]),
                                "time": int(x["time"]),
                                "senderName": x["senderName"],
                                "messageChain": MessageChain.to_mirai(x["message"], length_limit=length_limit, depth_limit=depth_limit-1),
                            }
                            for x in item.node_list
                        ]
                    })
                else:
                    message_list.append({
                        "type": "Plain",
                        "text": "[转发消息]"
                    })
            elif isinstance(item, Xml):
                message_list.append({
                    "type": "Xml",
                    "xml": item.xml,
                })

        if length_limit:
            return message_list[:length_limit]
        else:
            return message_list


def json_to_msg(msg: Union[str, List[dict], dict]) -> MessageChain:
    if isinstance(msg, list):
        tmp_message = MessageChain([])
        for m in msg:
            tmp_message += json_to_msg(m)
        return tmp_message
    elif isinstance(msg, str):
        return MessageChain.plain(msg)
    elif isinstance(msg, dict):
        if msg["type"] == "text":
            return MessageChain([Plain(msg["content"])])
        elif msg["type"] == "image":
            return MessageChain([Image(base64=msg["content"])])
        elif msg["type"] == "image_url":
            return MessageChain([Image(url=msg["content"])])
        elif msg["type"] == "forward":
            '''
            {
                'type': 'forward',
                'title': 'optional',
                'brief': 'optional',
                'content': [{
                    'sender': 'name',
                    'content': [{#messageChain#}]
                }]
            }
            '''
            res = ForwardMessage.get_quick_forward_message([
                (0, x['sender'], json_to_msg(x['content']))
                for x in msg["content"]],
                forward_name=msg.get("title", "转发消息"),
                forward_brief=msg.get("brief", "转发消息")
            )
            return res
        elif msg["type"] == "at":
            return MessageChain([At(int(msg["content"]))])
        else:
            return MessageChain.plain("[未知消息类型]")
    else:
        return MessageChain.plain("[未知消息类型]")
