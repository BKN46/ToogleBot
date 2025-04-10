import json
import os
import sys
import time

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import requests

from configs import proxies
from plugins.currencyExchange import CurrencyExchange
from plugins.math import Calculator


API_DATA_PATH = os.path.join(os.path.dirname(__file__), '../../../data/milkywayidle_api.json')
LEVEL_DATA_PATH = os.path.join(os.path.dirname(__file__), '../../../data/milkywayidle_levels.txt')

def load_data():
    data = json.load(open(API_DATA_PATH, 'r', encoding='utf-8'))
    data_time = data.get('time', 0)
    if time.time() - data_time > 3600*4:
        if update_info_json():
            data = json.load(open(API_DATA_PATH, 'r', encoding='utf-8'))
    return data.get('market', {})


def update_info_json():
    url = 'https://raw.githubusercontent.com/holychikenz/MWIApi/refs/heads/main/milkyapi.json'
    res = requests.get(url, proxies=proxies)
    if res.status_code == 200:
        with open(API_DATA_PATH, 'wb') as f:
            f.write(res.content)
        return True
    else:
        return False


def gold_to_money(gold: str):
    gold_ = Calculator.get_exec(Calculator.func_preproc(gold))
    data = load_data()
    cowbell = data['Bag Of 10 Cowbells']['ask']
    convert = gold_ / 0.82 / cowbell / 10 # type: ignore
    rate = CurrencyExchange.get_currency()['USD']
    convert_cny = convert / rate
    return f'{gold}金币(牛铃袋现价{cowbell/1000:.0f}K)\n约合{convert_cny:.2f}元 ({convert:.2f}usd)\n'


def get_level_info(start_level: int, end_level: int):
    levels = [
        x.strip().split('\t')
        for x in
        open(LEVEL_DATA_PATH, 'r', encoding='utf-8').readlines()
        if x.strip()
    ]
    if start_level > end_level:
        return f'等级错误'
    if end_level > 200:
        end_level = 200
    if start_level < 1:
        start_level = 1
    exp = int(levels[end_level - 1][1].replace(',','')) - int(levels[start_level - 1][1].replace(',',''))
    return f'{start_level}级到{end_level}级需要经验：{exp:,}点\n' \


if __name__ == "__main__":
    # load_data()
    # print(gold_to_money('15M'))
    print(get_level_info(60,85))
