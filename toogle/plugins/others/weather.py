
import datetime
import io
import os
import random
import re
import time

import requests

DEBUG_MODE = False

try:
    from toogle.message import Image
except Exception as e:
    print("debug_mode")
    DEBUG_MODE = True

HEADER = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "sec-ch-ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "if-none-match": 'W/"6949f0a1-947e"',
}


def get_rainfall_graph():
    datetoday = datetime.datetime.now().strftime("%Y%m%d")
    pic_name = f"rainfall_{datetoday}.gif"
    if os.path.exists(f"data/{pic_name}"):
        return open(f"data/{pic_name}", "rb").read()
    else:
        for x in os.listdir("data"):
            if x.startswith("rainfall_"):
                os.remove(f"data/{x}")

    # t = int(time.time() * 1000)
    # url = "https://weather.cma.cn/api/channel"
    # params = {
    #     "id": "d3236549863e453aab0ccc4027105bad,339,92,45",
    #     "_": t
    # }
    # res = requests.get(url, params=params)
    # try:
    #     rainfall_pic = res.json()['data'][1]['image']
    # except Exception as e:
    #     return "获取国家气象局预报数据失败"
                
    # rainfall_pic = "https://weather.cma.cn" + rainfall_pic.split("?")[0]
    # pics = [
    #     rainfall_pic.replace("000002400", x)
    #     for x in ["000002400", "000004800", "000007200", "000009600", "000012000", "000014400", "000016800"]
    # ]
    
    pics = []
    for x in range(339, 346):
        HEADER['if-none-match'] = f'W/"{random.randint(1000000, 9999999)}-947e"'
        res = requests.get(f"https://weather.cma.cn/web/channel-{x}.html", headers=HEADER).text
        search_reg = r'(/file.*?")'
        search_res = re.findall(search_reg, res)
        if search_res:
            res = "https://weather.cma.cn" + search_res[0][:-1]
            pics.append(res)
            if DEBUG_MODE:
                print(f'added pic: {res}')
    if not pics:
        return "获取国家气象局预报数据失败"

    try:
        gif_frames = [
            Image.buffered_url_pic(x, return_PIL=True).compress(max_width=720)
            for x in pics
        ]
    except Exception as e:
        # if is_admin(message.member.id):
        #     return MessageChain.plain("\n".join(pics))
        return "获取国家气象局预报数据失败"


    img_bytes = io.BytesIO()
    gif_frames[0].save(
        img_bytes,
        format="GIF", # type: ignore
        save_all=True, # type: ignore
        append_images=gif_frames[1:], # type: ignore
        optimize=True, # type: ignore
        duration=1000, # type: ignore
        loop=0, # type: ignore
    )
    open(f"data/{pic_name}", "wb").write(img_bytes.getvalue())

    # return MessageChain.create([Image(url=x) for x in pics])
    return img_bytes.getvalue()


def get_weather_place_search(place_name):
    t = int(time.time() * 1000)
    url = f"https://weather.cma.cn/api/autocomplete?q={place_name}&limit=10&timestamp={t}"
    res = requests.get(url)
    for x in res.json()['data']:
        data = x.split("|")
        if data[1] == place_name:
            return data[0]
    return None


def get_weather_now(place_id):
    t = int(time.time() * 1000)
    url = f"https://weather.cma.cn/api/now/{place_id}"
    res = requests.get(url)
    data = res.json()['data']
    return data


if __name__ == "__main__":
    get_rainfall_graph()
