import os
import json

import requests

from toogle.utils import text2img, create_path


metajson_url = "https://controlnet.space/wt-data-project.data/metadata.json"
data_path = "https://controlnet.space/wt-data-project.data/joined/"
full_data_url = "https://controlnet.space/wt-data-project.data/rb_ranks_1.csv"
save_path = "data/wt"
create_path(save_path)

proxies = { "http": None, "https": None}

def get_winrate_v():
    wt_winrate_v = "wt_winrate_v"

    res = requests.get(metajson_url, proxies=proxies) # type: ignore
    date_date = json.loads(res.text)[-1]['date']
    data_url = data_path + f"{date_date}.csv"
    file_name = wt_winrate_v + "_" + date_date
    wr_list = [x for x in os.listdir(save_path) if x.startswith(wt_winrate_v)]
    if file_name not in wr_list:
        print("Downloading")
        for x in wr_list:
            os.remove(os.path.join(save_path, x))
        res = requests.get(data_url, proxies=proxies) # type: ignore
        open(os.path.join(save_path, file_name), 'wb').write(res.content)
    return open(os.path.join(save_path, file_name), 'r').read(), date_date


def get_winrate_n():
    wt_winrate_n = "wt_winrate_n"
    res = requests.get(metajson_url, proxies=proxies) # type: ignore
    date_date = json.loads(res.text)[-1]['date']
    file_name = wt_winrate_n + "_" + date_date
    wr_list = [x for x in os.listdir(save_path) if x.startswith(wt_winrate_n)]
    if file_name not in wr_list:
        print("Downloading")
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
        if line[2] != date:
            continue
        if line[0] not in wr_dict:
            wr_dict[line[0]] = {}
        wr_dict[line[0]][line[4]] = {
            'num': line[5],
            'wr': line[7]
        }
    return wr_dict, date


def draw_winrate_n():
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
        font_path="toogle/plugins/compose/DejaVuSansMono-Bold.ttf",
        word_size=15,
        max_size=(2000, 8000),
        font_height_adjust=4,
    )


if __name__ == "__main__":
    # draw_winrate_n()
    import PIL.Image
    import io
    pic = draw_winrate_n()
    PIL.Image.open(io.BytesIO(pic)).show()
