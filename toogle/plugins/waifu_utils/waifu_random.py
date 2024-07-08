import json
import math
import os
import random
import re
import io
from posixpath import split
from typing import Tuple

import bs4
import PIL.Image
import PIL.ImageColor
import PIL.ImageDraw
import PIL.ImageFont
import requests

SAVE_PATH = "data/waifu_rank.png"
FONT_TYPE = "toogle/plugins/compose/fonts/Arial Unicode MS Font.ttf"

PARAM_KEYWORD = {
    "黑发": ["hair_color", 1, 1],
    "黄发": ["hair_color", 2, 1],
    "金发": ["hair_color", 2, 1],
    "蓝发": ["hair_color", 3, 3],
    "棕发": ["hair_color", 4, 1],
    "绿发": ["hair_color", 5, 5],
    "灰发": ["hair_color", 6, 2],
    "橙发": ["hair_color", 7, 2],
    "紫发": ["hair_color", 8, 4],
    "红发": ["hair_color", 9, 2],
    "白发": ["hair_color", 10, 3],
    "粉发": ["hair_color", 12, 3],
    "粉毛": ["hair_color", 12, 3],
    "青发": ["hair_color", 14, 3],
    "黑瞳": ["eye_color", 1, 1],
    "蓝瞳": ["eye_color", 3, 1],
    "棕瞳": ["eye_color", 4, 1],
    "绿瞳": ["eye_color", 5, 2],
    "灰瞳": ["eye_color", 6, 2],
    "橙瞳": ["eye_color", 7, 2],
    "紫瞳": ["eye_color", 8, 3],
    "红瞳": ["eye_color", 9, 2],
    "白瞳": ["eye_color", 10, 2],
    "黄瞳": ["eye_color", 11, 2],
    "粉瞳": ["eye_color", 12, 3],
    "青瞳": ["eye_color", 14, 3],
    "光头": ["hair_length", 1, 5],
    "短发": ["hair_length", 2, 2],
    "齐颈发": ["hair_length", 3, 2],
    "齐肩发": ["hair_length", 4, 2],
    "齐胸发": ["hair_length", 5, 2],
    "齐腰发": ["hair_length", 6, 2],
    "过腰发": ["hair_length", 7, 2],
    "盘发": ["hair_length", 8, 2],
    "儿童": ["age", 1, 2],
    "青年": ["age", 3, 1],
    "成年": ["age", 4, 1],
    "大龄": ["age", 5, 2],
    "永生": ["age", 6, 3],
    "主角": ["role", 10, 5],
    "反派": ["role", 9, 4],
    "第二主角": ["role", 8, 4],
    "副主角": ["role", 7, 3],
    "配角": ["role", 5, 2],
    "黄游": ["mt", 1, 2],
    "动漫": ["mt", 2, 4],
    "游戏": ["mt", 3, 4],
    "视觉小说": ["mt", 4, 4],
    "漫画": ["mt", 5, 5],
    "OVA": ["mt", 8, 3],
    "其他来源": ["mt", 9, 3],
    "轻小说": ["mt", 13, 5],
    "western": ["mt", 14, 3],
    "手游": ["mt", 25, 4],
    "女仆装": ["clothing", 1, 2],
    "校服": ["clothing", 2, 2],
    "泳装": ["clothing", 4, 2],
    "哥特": ["clothing", 6, 4],
    "装甲": ["clothing", 10, 4],
    "正装": ["clothing", 11, 4],
    "护士": ["clothing", 29, 4],
    "人类": ["otherchar", 0, 1],
    "动物": ["otherchar", 1, 3],
    "非人": ["otherchar", 2, 3],
    "呆毛": ["tag", "ahoge", 1],
    "帽子": ["tag", "hat", 2],
    "大衣": ["tag", "coat", 2],
    "领带": ["tag", "tie", 3],
    "T恤": ["tag", "t-shirt", 3],
    "围巾": ["tag", "scarf", 3],
    "病娇": ["tag", "yandere", 5],
    "傲娇": ["tag", "tsundere", 3],
    "马尾": ["tag", "ponytail", 3],
    "双马尾": ["tag", "twintails", 4],
    "侧马尾": ["tag", "side ponytail", 5],
    "偶像": ["tag", "idol", 5],
    "歌手": ["tag", "singer", 5],
    "精灵": ["tag", "elf", 5],
    "黑皮": ["tag", "dark skin", 3],
    "僵尸": ["tag", "zombie", 7],
    "浅黑皮": ["tag", "tanned", 3],
    "枪械": ["tag", "gun", 4],
    "剑士": ["tag", "sword", 4],
    "丝袜": ["tag", "stockings", 2],
    "丝带": ["tag", "ribbon", 3],
    "发带": ["tag", "hair ribbon", 4],
    "猫耳": ["tag", "cat ears", 4],
    "尾巴": ["tag", "tail", 4],
    "项圈": ["tag", "choker", 4],
    "制服": ["tag", "uniform", 3],
    "和服": ["tag", "kimono", 4],
    "巨乳": ["tag", "kyonyuu", 3],
    "贫乳": ["tag", "hinnyuu", 3],
    "眼镜": ["tag", "glasses", 3],
    "连裤袜": ["tag", "tights", 4],
    "刘海": ["tag", "hair intakes", 3],
    "姬发": ["tag", "hime cut", 4],
    "辫子": ["tag", "braid", 3],
    "裙子": ["tag", "dress", 3],
    "多发色": ["tag", "multicolour hair", 3],
    "假小子": ["tag", "tomboy", 4],
    "兽耳": ["mimikko", 2, 3],
}
YEAR_SEARCH_COST = 6


TYPED_KEYWORD = {}
for k, v in PARAM_KEYWORD.items():
    if v[0] in TYPED_KEYWORD:
        TYPED_KEYWORD[v[0]].append(f"{k}【{v[2]}】")
    else:
        TYPED_KEYWORD[v[0]] = [f"{k}【{v[2]}】"]


class ACError(Exception):
    pass


def get_keyword_explain():
    return (
        "输入【随机老婆 属性1 属性2 ...】属性间空格分隔，每次搜索可用10个点数，选择不同属性会消耗点数，重复类型特性会互相覆盖\n可选特点【分数】:\n"
        + f"#date#\nXXXX年【{YEAR_SEARCH_COST}】\n\n"
        + "\n\n".join([f"#{k}#:\n{','.join(v)}" for k, v in TYPED_KEYWORD.items()])
    )


def get_random_anime_character(sexual):
    req_url = f"https://www.animecharactersdatabase.com/r.php?{sexual}"
    header = {
        "Host": "www.animecharactersdatabase.com",
        "Referer": "https://www.animecharactersdatabase.com/index.php",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36",
        "sec-ch-ua": '''"Chromium";v="104", " Not A;Brand";v="99", "Google Chrome";v="104"''',
    }
    res = requests.get(req_url, headers=header, timeout=20)
    return parse_anime_db(res)


def get_anime_character(id):
    req_url = (
        f"https://www.animecharactersdatabase.com/characters.php?id={id}&more#extra"
    )
    header = {
        "Host": "www.animecharactersdatabase.com",
        "Referer": "https://www.animecharactersdatabase.com/index.php",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36",
        "sec-ch-ua": '''"Chromium";v="104", " Not A;Brand";v="99", "Google Chrome";v="104"''',
    }
    res = requests.get(req_url, headers=header, timeout=20)
    return parse_anime_db(res)


def get_designated_search(sexual, search_list, retry=3):
    total_score, total_cost = 10, 0
    # key value cost
    params = {
        "mimikko": 0,
        "tag": "",
        "sc": "",
        "sp": "",
        "date": 0,
        "refs": 0,
        "role": 0,
        "lightdark": 0,
        "esbr": -1,
        "clothing": 0,
        "otherchar": -1,
        "mt": 0,
        "gender": 1 if sexual == "m" else 2,
        "hair_color": 0,
        "hair_color2": 0,
        "hair_color3": 0,
        "hair_length": 0,
        "hair_length2": 0,
        "hair_length3": 0,
        "eye_color": 0,
        "eye_color2": 0,
        "eye_color3": 0,
        "age2": 0,
        "age3": 0,
        "age": 0,
        "random": 1,
    }

    for keyword in search_list:
        if keyword.endswith("年") and keyword not in PARAM_KEYWORD.keys():
            keyword = keyword[:-1]
            try:
                param_line = ["date", int(keyword), YEAR_SEARCH_COST]
            except Exception:
                raise ACError(f"年份不合法：{keyword}")
        elif keyword not in PARAM_KEYWORD.keys():
            raise ACError(f"{keyword}不在备选属性中，请输入【可选对象属性】来获取属性列表")
        else:
            param_line = PARAM_KEYWORD[keyword]
        total_cost += param_line[2]
        if total_cost > total_score:
            tmp = ", ".join(
                [
                    f"{x}【{PARAM_KEYWORD[x][2] if not x.endswith('年') or x in PARAM_KEYWORD.keys() else YEAR_SEARCH_COST}】"
                    for x in search_list if x in PARAM_KEYWORD.keys() or x.endswith('年')
                ]
            )
            raise ACError(f"分数不足: {tmp}")
        if param_line[0] == "tag":
            params.update(
                {
                    param_line[
                        0
                    ]: f"{params['tag']}{',' if params['tag'] else ''}{param_line[1]}"
                }
            )
        else:
            params.update({param_line[0]: param_line[1]})

    param_str = "&".join([f"{k}={v}" for k, v in params.items()])
    req_url = f"https://www.animecharactersdatabase.com/ajax_ux_search.php?" + param_str
    header = {
        "Host": "www.animecharactersdatabase.com",
        "Referer": "https://www.animecharactersdatabase.com/index.php",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36",
        "sec-ch-ua": '''"Chromium";v="104", " Not A;Brand";v="99", "Google Chrome";v="104"''',
        "Content-Type": "application/x-www-form-urlencoded",
    }
    body = {
        "random": 1,
        "order": 1,
    }
    res = requests.get(req_url, headers=header, data=body, timeout=20)
    soup = bs4.BeautifulSoup(res.text, "html.parser")
    page_links = soup.find("div", {"class": "flexcontainer"})
    if page_links:
        max_page = int(page_links.findAll("a", {"class": "flexitem pad"})[-1].text.strip()) # type: ignore
        req_url += f"&page={random.randint(1, max_page)}"
        res = requests.get(req_url, headers=header, data=body, timeout=20)
        soup = bs4.BeautifulSoup(res.text, "html.parser")
    chara_list = [
        x for x in soup.findAll("a")
        if 'href' in x.attrs and 'class' not in x.attrs
    ]
    if len(chara_list) == 0:
        raise ACError("无符合条件角色，请至animecharactersdatabase确认")
    chara_id = random.choice(chara_list).attrs["href"].split("?id=")[-1]
    while retry > 0:
        try:
            return get_anime_character(chara_id), req_url
        except Exception as e:
            chara_id = random.choice(chara_list).attrs["href"].split("?id=")[-1]
            if retry == 0:
                raise ACError("获取角色信息失败，请至animecharactersdatabase确认")
        retry -= 1


def get_anime_src(src_id):
    req_url = f"https://www.animecharactersdatabase.com/source.php?id={src_id}"
    header = {
        "Host": "www.animecharactersdatabase.com",
        "Referer": "https://www.animecharactersdatabase.com/index.php",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36",
        "sec-ch-ua": '''"Chromium";v="104", " Not A;Brand";v="99", "Google Chrome";v="104"''',
    }
    res = requests.get(req_url, headers=header, timeout=20)
    soup = bs4.BeautifulSoup(res.text, "html.parser")

    def find_in_profile(key):
        base = soup.find(id="besttable").find(text=key) # type: ignore
        if base:
            if base.parent.name == "a": # type: ignore
                return base.parent.parent.parent.td.text # type: ignore
            else:
                return base.parent.parent.td.text # type: ignore
        else:
            return ""

    res = {
        "title_en": find_in_profile("English Title"),
        "title": find_in_profile("Japanese Title"),
        "studio": find_in_profile("Japanese Studio Name"),
    }
    return res


def parse_anime_db(res):
    profile_id = res.url.split("?id=")[1].replace("&more#extra", "")

    def find_in_profile(key):
        base = soup.find(id="sidephoto").find(text=key) # type: ignore
        if base:
            if base.parent.name == "a": # type: ignore
                return base.parent.parent.parent.td.text # type: ignore
            else:
                return base.parent.parent.td.text # type: ignore
        else:
            return ""

    soup = bs4.BeautifulSoup(res.text, "html.parser")
    profile_pic = soup.find(id="profileimage").attrs.get("src") # type: ignore
    profile_name = (
        soup.find(id="mainframe1")
        .find(text="Share ▼") # type: ignore
        .parent.parent.text.split("|")[0] # type: ignore
        .strip()
    ).split(", ")[0]
    profile_name = re.sub(r"(\(.*?\))|(（.*?）)", "", profile_name).strip()
    en_name = soup.find(id="main1").find("a", {"class": "fgw"}).text # type: ignore
    if len(profile_name) < 1 or profile_name == "\xa0":
        profile_name = en_name
    profile_heat = (
        soup.find(id="main1").find("a", {"href": "seriesfinder3.php"}).text.split()[0] # type: ignore
    )
    profile_year = soup.find("a", {"href": "year_trivia.php"}).text.split()[0] # type: ignore
    profile_src = (
        soup.find(id="sidephoto")
        .find(text="From") # type: ignore
        .parent.parent.find("a") # type: ignore
        .attrs["href"] # type: ignore
        .split("?id=")[-1]
    )

    profile_vs_matches = soup.find(id="mainframe2").findAll(id="besttable") # type: ignore
    profile_vs_result = []
    for vs in profile_vs_matches:
        against_chara_id = vs.find("td").findAll("a")[1].attrs["href"].split("?id=")[-1]
        against_chara_name = vs.find("td").findAll("a")[1].text
        vs_res = False
        if profile_id == against_chara_id:
            against_chara_id = (
                vs.find("td").findAll("a")[2].attrs["href"].split("?id=")[-1]
            )
            against_chara_name = vs.find("td").findAll("a")[2].text
            vs_res = True
        if "won" in vs.find("td").contents[4]:
            profile_vs_result.append([vs_res, against_chara_name, against_chara_id])
        else:
            profile_vs_result.append([not vs_res, against_chara_name, against_chara_id])

    res = {
        "姓名": profile_name,
        "CV": find_in_profile("Voiced By"),
        "来源": find_in_profile("From"),
        "类型": find_in_profile("Media Type"),
        "年龄": find_in_profile("Age"),
        "生日": find_in_profile("Birthday"),
        "身高": find_in_profile("Height"),
        "三维": "/".join(
            [
                find_in_profile("Bust"),
                find_in_profile("Waist"),
                find_in_profile("Hip"),
            ]
        ),
        "血型": find_in_profile("Blood Type"),
        "星座": find_in_profile("Sign"),
        "TAG": find_in_profile("Tags "),
        "年代": profile_year,
        "热度": profile_heat,
    }
    raw_res = {
        **res,
        "en_name": en_name,
        "src_id": profile_src,
        "vs": profile_vs_result,
    }

    def parse_output(res):
        return "\n".join(
            [f"{k}: {v}" for k, v in res.items() if len(v.replace("/", "")) > 0]
        )

    return profile_pic, parse_output(res), profile_id, raw_res


def bgm_search(object_str):
    object_str = object_str.replace(" ", "+")
    for k in ["!", "?", "？", "！", "/", " "]:
        object_str = object_str.replace(k, f"+")
    req_url = f"https://bgm.tv/subject_search/{object_str}?cat=all"
    header = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36",
        "sec-ch-ua": '''"Chromium";v="104", " Not A;Brand";v="99", "Google Chrome";v="104"''',
    }
    res = requests.get(req_url, headers=header, timeout=20)
    soup = bs4.BeautifulSoup(res.text, "html.parser")

    def parse_rate(item):
        try:
            rate_str = item.find("span", {"class": "tip_j"}).text
        except Exception as e:
            return 0
        if "(å°\x91äº\x8e10äººè¯\x84å\x88\x86)" == rate_str:
            return 1
        elif "äººè¯\x84å\x88\x86)" in rate_str:
            return int(rate_str.replace("äººè¯\x84å\x88\x86)", "")[1:])
        return 0

    if not soup.find(id="browserItemList"):
        return []

    item_list = [
        {
            "id": x.a.attrs["href"].split("/")[-1], # type: ignore
            "rate": parse_rate(x),
        }
        for x in soup.find(id="browserItemList").contents # type: ignore
    ]
    return sorted(item_list, key=lambda x: x["rate"], reverse=True)


def bgm_character_search(object_str):
    req_url = f"https://bgm.tv/mono_search/{object_str}?cat=all"
    header = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36",
        "sec-ch-ua": '''"Chromium";v="104", " Not A;Brand";v="99", "Google Chrome";v="104"''',
    }
    res = requests.get(req_url, headers=header, timeout=20)
    soup = bs4.BeautifulSoup(res.text, "html.parser")

    item_list = [
        {
            "id": x.a.attrs["href"].split("/")[-1],
            "popularity": x.find("small", {"class": "na"}).text[2:-1],
        }
        for x in soup.find("div", {"id", "columnSearchB"}).findAll( # type: ignore
            "div", {"class", "light_odd clearit"}
        )
    ]

    return sorted(item_list, key=lambda x: x["popularity"], reverse=True)


def get_bgm_src_detail(id):
    req_url = f"https://bgm.tv/subject/{id}"
    header = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36",
        "sec-ch-ua": '''"Chromium";v="104", " Not A;Brand";v="99", "Google Chrome";v="104"''',
    }
    res = requests.get(req_url, headers=header, timeout=20)

    soup = bs4.BeautifulSoup(res.text, "html.parser")

    if soup.find("h2").text == "å\x91\x9cå\x92\x95ï¼\x8cå\x87ºé\x94\x99äº\x86": # type: ignore
        return {"score": 0, "rank": 99999, "popularity": 0}

    def get_rank():
        rank = soup.find("div", {"class": "global_score"}).find( # type: ignore
            "small", {"class": "alarm"} # type: ignore
        )
        if rank:
            return int(rank.text[1:]) # type: ignore
        else:
            return 99999

    res = {
        "score": float(soup.find("span", {"property": "v:average"}).text), # type: ignore
        "rank": get_rank(),
        "popularity": int(soup.find("span", {"property": "v:votes"}).text), # type: ignore
    }

    return res


def parse_popularity_data(data):
    res = (
        f"{data['name']}\n"
        f"{data['en_name']}\n"
        f"来自作品 {data['src']}\n"
        f"ACDB角色热度{data['acdb_heat']}\n"
        f"BGM作品评分{data['bgm_score']}\n"
        f"BGM作品排名{data['bgm_rank']}\n"
        f"BGM作品热度{data['bgm_heat']}\n\n"
        f"综合分数{data['score']:.2f}\n综合评级{data['rank']}"
    )
    return res


def get_anime_character_popularity(acdb_id=None, sexual="f", extra_ratio=1.0):
    try:
        if acdb_id:
            acdb_pic, _, acdb_id, acdb_raw = get_anime_character(acdb_id)
        else:
            acdb_pic, _, acdb_id, acdb_raw = get_random_anime_character(sexual)
        acdb_src = get_anime_src(acdb_raw["src_id"])
        if len(acdb_src["title"]) > 0:
            bgm_search_res = bgm_search(acdb_src["title"])
        else:
            bgm_search_res = bgm_search(acdb_src["title_en"])
        if len(bgm_search_res) > 0:
            bgm_src_detail = get_bgm_src_detail(bgm_search_res[0]["id"])
        else:
            bgm_src_detail = {"score": 0, "rank": 99999, "popularity": 0}
    except requests.exceptions.RequestException as e:
        return "请求超时"

    res_data = {
        "name": acdb_raw["姓名"],
        "en_name": acdb_raw["en_name"],
        "CV": acdb_raw["CV"],
        "pic": acdb_pic,
        "src": acdb_src["title"] if acdb_src["title"] else acdb_src["title_en"],
        "type": acdb_raw["类型"],
        "vs": acdb_raw["vs"],
        "acdb_heat": acdb_raw["热度"],
        "bgm_score": bgm_src_detail["score"],
        "bgm_rank": bgm_src_detail["rank"],
        "bgm_heat": bgm_src_detail["popularity"],
    }

    score, rank = score_calc(res_data, extra_ratio=extra_ratio)
    res_data = {
        **res_data,
        "score": score,
        "rank": rank,
        "bgm_score": bgm_src_detail["score"]
        if bgm_src_detail["score"] != 0
        else " ---",
        "bgm_rank": bgm_src_detail["rank"]
        if bgm_src_detail["rank"] != 99999
        else " ---",
        "bgm_heat": bgm_src_detail["popularity"]
        if bgm_src_detail["popularity"] != 0
        else " ---",
    }

    return parse_popularity_data(res_data), acdb_pic, res_data


def score_calc(res_data, extra_ratio=1.0):
    def sigmoid(x, shift=0, ratio=1):
        return (1 / (1 + math.exp(-(x + shift) / ratio))) * ratio

    acdb_heat, bgm_heat, bgm_rank = (
        res_data["acdb_heat"],
        res_data["bgm_heat"],
        res_data["bgm_rank"],
    )
    src_type = res_data["type"]
    score = sigmoid(int(acdb_heat), shift=-2000, ratio=800) + sigmoid(
        int(bgm_heat), shift=-1500, ratio=700
    )
    score += math.sqrt(max((500 - bgm_rank) * 500, 0))
    for vs in res_data["vs"]:
        if vs[0]:
            score += 50
        else:
            score += 10

    score = score * extra_ratio

    if score > 1000:
        rank = "UR"
    elif score > 900:
        rank = "SSR"
    elif score > 700:
        rank = "SR"
    elif score > 500:
        rank = "R"
    else:
        rank = "N"

    return score, rank


def calc_confirm():
    confirm_list = ["115747", "36120", "11804", "19352", "16460", "102632"]
    for chara in confirm_list:
        tmp = get_anime_character_popularity(acdb_id=chara)[2]
        print(f"{tmp['name']} {tmp['score']} {tmp['rank']}") # type: ignore

    for _ in range(5):
        tmp = get_anime_character_popularity()[2]
        print(f"{tmp['name']} {tmp['score']} {tmp['rank']}") # type: ignore


BASE_PATH = ""

SIZE = [1500, 4000]
PIC_SIZE = [350, int(SIZE[1] / 10)]
BG_COLOR = [
    (255, 255, 255),
    (235, 235, 235),
    (200, 238, 243),
]

RANK_COLOR = {
    "UR": (230, 100, 203),
    "SSR": (250, 174, 89),
    "SR": (250, 245, 97),
    "R": (207, 212, 250),
    "N": (80, 80, 80),
}


def buffered_url_pic(pic_url):
    buffer_path = BASE_PATH + "data/buffer/"
    all_buffer = os.listdir(buffer_path)

    trans_url = pic_url.replace("://", "_").replace("/", "_")

    if trans_url in all_buffer:
        return PIL.Image.open(buffer_path + trans_url)

    PIL.Image.open(requests.get(pic_url, stream=True).raw).save(buffer_path + trans_url)
    return PIL.Image.open(buffer_path + trans_url)


def max_resize(img, max_width=PIC_SIZE[0], max_height=PIC_SIZE[1]):
    if img.size[0] >= img.size[1]:
        return img.resize(
            (max_width, int(img.size[1] * max_width / img.size[0])),
            PIL.Image.Resampling.LANCZOS,
        )
    else:
        return img.resize(
            (int(img.size[0] * max_height / img.size[1]), max_height),
            PIL.Image.Resampling.LANCZOS,
        )


def get_font_wrap(text: str, font: PIL.ImageFont.ImageFont, box_width: int):
    res = []
    for line in text.split("\n"):
        line_width = font.getbbox(line)[2]  # type: ignore
        while box_width < line_width:
            split_pos = int(box_width / line_width * len(line)) - 1
            while True:
                lw = font.getbbox(line[:split_pos])[2]  # type: ignore
                rw = font.getbbox(line[: split_pos + 1])[2]  # type: ignore
                if lw > box_width:
                    split_pos -= 1
                elif rw < box_width:
                    split_pos += 1
                else:
                    break
            res.append(line[:split_pos])
            line = line[split_pos:]
            line_width = font.getbbox(line)[2]  # type: ignore
        res.append(line)
    return "\n".join(res)


def text_on_image(
    image: PIL.Image.Image,
    text: str,
    font_path: str = FONT_TYPE,
    word_size: int = 20,
    max_size: Tuple[int, int] = (500, 1000),
    pos: Tuple[int, int] = (20, 20),
    bg_color: Tuple[int, int, int] = (255, 255, 255),
    font_color: Tuple[int, int, int] = (20, 20, 20),
    font_height_adjust: int = 0,
) -> PIL.Image.Image:
    font = PIL.ImageFont.truetype(font_path, word_size)
    text = get_font_wrap(text, font, max_size[0])  # type: ignore
    text_width = max([font.getbbox(x)[2] for x in text.split("\n")])
    # text_height = sum([font.getbbox(x)[3] for x in text.split('\n')])  # type: ignore
    text_height = sum([font.getbbox(x)[3] + font_height_adjust for x in text.split("\n")])  # type: ignore
    # text_height = (word_size + 3) * len(text.split("\n"))

    draw = PIL.ImageDraw.Draw(image)

    draw.text(
        (pos[0], pos[1]),
        text,
        font_color,
        font=font,
    )
    return image


def waifu_card(
    pic_url: str,
    name: str,
    src: str,
    waifu_type: str,
    text: str,
    bg_color = (248, 255, 240),
    max_size = (1000, 400),
):
    padding = (20, 20)
    pic = max_resize(
        buffered_url_pic(pic_url),
        max_width=int(max_size[0] * 0.3 - padding[0]),
        max_height=int(max_size[1] - 2 * padding[1]),
    )
    pic_size = pic.size
    gen_image = PIL.Image.new(
        "RGBA",
        (max_size[0], max_size[1]),
        bg_color,
    )
    image_draw = PIL.ImageDraw.Draw(gen_image)

    font1 = PIL.ImageFont.truetype(FONT_TYPE, 60)
    font2 = PIL.ImageFont.truetype(FONT_TYPE, 20)
    font3 = PIL.ImageFont.truetype(FONT_TYPE, 40)
    image_draw.text(
        (max_size[0] - padding[0] - font1.getbbox(name)[2], padding[1]),
        name,
        (96, 221, 250),
        font=font1,
    )
    image_draw.text(
        (max_size[0] - padding[0] - font2.getbbox(src)[2], padding[1] + 65),
        src,
        (250, 239, 131),
        font=font2,
    )
    waifu_type = waifu_type.upper()
    image_draw.text(
        (max_size[0] - padding[0] - font3.getbbox(waifu_type)[2], max_size[1] - padding[1] - font3.getbbox(waifu_type)[3]),
        waifu_type,
        (255, 96, 85),
        font=font3,
    )
    image_draw.rectangle(
        (0, 0, padding[0], max_size[1]),
        fill=bg_color
    )

    gen_image.paste(pic, (padding[0], padding[1]))
    text_on_image(
        gen_image,
        text,
        word_size=23,
        max_size=(max_size[0] - pic_size[0] - padding[0] * 3, int(max_size[1] * 1.5)),
        pos=(pic_size[0] + padding[0] * 2, padding[1]),
        bg_color=bg_color,
        font_color=(10, 10, 10),
        font_height_adjust=6,
    )

    img_bytes = io.BytesIO()
    gen_image.save(img_bytes, format="PNG")
    return img_bytes.getvalue()


if __name__ == "__main__":
    # print(get_random_anime_character("f"))
    # print(get_anime_character("102632")[1])
    # print(get_anime_src("107190"))
    # print(get_bgm_src_detail("137458"))
    # print(bgm_character_search("エアリス"))
    # print(get_anime_character_popularity(acdb_id="15442")[0])
    # print(get_keyword_explain())
    # print(get_designated_search("f", ["红发", "轻小说"])[1])
    # calc_confirm()

    data, url = get_designated_search("f", ["粉毛", "动漫"]) # type: ignore
    print(data, url)
    # pic_url, text, profile_id, raw = data
    # pic = waifu_card(
    #     pic_url, # type: ignore
    #     raw['姓名'],
    #     raw['来源'],
    #     raw['类型'],
    #     text
    # )
    # open('data/test.png', 'wb').write(pic)
