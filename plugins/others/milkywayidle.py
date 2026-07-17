import json
import random
import time
from pathlib import Path

import requests

from configs import proxies
from plugins.currencyExchange import CurrencyExchange
from plugins.math import Calculator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "milkywayidle"
API_DATA_PATH = DATA_DIR / "milkywayidle_api.json"
DB_DATA_PATH = DATA_DIR / "milkywayidle_price.db"
LEVEL_DATA_PATH = DATA_DIR / "milkywayidle_levels.txt"
TRANSLATE_FILE_PATH = DATA_DIR / "translate.json"


def load_long_term_price_data():
    url = 'https://raw.gitmirror.com/holychikenz/MWIApi/refs/heads/main/market.db'
    res = requests.get(url, proxies=proxies, timeout=(5, 30))
    if res.status_code == 200:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with DB_DATA_PATH.open('wb') as f:
            f.write(res.content)
        return True
    else:
        return False


def load_now_price_data():
    with API_DATA_PATH.open('r', encoding='utf-8') as data_file:
        data = json.load(data_file)
    data_time = data.get('time', 0)
    if time.time() - data_time > 3600*4:
        if update_info_json():
            with API_DATA_PATH.open('r', encoding='utf-8') as data_file:
                data = json.load(data_file)
    return data.get('market', {})


def search_item_eng_name(name):
    with TRANSLATE_FILE_PATH.open('r', encoding='utf-8') as data_file:
        data = json.load(data_file)
    res = []
    for eng_name, chn_name in data.items():
        if name == chn_name:
            return eng_name
        elif name in chn_name:
            res.append(eng_name)
    return res


def large_number_convert(num):
    if num > 1e12:
        return f'{num / 1e12:.2f}T'
    elif num > 1e9:
        return f'{num / 1e9:.2f}B'
    elif num > 1e6:
        return f'{num / 1e6:.2f}M'
    elif num > 1e3:
        return f'{num / 1e3:.2f}K'
    else:
        return str(num)


def get_item_price(item_name, data=None, with_format=False):
    if data is None:
        data = load_now_price_data()
    ask = data.get(item_name, {}).get('ask', 0)
    bid = data.get(item_name, {}).get('bid', 0)
    if with_format:
        ask = large_number_convert(ask)
        bid = large_number_convert(bid)
    return ask, bid


def update_info_json():
    url = 'https://raw.githubusercontent.com/holychikenz/MWIApi/refs/heads/main/milkyapi.json'
    res = requests.get(url, proxies=proxies, timeout=(5, 30))
    if res.status_code == 200:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with API_DATA_PATH.open('wb') as f:
            f.write(res.content)
        return True
    else:
        return False


def gold_to_money(gold: str):
    gold_ = Calculator.get_exec(Calculator.func_preproc(gold))
    ask, bid = get_item_price('Bag Of 10 Cowbells')
    convert = gold_ / 0.82 / ask / 10 # type: ignore
    rate = CurrencyExchange.get_currency()['USD']
    convert_cny = convert / rate
    return f'{gold}金币(牛铃袋现价{ask/1000:.0f}K)\n约合{convert_cny:.2f}元 ({convert:.2f}usd)\n' # type: ignore


def get_level_info(start_level: int, end_level: int):
    with LEVEL_DATA_PATH.open('r', encoding='utf-8') as level_file:
        levels = [
            line.strip().split('\t')
            for line in level_file
            if line.strip()
        ]
    if start_level > end_level:
        return f'等级错误'
    if end_level > 200:
        end_level = 200
    if start_level < 1:
        start_level = 1
    exp = int(levels[end_level - 1][1].replace(',','')) - int(levels[start_level - 1][1].replace(',',''))
    return f'{start_level}级到{end_level}级需要经验：{exp:,}点\n折合{exp/500:.2f}(或{exp/50:.2f})本技能书' \


enhancement_succes_rates = [
    0.5,
    0.4,
    0.4,
    0.4,
    0.4,
    0.4,
    0.3,
    0.3,
    0.3,
    0.3,
    0.3,
    0.3,
    0.3,
    0.3,
    0.3,
    0.3,
    0.3,
    0.3,
    0.3,
    0.3,
]

def get_success_rate_matrix(base_success_rate, initial_level=1, protect_from=5):
    if base_success_rate > 1:
        base_success_rate /= 100
    base_success_rate /= enhancement_succes_rates[initial_level - 1]
    levels = []
    for i in range(19):
        level = [0 for _ in range(20)]
        success_rate = base_success_rate * enhancement_succes_rates[i]
        if i+1 < protect_from:
            level[0] = 1 - success_rate
            level[i+1] = success_rate
        else:
            level[max(i-1, 0)] = 1 - success_rate
            level[i+1] = success_rate
        levels.append(level)

    return levels


def sim_enhancement(base_success_rate, initial_level=1, target_level=10, protect_from=5):
    if base_success_rate > 1:
        base_success_rate /= 100
    base_success_rate /= enhancement_succes_rates[initial_level - 1]
    now_level = initial_level
    protect_cnt, cnt = 0, 0
    while now_level < target_level:
        cnt += 1
        success_rate = base_success_rate * enhancement_succes_rates[now_level - 1]
        if random.random() < success_rate:
            now_level += 1
        else:
            if now_level < protect_from:
                now_level = 1
            else:
                now_level -= 1
                protect_cnt += 1
    return cnt, protect_cnt


def multiple_sim_enhancement(base_success_rate, initial_level=1, target_level=10, protect_from=5, times=30000):
    cnt_res, protect_res= [], []
    for _ in range(times):
        cnt, protect_cnt = sim_enhancement(base_success_rate, initial_level, target_level, protect_from)
        cnt_res.append(cnt)
        protect_res.append(protect_cnt)
    return sum(cnt_res) / len(cnt_res), sum(protect_res) / len(protect_res)
