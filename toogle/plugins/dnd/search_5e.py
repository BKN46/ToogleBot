import json
import os
import pickle
import random

from thefuzz import fuzz, process


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
    def get_from_data(*args, default=""):
        tmp = data
        try:
            for arg in args:
                tmp = tmp[arg]
            return tmp
        except Exception as e:
            return default

    try:
        desc = []
        for x in get_from_data("entries", default=[]):
            if isinstance(x, str):
                desc.append(x)
            elif isinstance(x, list):
                desc.append('\n'.join(x))
            elif isinstance(x, dict):
                desc.append('\n'.join(x['items']))
        desc = "\n".join(desc)
        duration = (
            f"{get_from_data('duration',0,'duration','amount')} {get_from_data('duration',0,'duration','type')}"
            if get_from_data('duration',0,'type') != "instant"
            else "立即"
        )
        m_range = (
            f"{get_from_data('range','distance','amount')} {get_from_data('range','distance','type')}"
            if get_from_data("range","distance","type") != "self"
            else "自身"
        )
        upper_desc = (
            "\n升环效果: " + "\n".join(get_from_data("entriesHigherLevel",0,"entries", default=[]))
            if "entriesHigherLevel" in data
            else ""
        )
        return (
            f"{get_from_data('name')} {get_from_data('ENG_name')} ({get_from_data('source')} p.{get_from_data('page')})\n"
            f"{get_from_data('level')}环 {SCHOOL_MAP[get_from_data('school')]}系 "
            f"成分: {'V' if 'v' in get_from_data('components') and get_from_data('components','v') else ''}"
            f"{'S' if 's' in get_from_data('components') and get_from_data('components','s') else ''}"
            f"{'M (' + get_from_data('components','m') + ')' if 'm' in get_from_data('components') and get_from_data('components','m') else ''}\n"
            f"施法时间: {get_from_data('time',0,'number')} {get_from_data('time',0,'unit')} | "
            f"持续时间: {duration} | "
            f"射程: {m_range}\n"
            f"描述: {desc}"
            f"{upper_desc}"
        )
    except Exception as e:
        # raise e
        return json.dumps(data, indent=2, ensure_ascii=False)


def search_magic(search_han):
    res = get_in_list(search_han)
    if res:
        return magic_stringify(res)
    if res:
        return magic_stringify(res)
    res = process.extract(search_han, DATA_FLATEN, limit=10)
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
    print(search_magic("wish"))
