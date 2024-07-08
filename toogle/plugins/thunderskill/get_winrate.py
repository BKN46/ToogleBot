import math
import os
import io
import json
from typing import Tuple

import requests
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import numpy as np

save_path = "data/wt"

try:
    from toogle.utils import text2img, create_path, color_gradient
    create_path(save_path)
except Exception as e:
    pass

metajson_url = "https://controlnet.space/wt-data-project.data/metadata.json"
data_path = "https://controlnet.space/wt-data-project.data/joined/"
full_data_url = "https://controlnet.space/wt-data-project.data/rb_ranks_1.csv"
font_path = "toogle/plugins/compose/fonts/DejaVuSansMono-Bold.ttf"

proxies = { "http": None, "https": None}

def get_winrate_v():
    wt_winrate_v = "wt_winrate_v"

    res = requests.get(metajson_url, proxies=proxies) # type: ignore
    sort_date = sorted(json.loads(res.text), key=lambda x:x['date'], reverse=True)
    date_date = sort_date[0]['date']
    data_url = data_path + f"{date_date}.csv"
    file_name = wt_winrate_v + "_" + date_date
    wr_list = [x for x in os.listdir(save_path) if x.startswith(wt_winrate_v)]
    if file_name not in wr_list:
        # print("Downloading")
        for x in wr_list:
            os.remove(os.path.join(save_path, x))
        res = requests.get(data_url, proxies=proxies) # type: ignore
        open(os.path.join(save_path, file_name), 'wb').write(res.content)
    return open(os.path.join(save_path, file_name), 'r').read(), date_date


def get_winrate_n():
    wt_winrate_n = "wt_winrate_n"
    res = requests.get(metajson_url, proxies=proxies) # type: ignore
    sort_date = sorted(json.loads(res.text), key=lambda x:x['date'], reverse=True)
    date_date = sort_date[0]['date']
    file_name = wt_winrate_n + "_" + date_date
    wr_list = [x for x in os.listdir(save_path) if x.startswith(wt_winrate_n)]
    if file_name not in wr_list:
        # print("Downloading")
        for x in wr_list:
            os.remove(os.path.join(save_path, x))
        res = requests.get(full_data_url, proxies=proxies) # type: ignore
        open(os.path.join(save_path, file_name), 'wb').write(res.content)
    return open(os.path.join(save_path, file_name), 'r').read(), date_date


def parse_winrate_n():
    raw, date = get_winrate_n()
    header = "nation,cls,date,rb_br,rb_lower_br,rb_battles_sum,rb_battles_mean,rb_win_rate,rb_air_frags_per_battle,rb_air_frags_per_death,rb_ground_frags_per_battle,rb_ground_frags_per_death".split(',')
    wr_dict = {}
    for line in raw.split('\n')[1:]:
        if not line:
            continue
        line = line.strip().split(',')
        if line[1] != "Ground_vehicles":
            continue
        if line[2] != date:
            continue
        if line[0] not in wr_dict:
            wr_dict[line[0]] = {}
        wr_dict[line[0]][line[4]] = {
            'num': line[5],
            'wr': line[7]
        }
    return wr_dict, date


def draw_winrate_n_text():
    res, date = parse_winrate_n()
    whitespace = 10
    output_text = f"{date + ' Realistic Battle':^{whitespace * (len(res) + 1)}}\n\n" + " " * whitespace
    rank_dict = {}
    for nation, nation_data in res.items():
        output_text += f"{nation:^{whitespace}}"
        for rank, res_data in nation_data.items():
            if rank not in rank_dict:
                rank_dict[rank] = {}
            rank_dict[rank][nation] = res_data
    output_text += f"\n\n"

    rank_list = sorted([(k, v) for k, v in rank_dict.items()], key=lambda x: float(x[0]), reverse=True)
    for rank, rank_data in rank_list:
        output_text += f"{rank:^{whitespace}}"
        for nation, nation_data in rank_data.items():
            output_text += f"{float(nation_data['wr']):^{whitespace}.2f}"
        output_text += "\n"
        output_text += " " * whitespace
        for nation, nation_data in rank_data.items():
            output_text += f"{int(float(nation_data['num'])):^{whitespace}}"
        output_text += "\n \n"

    # print(output_text)
    return text2img(
        output_text,
        font_path="toogle/plugins/compose/fonts/DejaVuSansMono-Bold.ttf",
        word_size=15,
        max_size=(2000, 8000),
        font_height_adjust=4,
    )


def color_gradient(
    c1: Tuple[int, int, int],
    c2: Tuple[int, int, int],
    v: float,
    mid_c: Tuple[int, int, int] = (255, 255, 255),
) -> Tuple[int, int, int]:
    if v < 0:
        return c1
    elif v > 1:
        return c2
    elif v <= 0.5:
        return (
            int(c1[0] + (mid_c[0] - c1[0]) * v * 2),
            int(c1[1] + (mid_c[1] - c1[1]) * v * 2),
            int(c1[2] + (mid_c[2] - c1[2]) * v * 2),
        )
    else:
        return (
            int(c2[0] + (mid_c[0] - c2[0]) * (1 - v) * 2),
            int(c2[1] + (mid_c[1] - c2[1]) * (1 - v) * 2),
            int(c2[2] + (mid_c[2] - c2[2]) * (1 - v) * 2),
        )


def draw_winrate_n():
    res, date = parse_winrate_n()
    whitespace = 10
    font_size = 15
    block_width, block_height = 100, 20
    font = PIL.ImageFont.truetype(font_path, font_size)
    
    gen_image = PIL.Image.new(
        "RGBA",
        (1270, 2150),
        (255, 255, 255),
    )
    draw = PIL.ImageDraw.Draw(gen_image)
    draw.text(
        (block_width, 20),
        date + ' Ground Realistic Battle',
        (10, 10, 10),
        font=font,
    )
    
    rank_dict = {}
    tmp_x = block_width * 2
    for nation, nation_data in res.items():
        draw.text(
            (tmp_x, 50),
            nation,
            (10, 10, 10),
            font=font,
        )
        tmp_x += block_width
        for rank, res_data in nation_data.items():
            if rank not in rank_dict:
                rank_dict[rank] = {}
            rank_dict[rank][nation] = res_data

    rank_list = sorted([(k, v) for k, v in rank_dict.items()], key=lambda x: float(x[0]), reverse=True)

    tmp_x, tmp_y = block_width, 70
    for rank, rank_data in rank_list:
        tmp_x = block_width
        draw.text(
            (tmp_x, tmp_y),
            f"{rank}",
            (10, 10, 10),
            font=font,
        )
        tmp_x += block_width
        for nation, nation_data in rank_data.items():
            wr = float(nation_data['wr'])
            color = color_gradient(
                (255, 0, 0),
                (0, 255, 0),
                # math.sqrt(wr / 100) if wr > 50 else math.pow(wr / 100, 2)
                ((wr - 10) / 90)
            )
            if wr == 0:
                color = (130, 130, 130)
            draw.rectangle(
                (tmp_x, tmp_y, tmp_x + block_width, tmp_y + block_height * 2),
                fill = color,
            )
            draw.text(
                (tmp_x, tmp_y),
                f"{wr:.2f}",
                (10, 10, 10),
                font=font,
            )
            tmp_x += block_width
        tmp_x = block_width * 2
        tmp_y += block_height
        for nation, nation_data in rank_data.items():
            draw.text(
                (tmp_x, tmp_y),
                f"{int(float(nation_data['num']))}",
                (10, 10, 10),
                font=font,
            )
            tmp_x += block_width
        tmp_y += block_height * 2

    img_bytes = io.BytesIO()
    gen_image.save(img_bytes, format="PNG")
    return img_bytes.getvalue()


if __name__ == "__main__":
    # draw_winrate_n()
    import io
    import time
    start_time = time.time()
    pic = draw_winrate_n()
    open('data/test.jpg', 'wb').write(pic)
    print(f"use time: {time.time() - start_time:.4f}")
