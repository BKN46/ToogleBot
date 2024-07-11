import datetime
import math
import os
import time

import bs4
import requests
from PIL import Image, ImageDraw, ImageFont

# from toogle.exceptions import VisibleException

HIGH_LIGHT_PROD = [
    "A-1 Pictures",
    "BONES",
    "CloverWorks",
    "David Production",
    # "J.C.Staff",
    "Madhouse",
    "MADHOUSE",
    "MAD HOUSE",
    "MAPPA",
    # "P.A.WORKS",
    "Production I.G",
    # "Sunrise",
    # "Toei Animation",
    "ufotable",
    "UFOTABLE",
    "WIT Studio",
    "Kyoto Animation",
    "Studio Ghibli",
    "SHAFT",
    "Trigger",
    "TRIGGER",
    "扳机社",
    "动画工房",
]

def get_now_anime_season():
    now = datetime.datetime.now()
    month = ((now.month - 1) // 3) * 3 + 1
    time_str = f"{now.year}{month:02d}"
    return time_str


def get_str_similarity(str1: str, str2: str):
    len_str1, len_str2 = len(str1), len(str2)
    if len_str1 == 0 or len_str2 == 0:
        return 0
    if len_str1 > len_str2:
        len_str1, len_str2 = len_str2, len_str1
        str1, str2 = str2, str1
    dp = [0] * len_str1
    for i in range(len_str1):
        dp[i] = 1 if str1[i] == str2[0] else 0
    for j in range(1, len_str2):
        new_dp = [0] * len_str1
        new_dp[0] = 1 if str1[0] == str2[j] else 0
        for i in range(1, len_str1):
            if str1[i] == str2[j]:
                new_dp[i] = dp[i - 1] + 1
            else:
                new_dp[i] = max(new_dp[i - 1], dp[i])
        dp = new_dp
    return dp[-1] / min(len_str1, len_str2)


def save_anime_list(buffer_path: str = "data/anime/", ignore_cache: bool = False):
    anime_season = get_now_anime_season()
    pic_file = os.path.join(buffer_path, f"anime_{anime_season}.png")
    if os.path.exists(pic_file) and not ignore_cache:
        return pic_file

    # get html
    html_buffer = os.path.join(buffer_path, f"anime_{anime_season}.html")
    if os.path.exists(html_buffer):
        with open(html_buffer, "r") as f:
            html = bs4.BeautifulSoup(f.read(), "html.parser")
    else:
        url = f"https://yuc.wiki/{anime_season}"
        resp = requests.get(url)
        try:
            resp.raise_for_status()
        except Exception as e:
            raise Exception("爬虫网络连接失败")
        with open(html_buffer, "w") as f:
            f.write(resp.text)
        html = bs4.BeautifulSoup(resp.text, "html.parser")

    # parse html
    anime_list, now_weekday = [], ''
    detail_map = {}
    for line in html.findAll('div'):
        if line.find('td', {'class': 'date2'}):
            now_weekday = line.find('td', {'class': 'date2'}).text
            continue
        if line.attrs.get('style') != "float:left":
            detail_title = line.find('p', {'class': ['title_cn_r', 'title_cn_r1', 'title_cn_r2']})
            if detail_title:
                detail_title = detail_title.text.strip()
                detail_staff = {
                    x.split('：')[0]: x.split('：')[1] for x in
                    line.find('td', {'class': ['staff_r', 'staff_r1', 'staff_r2']}).text.replace('\u3000', '').split('\n')
                    if x and '：' in x
                }
                casts = [
                    x for x in
                    line.find('td', {'class': ['cast_r', 'cast_r1', 'cast_r2']}).text.split()
                    if x
                ]
                detail_map[detail_title] = {
                    'staff': detail_staff,
                    'casts': casts,
                    'type': line.find('td', {'class': ['type_c_r', 'type_b_r', 'type_a_r', 'type_d_r', 'type_e_r', 'type_f_r', 'type_g_r']}).text,
                    'tag': line.find('td', {'class': ['type_tag_r', 'type_tag_r1', 'type_tag_r2']}).text,
                }
            continue
        info = line.find('div', {"class": "div_date"})
        if not info:
            continue
        data = {
            'week_day': now_weekday,
            'anime_img': info.find('img').attrs['src'],
            'anime_time': info.findAll('p')[1].text,
            'anime_start_time': info.findAll('p')[0].text,
            'anime_name': line.find('td').text,
        }
        anime_list.append(data)

    # draw image
    total_anime_num = len(anime_list)
    per_row, col_size = 5, 240
    font_size = 12
    pic_size = (160, 200)
    size = (pic_size[0] * per_row, col_size * math.ceil(total_anime_num / per_row))
    img = Image.new("RGB", size, (14, 102, 85))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("toogle/plugins/compose/fonts/Arial Unicode MS Font.ttf", font_size)
    for anime in anime_list:
        idx = anime_list.index(anime)
        row = idx // per_row
        col = idx % per_row

        detail = [
            x for x in detail_map
            if get_str_similarity(anime['anime_name'], x) > 0.95
        ]
        if detail:
            detail = detail_map[detail[0]]
            prod = detail['staff'].get('动画制作', detail['staff'].get('制作', ''))
            if prod in HIGH_LIGHT_PROD:
                draw.rectangle(
                    (
                        (col * pic_size[0], row * col_size), 
                        (col * pic_size[0] + pic_size[0], row * col_size + col_size)
                    ),
                    fill="#C24615",
                )
            draw.text(
                (col * pic_size[0], row * col_size + font_size * 2),
                f"{prod} - {detail['type']}",
                font=font,
                fill=(255, 255, 255),
            )

        anime_img = Image.open(requests.get(anime['anime_img'], stream=True, timeout=5).raw)
        anime_img = anime_img.resize(pic_size, Image.Resampling.LANCZOS)
        img.paste(anime_img, (col * pic_size[0], row * col_size + (col_size - pic_size[1])))
        draw.text(
            (col * pic_size[0], row * col_size),
            f"{anime['week_day']} {anime['anime_time']} ({anime['anime_start_time']})",
            font=font,
            fill=(255, 255, 255),
        )
        anime_name = anime['anime_name'][:8] + "..." if len(anime['anime_name']) > 10 else anime['anime_name']
        draw.text(
            (col * pic_size[0], row * col_size + font_size),
            f"{anime_name}",
            font=font,
            fill=(255, 255, 255),
        )

    img.save(pic_file)
    return pic_file


if __name__ == "__main__":
    save_anime_list(ignore_cache=True)
