import json
import math
import os
import random
import re
from posixpath import split

import bs4
import PIL.Image
import PIL.ImageColor
import PIL.ImageDraw
import PIL.ImageFont
import requests

SAVE_PATH = "data/waifu_rank.png"
FONT_TYPE = "toogle/plugins/compose/Arial Unicode MS Font.ttf"

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


def get_designated_search(sexual, search_list):
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
                    for x in search_list
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
    page_links = soup.find("td", {"class": "pager_links"})
    if page_links:
        max_page = int(page_links.findAll("span")[-1].text.strip())
        req_url += f"&page={random.randint(1, max_page)}"
        res = requests.get(req_url, headers=header, data=body, timeout=20)
        soup = bs4.BeautifulSoup(res.text, "html.parser")
    chara_list = soup.findAll("a", {"target": "_blank"})
    if len(chara_list) == 0:
        raise ACError("无符合条件角色，请至animecharactersdatabase确认")
    chara_id = random.choice(chara_list).attrs["href"].split("?id=")[-1]
    return get_anime_character(chara_id), req_url


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
        base = soup.find(id="besttable").find(text=key)
        if base:
            if base.parent.name == "a":
                return base.parent.parent.parent.td.text
            else:
                return base.parent.parent.td.text
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
        base = soup.find(id="sidephoto").find(text=key)
        if base:
            if base.parent.name == "a":
                return base.parent.parent.parent.td.text
            else:
                return base.parent.parent.td.text
        else:
            return ""

    soup = bs4.BeautifulSoup(res.text, "html.parser")
    profile_pic = soup.find(id="profileimage").attrs.get("src")
    profile_name = (
        soup.find(id="mainframe1")
        .find(text="Share ▼")
        .parent.parent.text.split("|")[0]
        .strip()
    ).split(", ")[0]
    profile_name = re.sub(r"(\(.*?\))|(（.*?）)", "", profile_name).strip()
    en_name = soup.find(id="main1").find("a", {"class": "fgw"}).text
    if len(profile_name) < 1 or profile_name == "\xa0":
        profile_name = en_name
    profile_heat = (
        soup.find(id="main1").find("a", {"href": "seriesfinder3.php"}).text.split()[0]
    )
    profile_year = soup.find("a", {"href": "year_trivia.php"}).text.split()[0]
    profile_src = (
        soup.find(id="sidephoto")
        .find(text="From")
        .parent.parent.find("a")
        .attrs["href"]
        .split("?id=")[-1]
    )

    profile_vs_matches = soup.find(id="mainframe2").findAll(id="besttable")
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
            "id": x.a.attrs["href"].split("/")[-1],
            "rate": parse_rate(x),
        }
        for x in soup.find(id="browserItemList").contents
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
        for x in soup.find("div", {"id", "columnSearchB"}).findAll(
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

    if soup.find("h2").text == "å\x91\x9cå\x92\x95ï¼\x8cå\x87ºé\x94\x99äº\x86":
        return {"score": 0, "rank": 99999, "popularity": 0}

    def get_rank():
        rank = soup.find("div", {"class": "global_score"}).find(
            "small", {"class": "alarm"}
        )
        if rank:
            return int(rank.text[1:])
        else:
            return 99999

    res = {
        "score": float(soup.find("span", {"property": "v:average"}).text),
        "rank": get_rank(),
        "popularity": int(soup.find("span", {"property": "v:votes"}).text),
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


def get_anime_character_popularity(acdb_id=None, sexual="f"):
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
        "pic": acdb_pic,
        "src": acdb_src["title"] if acdb_src["title"] else acdb_src["title_en"],
        "type": acdb_raw["类型"],
        "vs": acdb_raw["vs"],
        "acdb_heat": acdb_raw["热度"],
        "bgm_score": bgm_src_detail["score"],
        "bgm_rank": bgm_src_detail["rank"],
        "bgm_heat": bgm_src_detail["popularity"],
    }

    score, rank = score_calc(res_data)
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


def score_calc(res_data):
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
        print(f"{tmp['name']} {tmp['score']} {tmp['rank']}")

    for _ in range(5):
        tmp = get_anime_character_popularity()[2]
        print(f"{tmp['name']} {tmp['score']} {tmp['rank']}")


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
            PIL.Image.ANTIALIAS,
        )
    else:
        return img.resize(
            (int(img.size[0] * max_height / img.size[1]), max_height),
            PIL.Image.ANTIALIAS,
        )


def ranking_compose(waifu_data_list, highlight=0):
    SIZE[1] = PIC_SIZE[1] * len(waifu_data_list)
    gen_image = PIL.Image.new("RGBA", SIZE, (255, 255, 255))

    bg_num_font = PIL.ImageFont.truetype(FONT_TYPE, 200)
    name_font = PIL.ImageFont.truetype(FONT_TYPE, 60)
    src_font = PIL.ImageFont.truetype(FONT_TYPE, 30)
    score_font = PIL.ImageFont.truetype(FONT_TYPE, 70)
    rank_font = PIL.ImageFont.truetype(FONT_TYPE, 180)
    user_font = PIL.ImageFont.truetype(FONT_TYPE, 50)

    for index, waifu_data in enumerate(waifu_data_list):
        user_name = waifu_data["id"]
        ac_data = waifu_data["data"]
        ac_stand = waifu_data["rank"]

        image = max_resize(buffered_url_pic(ac_data["pic"])).convert("RGBA")
        ac_name = ac_data["name"]
        ac_src = ac_data["src"]
        ac_score = ac_data["score"]
        ac_rank = ac_data["rank"]

        word_box = PIL.Image.new(
            "RGBA", (SIZE[0] - PIC_SIZE[0], PIC_SIZE[1]), (255, 255, 255, 0)
        )
        draw = PIL.ImageDraw.Draw(word_box)

        std_text = f"{ac_stand}"
        # std_text_size = draw.textsize(std_text, font=bg_num_font)
        draw.text(
            (SIZE[0] - 350 - len(std_text) * 120, 200),
            std_text,
            BG_COLOR[(index + 1) % 2],
            font=bg_num_font,
        )
        if ac_stand == highlight:
            pic_bg = PIL.Image.new("RGBA", (SIZE[0], PIC_SIZE[1]), BG_COLOR[2])
        else:
            pic_bg = PIL.Image.new("RGBA", (SIZE[0], PIC_SIZE[1]), BG_COLOR[index % 2])
        gen_image.paste(pic_bg, (0, index * PIC_SIZE[1]))

        offset_x = int((PIC_SIZE[0] - image.size[0]) / 2)
        offset_y = int((PIC_SIZE[1] - image.size[1]) / 2)
        gen_image.paste(image, (offset_x, index * PIC_SIZE[1] + offset_y), image)

        draw.text((20, 40), f"{ac_name}", (0, 0, 0), font=name_font)
        draw.text((20, 110), f"《{ac_src}》", (0, 0, 0), font=src_font)
        draw.text((0, 160), f"{ac_rank}", RANK_COLOR[ac_rank], font=rank_font)
        draw.text((370, 180), f"SCORE {ac_score: .2f}", (0, 0, 0), font=score_font)
        draw.text((370, 260), f"对象是 {user_name}", (0, 0, 0), font=user_font)
        draw.text((540, 310), f"{waifu_data['qq']}", (50, 50, 50), font=src_font)
        draw.text(
            (900, 40),
            f"[ {ac_data['def']} ]",
            BG_COLOR[(index + 1) % 2],
            font=score_font,
        )
        gen_image.paste(word_box, (PIC_SIZE[0], index * PIC_SIZE[1]), word_box)

    gen_image.save(SAVE_PATH)
    return SAVE_PATH


if __name__ == "__main__":
    # print(get_random_anime_character("f"))
    # print(get_anime_character("102632")[1])
    # print(get_anime_src("107190"))
    # print(get_bgm_src_detail("137458"))
    # print(bgm_character_search("エアリス"))
    # print(get_anime_character_popularity(acdb_id="15442")[0])
    # print(get_keyword_explain())
    print(get_designated_search("f", ["红发", "轻小说"])[1])
    # calc_confirm()
