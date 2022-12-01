import configparser

import nonebot


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
    "NovelAICookie": "NovelAI作图相关功能",
    "DBHost": "数据库",
    "DBUser": "数据库",
    "DBPassword": "数据库",
    "DBTable": "数据库",
    "BLACK_LIST": "黑名单",
    "DISABLED_MODULE": "禁用功能",
}

for key in key_check.keys():
    if not config or key not in config:
        nonebot.logger.warning(f".env 中不包含 {key} 项，将导致无法正常使用{key_check[key]}")  # type: ignore
