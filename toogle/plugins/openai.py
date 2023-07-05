import datetime
import json
import math
import re
import requests
import time
from requests.exceptions import ReadTimeout

from toogle.configs import config, interval_limiter
from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack
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
    trigger = r"^\.gpt(\[.*?\]|)(all|context|bill|)\s(.*)"
    thread_limit = True
    readme = "OpenAI GPT-4 模型对话，使用例：\n.gpt 你好\n.gpt[JK] 你好"
    interval = 600
    message_length_limit = 1000

    async def ret(self, message: MessagePack) -> MessageChain:
        match_group = re.match(self.trigger, message.message.asDisplay())
        if not match_group:
            raise Exception("误触发")
        setting = match_group.group(1)
        extra = match_group.group(2)
        message_content = match_group.group(3)

        max_time, context_content = 45, []
        if extra=='all':
            max_time = 600
        elif extra=='bill':
            return MessageChain.plain(GetOpenAIConversation.get_openai_usage())

        if setting:
            setting = setting[1:-1]
            if setting not in default_settings:
                return MessageChain.plain(f"预设[{setting}]场景不存在，请使用以下场景：{'、'.join(default_settings.keys())}", no_interval=True)

        if len(message_content) > self.message_length_limit:
            return MessageChain.plain(f"请求字数超限：{len(message_content)} > {self.message_length_limit}", no_interval=True)

        try:
            # res = GetOpenAIConversation.get_completion(message_content)
            res = GetOpenAIConversation.get_chat_stream(
                message_content,
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
    def get_chat_stream(text: str, max_time=30, settings: str = "", model="gpt-4") -> str:
        path = "/chat/completions"
        body = {
            "model": model,
            "messages": [{"role": "user", "content": text}],
            "stream": True,
        }
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
        res = requests.get(url + path, headers=header, timeout=30, proxies=proxies).json()
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

        res_text += f"Total: {total_usage/100:.2f} usd\n"

        return res_text
