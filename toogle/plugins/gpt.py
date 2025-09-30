import datetime
import json
import math
import random
import re
from typing import List, Optional, Tuple, Union
import nonebot
import requests
import time
from requests.exceptions import ReadTimeout

from toogle.configs import config, interval_limiter
from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MESSAGE_HISTORY, MessageHandler, MessagePack, ActiveHandler
from toogle.nonebot2_adapter import bot_send_message
from toogle.sql import DatetimeUtils, SQLConnection
from toogle.utils import read_chat_log

api_key = config.get("GPTSecret")
header = {"Authorization": f"Bearer {api_key}"}

proxies = {
    # 'http': config.get('REQUEST_PROXY_HTTP', ''),
    # 'https': config.get('REQUEST_PROXY_HTTPS', ''),
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
    # to_me_trigger = True
    readme = "GPT 模型对话，使用例：\n.gpt 你好\n.gpt[JK] 你好"
    interval = 600
    message_length_limit = 1000
    price = 5

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
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

        pics = message.message.get(Image)
        if pics:
            return MessageChain.plain("deepseek暂不支持多模态对话", quote=message.as_quote(), no_interval=True)
            model = config.get("GPTModel", "")
            message_content = [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{x.getBase64()}" }} if isinstance(x, Image) 
                else {"type": "text", "text": x.asDisplay()}
                for x in message.message.root
            ]
        elif extra=="+":
            model = config.get("GPTModel", "")
            history_context = MESSAGE_HISTORY.get(message.group.id)
            if not history_context:
                return MessageChain.plain("无记录聊天历史", no_interval=True)
            context_content = GetOpenAIConversation.parse_history_context(history_context)
        else:
            model = config.get("GPTModel", "")

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
                settings=default_settings.get(setting, ''),
                url=config.get("GPTUrl", ""),
            )
            return MessageChain.plain(res, quote=message.as_quote())
        except ReadTimeout as e:
            return MessageChain.plain("请求OpenAI GPT模型超时，请稍后尝试", no_interval=True)
        except Exception as e:
            # return MessageChain.plain(f"出现错误: {repr(e)}")
            return MessageChain.plain(f"OpenAI GPT模型服务可能出错，请稍后尝试\n{repr(e)}", no_interval=True)

    @staticmethod
    def get_completion(
        text: str,
        model="gpt-4",
        url = "https://api.openai.com/v1",
    ) -> str:
        path = "/completions"
        text = f"You: {text}\nAssistant: "
        body = {
            "model": model,
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
    def get_chat(
        text: str,
        json_output: bool=False,
        raw_output: bool=False,
        settings: str = "",
        other_history: list = [],
        model="gpt-4",
        url = "https://api.openai.com/v1",
        tools = [],
    ) -> str:
        path = "/chat/completions"
        body = {
            "model": model,
            "messages": [{"role": "user", "content": text}]
        }
        if tools:
            body['tools'] = tools

        if other_history:
            body['messages'] = [({"role": "user", "content": x} if isinstance(x, str) else x) for x in other_history] + (body['messages'] if text else [])
        if settings:
            body['messages'] = [{"role": "system", "content": settings}] + body['messages']
        if json_output:
            body['response_format'] = {"type": "json_object"}
        res = requests.post(url + path, headers=header, json=body, timeout=60, proxies=proxies, verify=False)
        try:
            if raw_output:
                return res.json()
            else:
                return res.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return res.text

    @staticmethod
    def get_chat_stream(
        text: Union[str, list],
        max_time=30,
        settings: str = "",
        other_history: list = [],
        model="gpt-4",
        max_tokens=1000,
        url = "https://api.openai.com/v1",
        tools = [],
    ) -> str:
        path = "/chat/completions"
        body = {
            "model": model,
            "messages": [{"role": "user", "content": text}],
            "stream": True,
            "max_tokens": max_tokens,
        }
        if tools:
            body['tools'] = tools

        if other_history:
            body['messages'] = [({"role": "user", "content": x} if isinstance(x, str) else x) for x in other_history] + body['messages']
        if settings:
            body['messages'] = [{"role": "system", "content": settings}] + body['messages']

        res = requests.post(url + path, headers=header, json=body, proxies=proxies, stream=True, timeout=15, verify=False)
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
                elif decoded_line.endswith("[DONE]"):
                    break
            if time.time() - start_time > max_time:
                res_text += "\n[由于时长限制后续生成直接截断]"
                break
        return res_text.strip()

    @staticmethod
    def get_chat_stream_logic_chain(
        text: Union[str, list],
        max_time=30,
        settings: str = "",
        other_history: list = [],
        model="deepseek-r1",
        max_tokens=1000,
        url = "https://api.openai.com/v1",
        tools = [],
        api_key = config.get("GPTSecret"),
    ):
        path = "/chat/completions"
        body = {
            "model": model,
            "messages": [{"role": "user", "content": text}],
            "stream": True,
            "max_tokens": max_tokens,
        }
        if tools:
            body['tools'] = tools

        if other_history:
            body['messages'] = [({"role": "user", "content": x} if isinstance(x, str) else x) for x in other_history] + body['messages']
        if settings:
            body['messages'] = [{"role": "system", "content": settings}] + body['messages']

        reason_text = ''
        res_text = ''
        total_text = ''
        error = ''
        usage = 0
        start_time = time.time()

        header = {"Authorization": f"Bearer {api_key}"}
        res = requests.post(url + path, headers=header, json=body, proxies=proxies, stream=True, timeout=15, verify=False)
        for line in res.iter_lines():
            # filter out keep-alive new lines
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data:") and not decoded_line.endswith("[DONE]"):
                    data = json.loads(decoded_line[5:].strip())
                    if 'reasoning_content' in data['choices'][0]['delta']:
                        reason_text += data['choices'][0]['delta']['reasoning_content']
                        total_text += data['choices'][0]['delta']['reasoning_content']
                    if 'content' in data['choices'][0]['delta']:
                        res_text += data['choices'][0]['delta']['content']
                        total_text += data['choices'][0]['delta']['content']
                    if 'usage' in data:
                        usage = data['usage']['total_tokens']
                elif 'error' in decoded_line:
                    error = json.loads(decoded_line)['error']['message']
            if time.time() - start_time > max_time:
                res_text += "\n[由于时长限制后续生成直接截断]"
                break

            if '\n\n' in total_text:
                yield_content = total_text.split('\n\n')[:-1]
                total_text = total_text.split('\n\n')[-1]
                for content in yield_content:
                    yield {
                        'yield': content,
                        'usage': usage,
                        'error': error,
                        'is_res': len(res_text) > 0,
                    }

        yield {
            'yield': total_text,
            'reason': reason_text.strip(),
            'res': res_text.strip(),
            'usage': usage,
            'error': error,
            'use_time': (time.time() - start_time) * 1000,
        }


    @staticmethod
    def get_web_search(
        text: str,
        model="gpt-4",
        settings = "你是一条乐于助人的大黄狗",
        url = "https://api.openai.com/v1",
    ):
        messages = [
            {"role": "system", "content": settings},
        ]
        messages.append({
            "role": "user",
            "content": text
        })
        finish_reason = None
        while finish_reason is None or finish_reason == "tool_calls":
            choice = GetOpenAIConversation.get_chat( # type: ignore
                '',
                other_history=messages,
                model=model,
                raw_output=True,
                url=url,
                tools=[
                    {
                        "type": "builtin_function",
                        "function": {
                            "name": "$web_search",
                        },
                    }
                ]
            )
            if 'choices' not in choice:
                if 'Your request exceeded model token limit' in choice.get('error', {}).get('message', ''):
                    raise Exception(f"Error: model token limit exceeded: {choice['error']}")
                raise Exception(f"Error: unable to find choices in response: {json.dumps(choice, ensure_ascii=False)}")
            choice: dict = choice['choices'][0]
            finish_reason = choice['finish_reason']
            if finish_reason == "tool_calls":  # <-- 判断当前返回内容是否包含 tool_calls
                messages.append(choice['message'])  # <-- 我们将 Kimi 大模型返回给我们的 assistant 消息也添加到上下文中，以便于下次请求时 Kimi 大模型能理解我们的诉求
                for tool_call in choice['message']['tool_calls']:  # <-- tool_calls 可能是多个，因此我们使用循环逐个执行
                    tool_call_name = tool_call['function']['name']
                    tool_call_arguments = json.loads(tool_call['function']['arguments'])  # <-- arguments 是序列化后的 JSON Object，我们需要使用 json.loads 反序列化一下
                    if tool_call_name == "$web_search":
                        tool_result = tool_call_arguments
                    else:
                        tool_result = f"Error: unable to find tool by name '{tool_call_name}'"
    
                    # 使用函数执行结果构造一个 role=tool 的 message，以此来向模型展示工具调用的结果；
                    # 注意，我们需要在 message 中提供 tool_call_id 和 name 字段，以便 Kimi 大模型
                    # 能正确匹配到对应的 tool_call。
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call['id'],
                        "name": tool_call_name,
                        "content": json.dumps(tool_result),  # <-- 我们约定使用字符串格式向 Kimi 大模型提交工具调用结果，因此在这里使用 json.dumps 将执行结果序列化成字符串
                    })
    
        return choice['message']['content']


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
            settings="请继续话题讨论，不要介绍自己、不要使用语气词、不要提问题，保持简洁自然亲切，使用地道北京话，100字以内"
        )
        return MessageChain.plain(res)


    def is_trigger_random(self, message: Optional[MessagePack] = None):
        return False
        message_content = message.message.asDisplay() if message else ""
        if random.random() < 0.005:
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


class WhatIs(MessageHandler):
    name = "大黄狗有问必答"
    trigger = r"^什么是|^查一下|^DS |^DSR "
    thread_limit = True
    readme = "什么是什么"
    interval = 600
    message_length_limit = 1000
    price = 12

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        content = message.message.asDisplay()
        if len(content) > self.message_length_limit:
            return MessageChain.plain(f"请求字数超限：{len(content)} > {self.message_length_limit}", no_interval=True)

        if content.startswith("DSR "):
            content = content[4:]
            start_output=False
            for res in GetOpenAIConversation.get_chat_stream_logic_chain(
                content,
                model="deepseek-r1",
                url="https://api.lkeap.cloud.tencent.com/v1",
                api_key=config.get("GPTSecretTencent"),
                max_time=300,
            ):
                if res['error']:
                    return MessageChain.plain(f"\n出现错误: {res['error']}", quote=message.as_quote())
                if not start_output and res['is_res']:
                    start_output = True
                    res['yield'] = f"{res['yield']}"
                bot_send_message(message, MessageChain.plain(res['yield'].strip()))
            return MessageChain.plain("对话结束", quote=message.as_quote())
        elif content.startswith("DS "):
            content = content[3:]
            final_res = {}
            for res in GetOpenAIConversation.get_chat_stream_logic_chain(
                content,
                model="deepseek-r1",
                url="https://api.lkeap.cloud.tencent.com/v1",
                api_key=config.get("GPTSecretTencent"),
                max_time=300,
            ):
                final_res = res
                if res['error']:
                    return MessageChain.plain(f"\n出现错误: {res['error']}", quote=message.as_quote())
            if not final_res['res'].strip():
                final_res['res'] = "无输出结果，以下是推理路径：\n" + final_res['reason']
            return MessageChain.plain(f"{final_res['res']}\n\n开销: {final_res['usage']}\n耗时: {final_res['use_time']:.2f}ms", quote=message.as_quote()) # type: ignore

        try:
            res = GetOpenAIConversation.get_web_search(
                content,
                model=config.get("GPTModel", ""),
                settings="请解答以下内容，结果精简在500字以内",
                url=config.get("GPTUrl", ""),
            )
            return MessageChain.plain(res, quote=message.as_quote())
        except ReadTimeout as e:
            return MessageChain.plain("请求GPT模型超时，请稍后尝试", no_interval=True)
        except Exception as e:
            if "model token limit exceeded" in repr(e):
                bot_send_message(message, MessageChain.plain("请求GPT模型token数量超限，正在切换更大模型尝试回答...", quote=message.as_quote()))
                try:
                    res = GetOpenAIConversation.get_web_search(
                        content,
                        model=config.get("GPTModelLarge", ""),
                        settings="请解答以下内容，结果精简在500字以内",
                        url=config.get("GPTUrl", ""),
                    )
                    return MessageChain.plain(res, quote=message.as_quote())
                except ReadTimeout as e:
                    return MessageChain.plain("请求GPT模型超时，请稍后尝试", no_interval=True)
                except Exception as e:
                    return MessageChain.plain(f"GPT模型服务可能出错，请稍后尝试\n{repr(e)}", no_interval=True)
            else:
                return MessageChain.plain(f"GPT模型服务可能出错，请稍后尝试\n{repr(e)}", no_interval=True)

class AIConclude(MessageHandler):
    name = "大黄狗总结"
    trigger = r"^刚才在聊什么$"
    thread_limit = True
    readme = "总结刚才的聊天内容"
    interval = 600
    price = 30
    
    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        logs = read_chat_log(
            datetime.datetime.now() - datetime.timedelta(hours=2),
            datetime.datetime.now(),
            group_id_match=str(message.group.id)
        )
        compressed_info = '\n'.join([
            f"{nickname}:{line}"
            for line_time, line, group_id, member_id, nickname in logs
        ])

        bot_send_message(message, MessageChain.plain(f"正在总结刚才的聊天内容(约{len(compressed_info)/1.5/1000000*4:.3f}元)，请稍候...", quote=message.as_quote()))

        res = GetOpenAIConversation.get_chat(
            compressed_info,
            settings="你是一条乐于助人的大黄狗，请总结以上聊天内容，忽略掉零星发散性内容，聚焦于不同人的交互对话过程，结果精简在500字以内",
            model=config.get("GPTModelLarge", ""),
            url=config.get("GPTUrl", ""),
        )
        return MessageChain.plain(res, quote=message.as_quote())

def gpt_censor(msg_list: List[Union[MessagePack, str]]):
    msg_list = [(x.message.asDisplay() if isinstance(x, MessagePack) else x) for x in msg_list]
    res = GetOpenAIConversation.get_chat(
        "",
        settings="你是一个审查机器人，对话题中的政治内容含量进行判断并输出打分（范围0-100）以及敏感内容，输出json格式为{value: #value#, sensitive_content: #sensitive_content#}",
        other_history=msg_list,
        json_output=True,
        raw_output=True,
        model="gpt-3.5-turbo-0125",
    )
    score = json.loads(res['choices'][0]['message']['content']).get("value", 0) # type: ignore
    content = json.loads(res['choices'][0]['message']['content']).get("sensitive_content", 'null') # type: ignore
    cost = res['usage']['prompt_tokens'] * 0.0000001 * 0.5 + res['usage']['completion_tokens'] * 0.0000001 * 1.5 # type: ignore
    datetime_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{datetime_str}]OpenAPI Censor usage [score: {score}] ${cost:10f}", file=open("log/openai.log", "a"))
    # print(json.dumps(res, ensure_ascii=False, indent=2))
    return score, content, cost
