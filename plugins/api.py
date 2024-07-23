import datetime
import json
import time
import nonebot
from fastapi import FastAPI, Request

from toogle.message import Image, MessageChain, Plain, At
from toogle.nonebot2_adapter import bot_send_message

app: FastAPI = nonebot.get_app()


@app.get("/api")
async def custom_api():
    return {"message": "Hello, world!"}


@app.post("/api")
async def custom_post_api(request: Request):
    data = await request.json()
    req_body = json.dumps(data, ensure_ascii=False)
    print(f"{datetime.datetime.now()}\t{request.client}\t{req_body}", file=open("data/api.log", "a"))
    return {"msg": "ok"}


SEND_LIMIT = {}

@app.post("/send")
async def send_message(request: Request):
    '''
    POST /send
    BODY {
        "secret": "your_secret",
        "message": "your_message_str" | [{
            "type": "text",
            "content": "..."
        }]
    }
    '''
    data = await request.json()
    try:
        secrets = json.load(open("data/send_api.json", "r"))
    except Exception as e:
        secrets = {}
    if data["secret"] not in secrets:
        return {"message": "error", "error": "invalid secret"}

    info = secrets[data["secret"]]
    
    if data["secret"] not in SEND_LIMIT:
        SEND_LIMIT[data["secret"]] = {
            "last_time": time.time(),
            "count": 0,
        }
    
    if time.time() - SEND_LIMIT[data["secret"]]["last_time"] < 60:
        if SEND_LIMIT[data["secret"]]["count"] > info["qpm"]:
            return {"message": "error", "error": f"rate limit exceeded: {info['qpm']} qpm"}
        SEND_LIMIT[data["secret"]]["count"] += 1
    else:
        SEND_LIMIT[data["secret"]]["last_time"] = time.time()
        SEND_LIMIT[data["secret"]]["count"] = 0

    group, msg = info["group"], data["message"]

    if isinstance(msg, list):
        tmp_message = []
        for m in msg:
            if m["type"] == "text":
                tmp_message.append(Plain(m["content"]))
            elif m["type"] == "image":
                tmp_message.append(Image(base64=m["content"]))
            elif m["type"] == "at":
                tmp_message.append(At(int(m["content"])))
        msg = MessageChain(tmp_message)

    bot_send_message(group, msg)
    return {"message": "success", "send_to": group}
