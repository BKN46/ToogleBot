import configparser

import nonebot
import time


def ini_parse(data: str):
    if data.startswith("[") and data.endswith("]"):
        return eval(data)
    return data


config = {
    line.split("=")[0]: ini_parse(line.split("=")[1].replace("\n", ""))
    for line in open(".env", "r").readlines()
    if len(line) > 1
}

key_check = {
    "NovelAISecret": "NovelAI作图相关功能",
    "OpenAISecret": "OpenAI相关功能",
    "DBHost": "数据库",
    "DBUser": "数据库",
    "DBPassword": "数据库",
    "DBTable": "数据库",
    "BLACK_LIST": "黑名单",
    "DISABLED_MODULE": "禁用功能",
    "WT_DATAMINE_GIT": "战雷拆包数据库查询功能",
    "SCRIPING_ANT_TOKEN": "涉及Cloudflare反反爬功能",
    "REQUEST_PROXY_HTTP": "部分需翻墙功能",
    "REQUEST_PROXY_HTTPS": "部分需翻墙功能",
    "HEALTHCARE_GROUP_LIST": "提肛喝水小助手",
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
            self.root.update({
                function_name: {
                    id: now_time_sec + interval
                }
            })
            return True
        else:
            if id not in self.root[function_name] or self.root[function_name][id] < now_time_sec:
                self.root[function_name].update({
                    id: now_time_sec + interval
                })
                return True
            return False

interval_limiter = IntervalLimiter()
