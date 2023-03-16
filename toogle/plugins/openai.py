import json
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
    "傲娇": "你是一名可爱的女生，对提问者有好感，但是尽量在回答中包含娇羞的否定语气",
    "DM": "你是一局龙与地下城游戏的主持人",
    "大黄狗": "你是一只金毛巡回犬，在回答中时不时的插入“汪汪”这样的拟声词，或是类似“[兴奋的摇摇尾巴]”这样的动作词",
    "OP": "你是一名狂热原神玩家，无论提问内容为何，请在回答中尽量表现出对原神的赞美与对其他游戏的不屑",
    "孙笑川": "无论提问如何，请在回答中尽量多的使用emoji来表达意思，并表现出尖酸刻薄阴阳怪气",
}

class GetOpenAIConversation(MessageHandler):
    name = "OpenAI对话"
    trigger = r"^\.gpt(\[.*?\]|)\s(.*)"
    thread_limit = True
    readme = "OpenAI gpt-3.5-turbo 模型对话，使用例：\n.gpt 你好\n.gpt[JK] 你好"
    interval = 120

    async def ret(self, message: MessagePack) -> MessageChain:
        match_group = re.match(self.trigger, message.message.asDisplay())
        if not match_group:
            raise Exception("误触发")
        setting = match_group.group(1)
        message_content = match_group.group(2)

        if setting:
            setting = setting[1:-1]
            if setting not in default_settings:
                return MessageChain.plain(f"预设[{setting}]场景不存在，请使用以下场景：{'、'.join(default_settings.keys())}")

        try:
            # res = GetOpenAIConversation.get_completion(message_content)
            res = GetOpenAIConversation.get_chat_stream(
                message_content,
                settings=default_settings.get(setting, '')
            )
            return MessageChain.plain(res)
        except ReadTimeout as e:
            return MessageChain.plain("请求OpenAI GPT模型超时，请稍后尝试")
        except Exception as e:
            # return MessageChain.plain(f"出现错误: {repr(e)}")
            return MessageChain.plain(f"OpenAI GPT模型服务可能出错，请稍后尝试")

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
        res = requests.post(url + path, headers=header, json=body, timeout=15, proxies=proxies)
        try:
            return res.json()["choices"][0]["text"].strip()
        except Exception as e:
            return res.text

    @staticmethod
    def get_chat(text: str) -> str:
        path = "/chat/completions"
        body = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": text}]
        }
        res = requests.post(url + path, headers=header, json=body, timeout=15, proxies=proxies)
        try:
            return res.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return res.text

    @staticmethod
    def get_chat_stream(text: str, max_time=10, settings: str = "") -> str:
        path = "/chat/completions"
        body = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": text}],
            "stream": True,
        }
        if settings:
            body['messages'] = [{"role": "system", "content": settings}] + body['messages']

        res = requests.post(url + path, headers=header, json=body, proxies=proxies, stream=True, timeout=5)
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
