import asyncio
import base64
import io
import json
import time

import websockets

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont

from toogle.utils import list2img

font_path = "toogle/plugins/compose/fonts/Arial Unicode MS Font.ttf"

async def wolfram_alpha_query(query):
    init = {
        "category": "results",
        "type": "init",
        "lang": "en",
        "wa_pro_s": "",
        "wa_pro_t": "",
        "wa_pro_u": "",
        "exp": int(time.time() * 1000),
        "displayDebuggingInfo": False,
        "messages": [],
    }
    query = {
        "type": "newQuery",
        "locationId": "0o5z1",
        "language": "en",
        "displayDebuggingInfo": False,
        "yellowIsError": False,
        "requestSidebarAd": False,
        "category": "results",
        "input": query,
        "i2d": False,
        "assumption": [],
        "apiParams": {},
        "file": None,
    }
    async with websockets.connect( # type: ignore
        "wss://www.wolframalpha.com/n/v1/api/fetcher/results"
    ) as websocket:
        await websocket.send(json.dumps(init))
        res = await websocket.recv()
        assert json.loads(res)["type"] == "ready"
        await websocket.send(json.dumps(query))
        res_list = []
        while True:
            try:
                res = await asyncio.wait_for(websocket.recv(), 2)
                res = json.loads(res)
                if res['type'] == "queryComplete":
                    break
                res_list.append(res)
            except asyncio.TimeoutError as e:
                break
    return res_list


def parse_query(query_result_list):
    query_result_list = [x for x in query_result_list if x['type'] == "pods"]
    if len(query_result_list) == 0:
        return b''
    result_list = []
    for item in query_result_list:
        result_list += item['pods']
    render_list = []
    for item in result_list:
        title = item['title']
        render_list.append(title)
        if 'subpods' in item:
            for sub_item in item['subpods']:
                if 'img' in sub_item:
                    render_list.append(base64.b64decode(sub_item['img']['data']))
    return list2img(
        render_list,
        font_path=font_path,
        word_size=15,
        padding=(10, 10),
        max_size=(800, 2500),
        font_color=(87, 161, 222),
    )



async def get_wolfram_alpha_query(query):
    res = await wolfram_alpha_query(query)
    return parse_query(res)


if __name__ == "__main__":
    start_time = time.time()
    res = asyncio.get_event_loop().run_until_complete(wolfram_alpha_query("integral of x^e^x"))
    # res = parse_query(json.load(open('tmp.json', 'r')))
    print("Using time: ", time.time() - start_time)
    print(res)
    # PIL.Image.open(io.BytesIO(res)).show()
