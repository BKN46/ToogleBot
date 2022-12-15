import requests
from requests.exceptions import ReadTimeout

from toogle.configs import config, interval_limiter
from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack
from toogle.sql import DatetimeUtils, SQLConnection

api_key = config.get("OpenAISecret")
header = {"Authorization": f"Bearer {api_key}"}
url = "https://api.openai.com/v1"


class GetOpenAIConversation(MessageHandler):
    name = "OpenAI对话"
    trigger = r"^.gpt\s"
    thread_limit = True
    readme = "OpenAI text-davinci-003 自然语言模型对话"

    async def ret(self, message: MessagePack) -> MessageChain:
        message_content = message.message.asDisplay()[4:].strip()
        try:
            res = GetOpenAIConversation.get_completion(message_content)
            return MessageChain.plain(res)
        except ReadTimeout as e:
            return MessageChain.plain("请求OpenAI GPT模型超时，请稍后尝试")
        except Exception as e:
            return MessageChain.plain(f"出现错误: {repr(e)}")

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
        res = requests.post(url + path, headers=header, json=body, timeout=10)
        try:
            return res.json()["choices"][0]["text"].strip()
        except Exception as e:
            return res.text
