import nonebot
from fastapi import FastAPI, Request

from toogle.nonebot2_adapter import bot_send_message

app: FastAPI = nonebot.get_app()


@app.get("/api")
async def custom_api():
    return {"message": "Hello, world!"}


@app.post("/send")
async def send_message(request: Request):
    data = await request.json()
    group, msg = data["group"], data["message"]
    await bot_send_message(group, msg)
    return {"message": "success"}
