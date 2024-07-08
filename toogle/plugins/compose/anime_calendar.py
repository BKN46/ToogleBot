import datetime
import math
import os
import time

import bs4
import requests
from PIL import Image, ImageDraw, ImageFont

# from toogle.exceptions import VisibleException

def get_now_anime_season():
    now = datetime.datetime.now()
    month = ((now.month - 1) // 3) * 3 + 1
    time_str = f"{now.year}{month:02d}"
    return time_str


def save_anime_list(buffer_path: str = "data/anime/", ignore_cache: bool = False):
    anime_season = get_now_anime_season()
    pic_file = os.path.join(buffer_path, f"anime_{anime_season}.png")
    if os.path.exists(pic_file) and not ignore_cache:
        return pic_file

    # get html
    html_buffer = os.path.join(buffer_path, f"anime_{anime_season}.html")
    if os.path.exists(pic_file):
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
    for line in html.findAll('div'):
        if line.find('td', {'class': 'date2'}):
            now_weekday = line.find('td', {'class': 'date2'}).text
            continue
        if line.attrs.get('style') != "float:left":
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
    per_row, col_size = 5, 180
    size = (120 * per_row, col_size * math.ceil(total_anime_num / per_row))
    img = Image.new("RGB", size, (14, 102, 85))
    pic_size = (120, 150)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("toogle/plugins/compose/fonts/Arial Unicode MS Font.ttf", 12)
    for anime in anime_list:
        idx = anime_list.index(anime)
        row = idx // per_row
        col = idx % per_row
        anime_img = Image.open(requests.get(anime['anime_img'], stream=True, timeout=5).raw)
        anime_img = anime_img.resize(pic_size, Image.Resampling.LANCZOS)
        img.paste(anime_img, (col * pic_size[0], row * col_size + (col_size - pic_size[1])))
        draw.text(
            (col * pic_size[0], row * col_size),
            f"{anime['week_day']} {anime['anime_time']}",
            font=font,
            fill=(255, 255, 255),
        )
        anime_name = anime['anime_name'][:8] + "..." if len(anime['anime_name']) > 10 else anime['anime_name']
        draw.text(
            (col * pic_size[0], row * col_size + 12),
            f"{anime_name}",
            font=font,
            fill=(255, 255, 255),
        )

    img.save(pic_file)
    return pic_file


if __name__ == "__main__":
    save_anime_list(ignore_cache=True)
