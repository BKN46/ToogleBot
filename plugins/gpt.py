import asyncio
import datetime
import json
import random
import re
from typing import Any, List, Optional, Union
import requests
import time
from requests.exceptions import ReadTimeout

from configs import config
from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MESSAGE_HISTORY, MessageHandler, MessagePack, ActiveHandler
from toogle.adapter import bot_send_message
from toogle.logger import logger
from tools import web_search
from toogle.llm_adapter import LLMError, llm


# DeepSeek's current official model catalog exposes the vision preview as ``-exp``.
DEEPSEEK_WEB_MODEL = "deepseek-v4-flash-vision-exp"
DEEPSEEK_WEB_URL = "https://api.deepseek.com"


class SearchExecutionError(RuntimeError):
    """Raised when the web-search tool cannot obtain usable results."""

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
    
    @staticmethod
    def parse_msg_chain(message_chain: MessageChain) -> List[dict]:
        res = []
        for el in message_chain.root:
            if isinstance(el, Plain):
                res.append({"type": "text", "text": el.asDisplay()})
            elif isinstance(el, Image):
                res.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{el.getBase64()}" }})
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
            return MessageChain.plain(
                f"请求字数超限：{len(message_content)} > {self.message_length_limit}",
                no_interval=True,
                no_charge=True,
            )

        max_time, context_content = 45, []
        if extra=='all':
            max_time = 600

        pics = message.message.get(Image)
        if pics:
            return MessageChain.plain(
                "deepseek暂不支持多模态对话",
                quote=message.as_quote(),
                no_interval=True,
                no_charge=True,
            )
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
                return MessageChain.plain(
                    "无记录聊天历史",
                    no_interval=True,
                    no_charge=True,
                )
            context_content = GetOpenAIConversation.parse_history_context(history_context)
        else:
            model = config.get("GPTModel", "")

        if setting:
            setting = setting[1:-1]
            if setting not in default_settings:
                return MessageChain.plain(
                    f"预设[{setting}]场景不存在，请使用以下场景："
                    f"{'、'.join(default_settings.keys())}",
                    no_interval=True,
                    no_charge=True,
                )

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
        except ReadTimeout:
            return MessageChain.plain(
                "请求OpenAI GPT模型超时，请稍后尝试",
                no_interval=True,
                no_charge=True,
            )
        except Exception:
            return MessageChain.plain(
                "OpenAI GPT模型服务可能出错，请稍后尝试",
                no_interval=True,
                no_charge=True,
            )

    @staticmethod
    def get_completion(
        text: str,
        model="gpt-4",
        url = "https://api.openai.com/v1",
    ) -> str:
        return llm.completion(text, provider=config.get("LLM_DEFAULT_PROVIDER", "moonshot"), model=model, url=url)

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
        other_params = {},
    ) -> str:
        return llm.chat(text, provider=config.get("LLM_DEFAULT_PROVIDER", "moonshot"), model=model, url=url, settings=settings,
                        other_history=other_history, tools=tools, json_output=json_output,
                        raw_output=raw_output, other_params=other_params)

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
        return llm.chat_stream(text, provider=config.get("LLM_DEFAULT_PROVIDER", "moonshot"), model=model, url=url,
                               settings=settings, other_history=other_history,
                               max_tokens=max_tokens, max_time=max_time, tools=tools)

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
        yield from llm.stream_logic_chain(
            text,
            provider="deepseek",
            model=model,
            url=url,
            api_key=api_key,
            settings=settings,
            other_history=other_history,
            max_tokens=max_tokens,
            max_time=max_time,
            tools=tools,
        )


    @staticmethod
    def get_web_search(
        text: Union[str, list],
        model=DEEPSEEK_WEB_MODEL,
        settings="请解答以下内容，结果精简在500字以内，不要使用markdown格式",
        url=DEEPSEEK_WEB_URL,
        api_key=None,
        include_source=False,
    ):
        tools = [{
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web and return current, sourced results.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "Search query"}},
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        }, {
            "type": "function",
            "function": {
                "name": "open_url",
                "description": "Open a public HTTP(S) search result and extract readable text for verification.",
                "parameters": {
                    "type": "object",
                    "properties": {"url": {"type": "string", "description": "Public result URL"}},
                    "required": ["url"],
                    "additionalProperties": False,
                },
            },
        }]
        api_key = api_key or config.get("GPTSecretDeepseek") or config.get("GPTSecret")
        messages = llm._messages(text, settings)
        def execute(name: str, arguments: dict[str, Any]):
            value = arguments.get("query" if name == "web_search" else "url") if isinstance(arguments, dict) else None
            if name not in {"web_search", "open_url"} or not isinstance(value, str) or not value.strip():
                return {"error": "invalid tool arguments"}, ""
            try:
                if name == "web_search":
                    result = web_search.search(value)
                    return result.as_dict(), web_search.provider_label(result.provider)
            except (web_search.WebSearchError, requests.exceptions.RequestException) as exc:
                logger.warning("web search tool failed: error_type=%s", type(exc).__name__)
                raise SearchExecutionError("web search failed") from exc
            try:
                return web_search.open_url(value), ""
            except (web_search.WebSearchError, requests.exceptions.RequestException) as exc:
                # Page verification is optional; preserve search evidence and
                # let the model finish instead of turning a page timeout into
                # a failed paid command.
                logger.warning("web page fetch failed: error_type=%s", type(exc).__name__)
                return {"error": "page fetch unavailable"}, ""
        content, providers = llm.tool_loop(
            messages,
            tools,
            execute,
            provider="deepseek",
            model=model,
            url=url,
            api_key=api_key,
            max_rounds=3,
        )
        if include_source and providers and content:
            content = f"{content.rstrip()}\n\n[通过{'、'.join(dict.fromkeys(providers))}搜索]"
        return content


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
        enabled = str(config.get("ACTIVE_AI_ENABLED", "")).lower()
        if enabled not in {"1", "true", "yes"}:
            return False
        message_content = message.message.asDisplay() if message else ""
        if random.random() < 0.005:
            logger.info(f"Triggered [{self.name}]")  # type: ignore
            return True
        elif len(message_content) < 5:
            return False
        elif "大黄狗" in message_content and random.random() < 0.15:
            logger.info(f"Triggered [{self.name}]")  # type: ignore
            return True
        elif message_content[-1] in ["?", "？", "吗", "嘛", "呢"] and random.random() < 0.01:
            logger.info(f"Triggered [{self.name}]")  # type: ignore
            return True
        elif (message_content.startswith("什么") or message_content.startswith("怎么") or message_content.startswith("为什么")) and random.random() < 0.01:
            logger.info(f"Triggered [{self.name}]")  # type: ignore
            return True
        return False


class WhatIs(MessageHandler):
    name = "大黄狗有问必答"
    trigger = r"^查一下"
    thread_limit = True
    readme = "查一下 <问题>"
    interval = 600
    message_length_limit = 1000
    price = 12

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        content = message.message.asDisplay()
        if len(content) > self.message_length_limit:
            return MessageChain.plain(
                f"请求字数超限：{len(content)} > {self.message_length_limit}",
                no_interval=True,
                no_charge=True,
            )

        try:
            res = await asyncio.to_thread(GetOpenAIConversation.get_web_search,
                GPTContext.parse_msg_chain(message.message),
                model=config.get("DEEPSEEK_WEB_MODEL", DEEPSEEK_WEB_MODEL),
                settings="请解答以下内容，结果精简在500字以内，不要使用markdown格式",
                url=config.get("DEEPSEEK_WEB_URL", DEEPSEEK_WEB_URL),
                api_key=config.get("GPTSecretDeepseek") or config.get("GPTSecret"),
                include_source=True,
            )
            return MessageChain.plain(res, quote=message.as_quote())
        except SearchExecutionError:
            return MessageChain.plain(
                "搜索服务出错，请稍后再试",
                quote=message.as_quote(),
                no_interval=True,
                no_charge=True,
            )
        except ReadTimeout:
            return MessageChain.plain(
                "请求GPT模型超时，请稍后尝试",
                no_interval=True,
                no_charge=True,
            )
        except Exception as e:
            logger.warning("查一下 failed: error_type=%s", type(e).__name__)
            if "model token limit exceeded" in repr(e):
                bot_send_message(message, MessageChain.plain("请求GPT模型token数量超限，正在切换更大模型尝试回答...", quote=message.as_quote()))
                try:
                    res = await asyncio.to_thread(GetOpenAIConversation.get_web_search,
                        content,
                        model=config.get("DEEPSEEK_WEB_MODEL", DEEPSEEK_WEB_MODEL),
                        settings="请解答以下内容，结果精简在500字以内",
                        url=config.get("DEEPSEEK_WEB_URL", DEEPSEEK_WEB_URL),
                        api_key=config.get("GPTSecretDeepseek") or config.get("GPTSecret"),
                        include_source=True,
                    )
                    return MessageChain.plain(res, quote=message.as_quote())
                except SearchExecutionError:
                    return MessageChain.plain(
                        "搜索服务出错，请稍后再试",
                        quote=message.as_quote(),
                        no_interval=True,
                        no_charge=True,
                    )
                except ReadTimeout:
                    return MessageChain.plain(
                        "请求GPT模型超时，请稍后尝试",
                        no_interval=True,
                        no_charge=True,
                    )
                except Exception as fallback_error:
                    logger.warning("查一下 fallback failed: error_type=%s", type(fallback_error).__name__)
                    return MessageChain.plain(
                        "GPT模型服务可能出错，请稍后尝试",
                        no_interval=True,
                        no_charge=True,
                    )
            else:
                return MessageChain.plain(
                    "GPT模型服务可能出错，请稍后尝试",
                    no_interval=True,
                    no_charge=True,
                )

class AIConclude(MessageHandler):
    name = "大黄狗总结"
    trigger = r"^刚才在聊什么"
    thread_limit = True
    readme = "总结刚才的聊天内容"
    interval = 600
    price = 30
    
    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        msg = message.message.asDisplay()
        if msg != "刚才在聊什么":
            msg_list = msg.split(' ')
            try:
                start_time = datetime.datetime.strptime(msg_list[1], "%Y-%m-%d_%H:%M")
                end_time = datetime.datetime.strptime(msg_list[2], "%Y-%m-%d_%H:%M") if len(msg_list) > 1 else datetime.datetime.now()
            except Exception as e:
                return MessageChain.plain("时间格式错误，请使用类似“2023-10-01_12:00 2023-10-01_14:00”的格式", no_interval=True)
        else:
            start_time = datetime.datetime.now() - datetime.timedelta(hours=2)
            end_time = datetime.datetime.now()
        logs = [
            history_message
            for history_message in MESSAGE_HISTORY.get(message.group.id, windows=500)
            if start_time.timestamp() <= history_message.time <= end_time.timestamp()
            and history_message.id != message.id
        ]
        compressed_info = '\n'.join([
            f"{history_message.member.name}:{history_message.message.asDisplay()}"
            for history_message in logs
        ])

        if not compressed_info:
            return MessageChain.plain("指定时间内没有可总结的聊天记录", no_interval=True)

        bot_send_message(message, MessageChain.plain(f"正在总结刚才的聊天内容(约{len(compressed_info)/1.5/1000000*4:.3f}元)，请稍候...", quote=message.as_quote()))

        res = GetOpenAIConversation.get_chat(
            compressed_info,
            settings="你是一条乐于助人的大黄狗，请总结以上聊天内容，忽略掉零星发散性内容，聚焦于不同人的交互对话过程，结果精简在1000字以内",
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
