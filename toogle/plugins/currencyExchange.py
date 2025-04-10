import re
from typing import Optional

import requests

from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack


class CurrencyExchange(MessageHandler):
    name = "货币转换"
    price = 2
    currency_map = {
        "USD": "usd",
        "usd": "usd",
        # "刀": "usd",
        "美刀": "usd",
        "美金": "usd",
        "美元": "usd",
        "GBP": "gbp",
        "gbp": "gbp",
        "镑": "gbp",
        "英镑": "gbp",
        "胖子": "gbp",
        "HKD": "hkd",
        "hkd": "hkd",
        "港币": "hkd",
        "港元": "hkd",
        "JPY": "jpy",
        "jpy": "jpy",
        "日元": "jpy",
        "yen": "jpy",
        "円": "jpy",
        "EUR": "eur",
        "eur": "eur",
        "欧": "eur",
        "欧元": "eur",
        # "RUB": "rub",
        # "rub": "rub",
        "卢布": "rub",
        "卢比": "inr",
        # "ARS": "ars",
        # "ars": "ars",
        "阿根廷比索": "ars",
        # "比索": "ars",
        # "peso": "ars",
        # "cad": "cad",
        # "CAD": "cad",
        "加币": "cad",
        "加元": "cad",
        # "try": "try",
        "TRY": "try",
        "里拉": "try",
        "土耳其里拉": "try",
        # "sgd": "sgd",
        # "SGD": "sgd",
        "新币": "sgd",
        "新加坡元": "sgd",
        # "twd": "twd",
        # "TWD": "twd",
        "台币": "twd",
        "新台币": "twd",
        # "aud": "aud",
        # "AUD": "aud",
        "澳币": "aud",
        "澳元": "aud",
        "澳刀": "aud",
        "韩元": "krw",
        # "Kr": "sek",
        # "kr": "sek",
        "SEK": "sek",
        "克朗": "sek",
        "瑞典克朗": "sek",
        "金鹰": "wtge",
        # "GE": "wtge",
        "研发点": "wtrp",
        "银狮": "wtsl",
    }
    block_chain_map = {
        # "bitcoin": "BTC",
        # "btc": "BTC",
        "BTC": "BTC",
        "比特币": "BTC",
        # "eth": "ETH",
        "ETH": "ETH",
        "以太坊": "ETH",
        "DOGE": "DOGE",
        "狗币": "DOGE",
    }
    currency_map.update(block_chain_map)

    num_str = "零一二三四五六七八九十百千万亿壹贰叁肆伍陆柒捌玖拾佰仟0123456789点两单俩兆/*+-,()mkwe"
    num_str = "|".join([x for x in num_str])
    keys_str = "|".join(currency_map.keys())
    exhibit_list = ["一刀"]
    trigger = f".*?(([\.|{num_str}]+)(usd|jpy|hkd|eur|gbp|{keys_str})).*" # type: ignore
    readme = "快捷货币转换"

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        message_str = message.message.asDisplay()
        matchs = re.search(self.trigger, message_str)

        if matchs:
            if matchs.group(1) in self.exhibit_list:
                raise Exception("误触发")
            currency = matchs.group(3)
            if currency in self.block_chain_map:
                rates = self.get_blockchain()
            else:
                rates = CurrencyExchange.get_currency()
            rate_mark = self.currency_map[currency].upper()
            num = self.cn2digit(matchs.group(2).replace(",", ""))
            if num <= 0:
                raise Exception("误触发")
            rate = rates[rate_mark]
            res = num / rate
            res = f"{matchs.group(1)} ({num:,.2f} {rate_mark})\n折合人民币为 ¥{res:,.2f}"
        else:
            raise Exception("误触发")
        return MessageChain.create([Plain(res)])

    def cn2digit(self, cn_str):
        UTIL_CN_NUM = {
            "零": 0,
            "一": 1,
            "单": 1,
            "俩": 2,
            "二": 2,
            "三": 3,
            "四": 4,
            "五": 5,
            "六": 6,
            "七": 7,
            "八": 8,
            "九": 9,
            "两": 2,
            "上": 1,
            "壹": 1,
            "贰": 2,
            "叁": 3,
            "肆": 4,
            "伍": 5,
            "陆": 6,
            "柒": 7,
            "捌": 8,
            "玖": 9,
            "拾": 10,
            "佰": 100,
            "仟": 1000,
            "十": 10,
            "百": 100,
            "千": 1000,
            "万": 10000,
            "兆": 1000000,
            "亿": 100000000,
            "e": 100000000,
            "m": 1000000,
            "w": 10000,
            "k": 1000,
            "0": 0,
            "1": 1,
            "2": 2,
            "3": 3,
            "4": 4,
            "5": 5,
            "6": 6,
            "7": 7,
            "8": 8,
            "9": 9,
            ".": ".",
            ",": "",
        }

        def cn2num(cnnumber):  # 中文转换成阿拉伯数字，小数部分
            arabnumber = ""
            for number in cnnumber:
                arabnumber = arabnumber + str(UTIL_CN_NUM[number])
            return arabnumber

        def under_k_parse(numberstr):
            try:
                return float(numberstr)
            except ValueError:
                pass
            total = []
            res_total = 0
            if "." in numberstr:
                res_total += float("0." + cn2num(numberstr.split(".")[1]))
                numberstr = numberstr.split(".")[0]

            for numstr_char in numberstr:
                val = UTIL_CN_NUM[numstr_char]
                total.append(val)
            if len(total) > 1 and total[-1] < 10 and total[-2] >= 100:
                total.append(int(total[-2] / 10))

            tmp_total = 0
            lis = False
            for index, num in enumerate(total):
                if num >= 10 and index != 0:
                    tmp_total *= num
                    if index == len(total) - 1:
                        res_total += tmp_total
                    lis = False
                elif num >= 10 and index == 0:
                    tmp_total += num
                    lis = False
                    if index == len(total) - 1:
                        res_total += tmp_total
                elif num == 0 and index != 0:
                    # tmp_total *= 10
                    lis = False
                else:
                    if lis:
                        tmp_total = tmp_total * 10 + num
                    else:
                        res_total += tmp_total
                        tmp_total = num
                    lis = True
                    if index == len(total) - 1:
                        res_total += tmp_total
            return res_total

        def cn2digits(cnnumber):  # 将中文转换成阿拉伯数字,整数部分 如七百二十四-> 724
            total = 0

            for big_unit in ["亿", "兆", "万"]:
                if big_unit in cnnumber:
                    total += (
                        under_k_parse(cnnumber.split(big_unit)[0])
                        * UTIL_CN_NUM[big_unit]
                    )
                    cnnumber = cnnumber.split(big_unit)[1]
            if cnnumber:
                total += under_k_parse(cnnumber)

            return str(total)

        cn_str = (
            cn_str.replace("点儿", ".")
            .replace("点", ".")
            .replace("w", "万")
            .replace("e", "亿")
        )
        try:
            return float(eval(cn_str))
        except Exception:
            pass

        return float(cn2digits(cn_str))

    def get_blockchain(self):
        api_url = "https://api.coincap.io/v2/assets"
        data = requests.get(api_url).json()["data"]
        usd_rate = CurrencyExchange.get_currency()["USD"]
        return {x["symbol"]: usd_rate / float(x["priceUsd"]) for x in data}

    @staticmethod
    def get_currency():
        api_url = "https://api.exchangerate-api.com/v4/latest/CNY"
        rates = requests.get(api_url).json()["rates"]
        rates.update(
            {
                "WTGE": 25000 / 113.85 * rates["USD"],
                "WTRP": 25000 / 113.85 * rates["USD"] * 45,
                "WTSL": 25000 / 113.85 * rates["USD"] * 1300000 / 3000,
            }
        )
        return rates
