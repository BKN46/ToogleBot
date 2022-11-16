import nonebot
from fastapi import FastAPI

app: FastAPI = nonebot.get_app()


@app.get("/api")
async def custom_api():
    return {"message": "Hello, world!"}
