import time
from typing import Tuple, Any

from nonebot.rule import to_me
from nonebot.adapters import Message
from nonebot.plugin import on_regex
from nonebot.params import RegexGroup

echo = on_regex("^22222$")


# @echo.handle()
async def handle_echo(foo: Tuple[Any, ...] = RegexGroup()):
    await echo.send("22222")

echo.append_handler(handle_echo)

from toogle.index import export_plugins

for plugin in export_plugins:
    matcher = on_regex(plugin.plugin.trigger)
    matcher.append_handler(plugin.ret)
