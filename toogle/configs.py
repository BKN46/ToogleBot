import nonebot
import time
import threading

interval_locker = threading.Lock()

def ini_parse(data: str):
    if data.startswith("[") and data.endswith("]"):
        return eval(data)
    return data


config = {}

def reload_config():
    global config
    config = {
        line.split("=")[0]: ini_parse(line.split("=")[1].replace("\n", ""))
        for line in open(".env", "r").readlines()
        if len(line) > 1
    }

reload_config()

proxies = {
    'http': config.get('REQUEST_PROXY_HTTP', ''),
    'https': config.get('REQUEST_PROXY_HTTPS', ''),
}

key_check = {
    "NovelAISecret": "NovelAI作图相关功能",
    "GPTSecret": "GPT相关功能",
    "GPTModel": "GPT相关功能",
    "GPTUrl": "GPT相关功能",
    "BLACK_LIST": "黑名单",
    "GROUP_LIST": "每日新闻",
    "DISABLED_MODULE": "禁用功能",
    "WT_DATAMINE_GIT": "战雷拆包数据库查询功能",
    "SCRIPING_ANT_TOKEN": "涉及Cloudflare反反爬功能",
    "REQUEST_PROXY_HTTP": "部分需翻墙功能",
    "REQUEST_PROXY_HTTPS": "部分需翻墙功能",
    "HEALTHCARE_GROUP_LIST": "提肛喝水小助手",
    "HISTORY_SAVE_PATH": "消息记录持久化路径",
}

for key in key_check.keys():
    if not config or key not in config:
        nonebot.logger.warning(f".env 中不包含 {key} 项，将导致无法正常使用{key_check[key]}")  # type: ignore


class IntervalLimiter():
    def __init__(self) -> None:
        self.root = {}

    def user_interval(self, function_name, id, interval = 30) -> bool:
        id = str(id)
        now_time_sec = int(time.time())
        if function_name not in self.root.keys():
            return True
        else:
            if id not in self.root[function_name] or self.root[function_name][id] < now_time_sec:
                return True
            return False
        
    def force_user_interval(self, function_name, id, interval=30):
        id = str(id)
        now_time_sec = int(time.time())
        interval_locker.acquire()
        if function_name not in self.root.keys():
            self.root.update({
                function_name: {
                    id: now_time_sec + interval
                }
            })
        else:
            self.root[function_name].update({
                id: now_time_sec + interval
            })
        interval_locker.release()

interval_limiter = IntervalLimiter()
