import time

from nonebot.rule import to_me
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.plugin import on_command

echo = on_command("echo")


@echo.handle()
async def handle_echo(message: Message = CommandArg()):
    time.sleep(5)
    await echo.send(message=message)