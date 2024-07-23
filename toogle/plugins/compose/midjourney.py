import json
import time
import requests

import toogle.configs as configs


TOKEN = configs.config.get("ZhishuyunToken", "")
URL = f"https://api.zhishuyun.com/midjourney/imagine?token={TOKEN}"

VARIATIONS = {
    "小变化": "low_variation",
    "大变化": "high_variation",
    "局部变化": "variation_region",
    "拉远2倍": "zoom_out_2x",
    "拉远1.5倍": "zoom_out_1_5x",
    "镜头左移": "pan_left",
    "镜头右移": "pan_right",
    "镜头上移": "pan_up",
    "镜头下移": "pan_down"
}

def generate_image(prompt: str):
    headers = {
        "accept": "application/json",
    }
    
    translation = not prompt[0].isalpha()

    payload = {
        "prompt": prompt,
        "action": "generate",
        "translation": translation,
    }

    response = requests.post(URL, json=payload, headers=headers)
    return response.json()

    '''
    {
        "image_url": "https://platform.cdn.zhishuyun.com/midjourney/aa0e0680-f8a9-4fdb-88d3-d37b4e81357d.png?imageMogr2/thumbnail/!50p",
        "image_width": 1024,
        "image_height": 1024,
        "actions": [
            "upsample1",
            "upsample2",
            "upsample3",
            "upsample4",
            "reroll",
            "variation1",
            "variation2",
            "variation3",
            "variation4"
        ],
        "raw_image_url": "https://platform.cdn.zhishuyun.com/midjourney/aa0e0680-f8a9-4fdb-88d3-d37b4e81357d.png",
        "raw_image_width": 2048,
        "raw_image_height": 2048,
        "progress": 100,
        "image_id": "1265153638989299712",
        "task_id": "aa0e0680-f8a9-4fdb-88d3-d37b4e81357d",
        "success": true,
        "trace_id": "bd0c4f94-9786-4f34-9f83-7596d9ed43e2"
    }
    '''


def upsample_image(image_id: str, index: int):
    if index < 1 or index > 4:
        raise Exception("Index must be between 1 and 4")
    headers = {
        "accept": "application/json",
    }

    payload = {
        "action": f"upsample{index}",
        "image_id": image_id
    }

    response = requests.post(URL, json=payload, headers=headers)
    return response.json()
    '''
    {
        "image_url": "https://platform.cdn.zhishuyun.com/midjourney/9d318ac2-47ae-4cc6-ad0f-5b510678f431.png?imageMogr2/thumbnail/!50p",
        "image_width": 512,
        "image_height": 512,
        "actions": [
            "low_variation",
            "high_variation",
            "variation_region",
            "zoom_out_2x",
            "zoom_out_1_5x",
            "pan_left",
            "pan_right",
            "pan_up",
            "pan_down"
        ],
        "raw_image_url": "https://platform.cdn.zhishuyun.com/midjourney/9d318ac2-47ae-4cc6-ad0f-5b510678f431.png",
        "raw_image_width": 1024,
        "raw_image_height": 1024,
        "progress": 100,
        "image_id": "1265158488611356672",
        "task_id": "9d318ac2-47ae-4cc6-ad0f-5b510678f431",
        "success": true,
        "trace_id": "b1d648d8-27f9-4799-97cb-25057f99c866"
    }
    '''


def varient_image(image_id: str, index: int=1, variation: str="variation"):
    if index < 1 or index > 4:
        raise Exception("Index must be between 1 and 4")
    headers = {
        "accept": "application/json",
    }

    if variation == "variation":
        payload = {
            "action": f"variation{index}",
            "image_id": image_id
        }
    else:
        payload = {
            "action": VARIATIONS.get(variation, variation),
            "image_id": image_id
        }

    response = requests.post(URL, json=payload, headers=headers)
    return response.json()


def reroll_image(image_id: str):
    headers = {
        "accept": "application/json",
    }

    payload = {
        "action": f"reroll",
        "image_id": image_id
    }

    response = requests.post(URL, json=payload, headers=headers)
    return response.json()


def get_balance():
    application_id = configs.config.get("ZhishuyunApplicationId", "")
    token = configs.config.get("ZhishuyunApplicationToken", "")
    url = f"https://data.zhishuyun.com/api/v1/applications/{application_id}"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {token}"
    }

    response = requests.get(url, headers=headers)
    # print(response.json())
    return response.json()


if __name__ == "__main__":
    start_time = time.time()
    res = upsample_image("1265156394357620736", 1)
    use_time = time.time() - start_time
    print(json.dumps(res, indent=4, ensure_ascii=False))
    print(f"Time used: {use_time:.2f}s")
