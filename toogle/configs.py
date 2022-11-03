import configparser

import nonebot

config = {
    line.split('=')[0]: line.split('=')[1]
    for line in open('.env', 'r').readlines()
    if len(line) > 1
}

key_check = {
    'NovelAICookie': 'NovelAI作图相关功能',
    'DBHost': '数据库',
    'DBUser': '数据库',
    'DBPassword': '数据库',
    'DBTable': '数据库',
}

for key in key_check.keys():
    if not config or key not in config:
        nonebot.logger.warning(f".env 中不包含 {key} 项，将导致无法正常使用{key_check[key]}") # type: ignore
