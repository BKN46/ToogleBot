import json
import os
import pickle
import random

from thefuzz import fuzz, process

from toogle.plugins.dnd.langconv import Converter

DATA_PATH = "data/dnd5e/spells/"
DATA_INDEX = json.loads(open(DATA_PATH + "index.json", "r").read())
DATA = {
    extension: json.loads(
        open(DATA_PATH + extension_path, "r", encoding="utf-8", errors="ignore").read()
    )["spell"]
    for extension, extension_path in DATA_INDEX.items()
}
DATA_FLATEN = []
for k, v in DATA.items():
    DATA_FLATEN += v


SCHOOL_MAP = {
    "V": "塑能",
    "T": "变化",
    "C": "咒法",
    "E": "惑控",
    "A": "防护",
    "C": "咒法",
    "D": "预言",
    "I": "幻术",
    "N": "死灵",
}


def get_in_list(name):
    for line in DATA_FLATEN:
        if "ENG_name" in line:
            if line["name"] == name or line["ENG_name"].lower() == name.lower():
                return line
        else:
            if line["name"].lower() == name.lower():
                return line
    return None


def magic_stringify(data):
    try:
        desc = "\n".join(data["entries"])
        duration = (
            f"{data['duration'][0]['duration']['amount']} {data['duration'][0]['duration']['type']}"
            if data["duration"][0]["type"] != "instant"
            else "立即"
        )
        m_range = (
            f"{data['range']['distance']['amount']} {data['range']['distance']['type']}"
            if data["range"]["distance"]["type"] != "self"
            else "自身"
        )
        upper_desc = (
            "\n升环效果: " + "\n".join(data["entriesHigherLevel"][0]["entries"])
            if "entriesHigherLevel" in data
            else ""
        )
        return (
            f"{data['name']} {data['ENG_name'] if 'ENG_name' in data else ''} ({data['source']} p.{data['page']})\n"
            f"{data['level']}环 {SCHOOL_MAP[data['school']]}系 "
            f"成分: {'V' if 'v' in data['components'] and data['components']['v'] else ''} {'S' if 's' in data['components'] and data['components']['s'] else ''} {'M (' + data['components']['m'] + ')' if 'm' in data['components'] and data['components']['m'] else ''}\n"
            f"施法时间: {data['time'][0]['number']} {data['time'][0]['unit']} | "
            f"持续时间: {duration} | "
            f"射程: {m_range}\n"
            f"描述: {desc}"
            f"{upper_desc}"
        )
    except Exception:
        return json.dumps(data, indent=2, ensure_ascii=False)


def search_magic(search_han):
    search_hant = Converter("zh-hant").convert(search_han)
    res = get_in_list(search_han)
    if res:
        return magic_stringify(res)
    res = get_in_list(search_hant)
    if res:
        return magic_stringify(res)
    res = process.extract(search_hant, DATA_FLATEN, limit=10)
    res = "\n".join(
        [f"{x[0]['name']} | {x[0]['level']}环 {x[0]['source']}" for x in res]
    )
    return f"没有匹配到具体法术，可能是:\n" f"{res}"


def random_magic():
    res = {}
    while "ENG_name" not in res:
        res = random.choice(DATA_FLATEN)
    return res["ENG_name"], res["name"]


if __name__ == "__main__":
    print(search_magic("治愈真言"))
