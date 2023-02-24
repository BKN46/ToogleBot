import base64
import random

import requests

from toogle.configs import config

req_site = {
    "NovelAI": {
        "hosts": "https://api.novelai.net",
        "headers": {
            "authorization": f"Bearer {config.get('NovelAISecret')}",
            "origin": "https://novelai.net",
            "referer": "https://novelai.net/",
            "sec-ch-ua": '''"Google Chrome";v="105", "Not)A;Brand";v="8", "Chromium";v="105"''',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '''"Windows"''',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36",
        },
    },
}

proxies = {
    "http": None,
    "https": None,
}
sizes = [
    [512, 768],
    [640, 640],
    [768, 512],
]


def novel_ai_login(key):
    data = {"key": key}
    res = requests.post("https://api.novelai.net/user/login", json=data)
    return res.json()['accessToken']


def get_ai_generate(
    content_str, image_byte=None, site="NovelAI", model="safe-diffusion"
):
    path = "/ai/generate-image"
    hosts = req_site[site]["hosts"]
    headers = req_site[site]["headers"]
    url = hosts + path

    content_str = content_str.replace("，", ",")

    size = random.choice(sizes)
    payload = {
        "input": "masterpiece, best quality, " + content_str,
        "model": model,
        "parameters": {
            "height": size[1],
            "n_samples": 1,
            "noise": 0.2,
            "sampler": "nai_smea",
            "scale": 12,
            "seed": random.randint(0, 2**32 - 1),
            "steps": 28,
            "strength": 0.7,
            "uc": "nsfw, lowres, bad anatomy, text, error, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry",
            "ucPreset": 0,
            "qualityToggle": True,
            "autoSmea": True,
            "width": size[0],
        },
    }
    if image_byte:
        payload["parameters"]["image"] = get_base64_encode(image_byte)

    res = requests.post(url, json=payload, headers=headers, proxies=proxies) # type: ignore
    if len(res.text.split("\n")) < 3 or not res.text.split("\n")[2].startswith("data"):
        raise Exception(res.text)
    jpeg_b64_str = res.text.split("\n")[2][5:]
    return read_base64_pic(jpeg_b64_str)


def get_balance(site="NovelAI"):
    path = "/user/data"
    hosts = req_site[site]["hosts"]
    headers = req_site[site]["headers"]
    url = hosts + path
    res = requests.get(url, headers=headers, proxies=proxies) # type: ignore
    fixed_anlas = res.json()["subscription"]["trainingStepsLeft"][
        "fixedTrainingStepsLeft"
    ]
    paid_anlas = res.json()["subscription"]["trainingStepsLeft"][
        "purchasedTrainingSteps"
    ]
    return fixed_anlas + paid_anlas


def read_base64_pic(jpeg_b64_str):
    content = base64.b64decode(jpeg_b64_str)
    # open("tmp.jpeg", "wb").write(content)
    return content


def get_base64_encode(jpeg_btye):
    return base64.b64encode(jpeg_btye).decode("utf-8")


# get_ai_generate("arcueid brunestud, race vehicle, ")
# read_base64_pic()
# print(get_balance())
