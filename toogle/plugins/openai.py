import datetime
import json
import math
import random
import re
from typing import Optional, Union
import nonebot
import requests
import time
from requests.exceptions import ReadTimeout

from toogle.configs import config, interval_limiter
from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MESSAGE_HISTORY, MessageHandler, MessagePack, ActiveHandler
from toogle.sql import DatetimeUtils, SQLConnection

api_key = config.get("OpenAISecret")
header = {"Authorization": f"Bearer {api_key}"}
url = "https://api.openai.com/v1"

proxies = {
    'http': config.get('REQUEST_PROXY_HTTP', ''),
    'https': config.get('REQUEST_PROXY_HTTPS', ''),
}

default_settings = {
    "JK": "你是一名日本女高中生，请使用调皮可爱的语气回答",
    "雌小鬼": "你是一名年龄较小的可爱女生，请使用带着尖酸的语气、阴阳怪气地回答，尽量在回答中包含对提问者的否定",
    "辣妹": "请使用日本高中辣妹的语气回答",
    "病娇": "你是一名心理病态的女生，对提问者有着无条件狂热的好感，并表现出丧失理智、妒忌与控制欲",
    "傲娇": "你是一名可爱的女生，对提问者有好感，但是请在回答中包含娇羞的否定语气",
    "DM": "你是一局龙与地下城游戏的主持人",
    "大黄狗": "你是一只金毛巡回犬，在回答中不断插入“汪汪”这样的拟声词，或是类似“[兴奋的摇摇尾巴]”这样的动作词",
    "OP": "你是一名狂热原神玩家，无论提问内容为何，都在回答中尽量表现出对原神的赞美与对其他游戏的不屑",
    "孙笑川": "你是孙笑川，无论提问如何，请在回答中尽量多的使用包含中文谐音的emoji来表达意思，并表现出尖酸刻薄阴阳怪气",
    "midjourney": "You will generate a stills image description exactly as instructed by me.\n\n- you will write the description in one long line without using line breaks.\n\nThe concept of the image I will send you later\n\n, start first with a headline - \"Prompt [number]:\", then in a new line start the description with the phrase \"/imagine prompt:\" then continue by mentioning the concept and fluently attach it to an art form, then choose an artist from your data bank as a matching inspiration for the art form, then describe the scene in some detail but not too much, then choose the color temperature, describe facial expressions if there are any in the image, then choose the lighting, and atmosphere. all the descriptions should not take more than 5 lines of text.\n\nArt forms to choose from:\nPhotography, Illustration, watercolor, oil painting, comics, Pixar 3D, digital illustration\n\n- If the art form is photography, you will choose a lens size (for example 35mm) \n\n- you will generate 3 different descriptions in 6 different art forms and styles\n\n- you will end each description with the phrase \"--v 5 --stylize 1000\"\n\n- you will wait for your next concept OR a request for more descriptions for the same concept\n\n- the description will be in English, text given later I will give you in the next paragraph",
}


class GPTContext:
    content = []

    def __init__(self, settings: str = "") -> None:
        if settings:
            self.content.append({"role": "system", "content": settings})

    def add_user_talk(self, text):
        self.content.append({"role": "user", "content": text})

    def add_gpt_reply(self, text):
        self.content.append({"role": "assistant", "content": text})

    def json(self):
        return json.dumps(self.content, indent=2, ensure_ascii=False)
    
    @staticmethod
    def from_json(json_text):
        res = GPTContext()
        res.content = json.loads(json_text)
        return res


class GetOpenAIConversation(MessageHandler):
    name = "OpenAI对话"
    trigger = r"^\.gpt(\[.*?\]|)(all|context|bill|\+|)\s(.*)"
    thread_limit = True
    to_me_trigger = True
    readme = "OpenAI GPT-4 模型对话，使用例：\n.gpt 你好\n.gpt[JK] 你好"
    interval = 600
    message_length_limit = 1000

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        return MessageChain.plain("成本原因，大黄狗GPT暂时关闭")
        match_group = re.match(self.trigger, message.message.asDisplay())
        if not match_group:
            if message.group.id == 0:
                return
            elif message.quote:
                return
            setting = ""
            extra = ""
            message_content = message.message.asDisplay()
        else:
            setting = match_group.group(1)
            extra = match_group.group(2)
            message_content = match_group.group(3)

        if len(message_content) > self.message_length_limit:
            return MessageChain.plain(f"请求字数超限：{len(message_content)} > {self.message_length_limit}", no_interval=True)

        max_time, context_content = 45, []
        if extra=='all':
            max_time = 600
        elif extra=='bill':
            return MessageChain.plain(GetOpenAIConversation.get_openai_usage())

        pics = message.message.get(Image)
        if pics:
            model = "gpt-4-vision-preview"
            message_content = [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{x.getBase64()}" }} if isinstance(x, Image) 
                else {"type": "text", "text": x.asDisplay()}
                for x in message.message.root
            ]
        elif extra=="+":
            model = "gpt-4-1106-preview"
            history_context = MESSAGE_HISTORY.get(message.group.id)
            if not history_context:
                return MessageChain.plain("无记录聊天历史", no_interval=True)
            context_content = GetOpenAIConversation.parse_history_context(history_context)
        else:
            model = "gpt-4-1106-preview"

        if setting:
            setting = setting[1:-1]
            if setting not in default_settings:
                return MessageChain.plain(f"预设[{setting}]场景不存在，请使用以下场景：{'、'.join(default_settings.keys())}", no_interval=True)

        try:
            # res = GetOpenAIConversation.get_completion(message_content)
            res = GetOpenAIConversation.get_chat_stream(
                message_content,
                model=model,
                other_history=context_content,
                max_time=max_time,
                settings=default_settings.get(setting, '')
            )
            return MessageChain.plain(res)
        except ReadTimeout as e:
            return MessageChain.plain("请求OpenAI GPT模型超时，请稍后尝试", no_interval=True)
        except Exception as e:
            # return MessageChain.plain(f"出现错误: {repr(e)}")
            return MessageChain.plain(f"OpenAI GPT模型服务可能出错，请稍后尝试\n{repr(e)}", no_interval=True)

    @staticmethod
    def get_completion(text: str) -> str:
        path = "/completions"
        text = f"You: {text}\nAssistant: "
        body = {
            "model": "text-davinci-003",
            "prompt": text,
            "max_tokens": 512,
            "temperature": 0.5,
            "top_p": 1,
            "n": 1,
            "stream": False,
            "logprobs": None,
            "stop": "You: ",
        }
        res = requests.post(url + path, headers=header, json=body, timeout=15, proxies=proxies, verify=False)
        try:
            return res.json()["choices"][0]["text"].strip()
        except Exception as e:
            return res.text

    @staticmethod
    def get_chat(text: str, model="gpt-4") -> str:
        path = "/chat/completions"
        body = {
            "model": model,
            "messages": [{"role": "user", "content": text}]
        }
        res = requests.post(url + path, headers=header, json=body, timeout=15, proxies=proxies, verify=False)
        try:
            return res.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return res.text

    @staticmethod
    def get_chat_stream(text: Union[str, list], max_time=30, settings: str = "", other_history: list = [], model="gpt-4", max_tokens=1000) -> str:
        path = "/chat/completions"
        body = {
            "model": model,
            "messages": [{"role": "user", "content": text}],
            "stream": True,
            "max_tokens": max_tokens,
        }

        if other_history:
            body['messages'] = [{"role": "user", "content": x} for x in other_history] + body['messages']
        if settings:
            body['messages'] = [{"role": "system", "content": settings}] + body['messages']

        res = requests.post(url + path, headers=header, json=body, proxies=proxies, stream=True, timeout=5, verify=False)
        res_text = ''
        start_time = time.time()
        for line in res.iter_lines():
            # filter out keep-alive new lines
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data:") and not decoded_line.endswith("[DONE]"):
                    data = json.loads(decoded_line[5:].strip())
                    if 'content' in data['choices'][0]['delta']:
                        res_text += data['choices'][0]['delta']['content']
            if time.time() - start_time > max_time:
                res_text += "\n[由于时长限制后续生成直接截断]"
                break
        return res_text.strip()

    @staticmethod
    def get_openai_usage(day_count=30):
        date_now = datetime.datetime.now()
        end_date = date_now.strftime("%Y-%m-%d")
        start_date = (date_now - datetime.timedelta(days=day_count)).strftime("%Y-%m-%d")
        path = f"/dashboard/billing/usage?end_date={end_date}&start_date={start_date}"
        res = requests.get("https://api.openai.com" + path, headers=header, timeout=30, proxies=proxies).json()
        total_usage = res['total_usage']
        daily_cost = [
            sum([x['cost'] for x in day['line_items']])
            for day in res['daily_costs']
        ]

        res_text = ""
        max_day, max_length = 300, 15
        for i, cost in enumerate(daily_cost):
            day_length = math.ceil(min(cost, max_day) / max_day * max_length)
            day = (date_now - datetime.timedelta(days=day_count-i)).strftime("%Y-%m-%d")
            res_text += f"{day} ${cost/100:<6.2f} {'#' * day_length}\n"

        res_text += f"Total: {total_usage/100:.2f} usd\n\n"

        res = requests.get("https://api.openai.com/dashboard/billing/invoices?system=api", headers=header, timeout=30, proxies=proxies).json()
        for invoices in res['data'][:3]:
            time_str = datetime.datetime.fromtimestamp(invoices['created_at']).strftime("%Y-%m-%d")
            res_text += f"Invoice: {time_str} ${invoices['total']/100:.2f}\n"

        return res_text


    @staticmethod
    def parse_history_context(history: list[MessagePack]) -> list:
        # return [
        #     [{"type": "text", "text": f"{m.member.name}: "}] + [
        #         {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{x.compress(max_height=400,max_width=400).getBase64()}" }}
        #         if isinstance(x, Image) 
        #         else {"type": "text", "text": x.asDisplay()}
        #         for x in m.message.root
        #     ] if m.message.get(Image)
        #     else f"{m.member.name}: {m.message.asDisplay()}"
        #     for m in history
        # ]
        return ["\n".join([f"{x.member.name}: {x.message.asDisplay()}" for x in history])]


class ActiveAIConversation(ActiveHandler):
    name = "OpenAI主动加入聊天"
    trigger = r""
    readme = "OpenAI主动加入聊天"
    white_list = False
    thread_limit = False
    trigger_rate = 0.01
    interval = 0

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        history_context = MESSAGE_HISTORY.get(message.group.id, windows=7)
        if not history_context:
            return
    
        context_content = GetOpenAIConversation.parse_history_context(history_context)

        pics = message.message.get(Image)
        if pics:
            model = "gpt-4-vision-preview"
            message_content = [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{x.getBase64()}" }} if isinstance(x, Image) 
                else {"type": "text", "text": x.asDisplay()}
                for x in message.message.root
            ]
        else:
            model = "gpt-4-1106-preview"
            message_content = message.message.asDisplay()

        res = GetOpenAIConversation.get_chat_stream(
            message_content,
            model=model,
            other_history=context_content,
            max_time=60,
            max_tokens=150,
            settings="你是一个名叫大黄狗的智能AI，请继续话题讨论，不要介绍自己、不要使用语气词、不要提问题，保持简洁自然亲切友善，使用粤语，100字以内"
        )
        return MessageChain.plain(res)


    def is_trigger_random(self, message: Optional[MessagePack] = None):
        return False
        message_content = message.message.asDisplay() if message else ""
        if random.random() < 0.003:
            nonebot.logger.success(f"Triggered [{self.name}]")  # type: ignore
            return True
        elif len(message_content) < 5:
            return False
        elif "大黄狗" in message_content and random.random() < 0.15:
            nonebot.logger.success(f"Triggered [{self.name}]")  # type: ignore
            return True
        elif message_content[-1] in ["?", "？", "吗", "嘛", "呢"] and random.random() < 0.01:
            nonebot.logger.success(f"Triggered [{self.name}]")  # type: ignore
            return True
        elif (message_content.startswith("什么") or message_content.startswith("怎么") or message_content.startswith("为什么")) and random.random() < 0.01:
            nonebot.logger.success(f"Triggered [{self.name}]")  # type: ignore
            return True
        return False
