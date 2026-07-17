import datetime
import json
import time

import flask

import configs
from toogle.message import json_to_msg
from toogle.adapter import bot_send_message
from toogle.membership import recv_afdian_msg

app = flask.Flask(__name__)

@app.get("/api")
async def custom_api():
    return {"message": "Hello, world!"}


@app.post("/api")
async def custom_post_api():
    data = flask.request.json
    req_body = json.dumps(data, ensure_ascii=False)
    print(f"{datetime.datetime.now()}\t{flask.request.remote_addr}\t{req_body}", file=open("log/api.log", "a"))
    return {"msg": "ok"}


@app.post("/afdian")
async def afdian_webhook_api():
    data = flask.request.json
    req_body = json.dumps(data, ensure_ascii=False)
    recv_afdian_msg(data)
    print(f"{datetime.datetime.now()}\t{flask.request.remote_addr}\t{req_body}", file=open("log/afdian.log", "a"))
    return {"ec": 200, "em": "ok"}


SEND_LIMIT = {}

@app.post("/send")
async def send_message():
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
    data = flask.request.json
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

    print(f"{datetime.datetime.now()}\t{flask.request.remote_addr}\t/send\t{group}\t{len(data['message'])}", file=open("log/api.log", "a"))

    msg = json_to_msg(msg)
    bot_send_message(group, msg)

    return {"message": "success", "send_to": group}


def start_api():
    app.run(host="0.0.0.0", port=int(configs.config.get("API_PORT", 8080)))
