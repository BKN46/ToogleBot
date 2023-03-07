import json
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

class GetOpenAIConversation(MessageHandler):
    name = "OpenAI对话"
    trigger = r"^.gpt\s"
    thread_limit = True
    readme = "OpenAI gpt-3.5-turbo 模型对话"

    async def ret(self, message: MessagePack) -> MessageChain:
        message_content = message.message.asDisplay()[4:].strip()
        try:
            # res = GetOpenAIConversation.get_completion(message_content)
            res = GetOpenAIConversation.get_chat_stream(message_content)
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
    def get_chat_stream(text: str, max_time=10) -> str:
        path = "/chat/completions"
        body = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": text}],
            "stream": True,
        }
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
