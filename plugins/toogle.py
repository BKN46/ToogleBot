import time
from typing import Any, Tuple

import nonebot
from nonebot.adapters import Message
from nonebot.params import RegexGroup
from nonebot.plugin import on_message, on_regex
from nonebot.rule import to_me

from toogle.configs import config

echo = on_regex("^22222$")


async def handle_echo(foo: Tuple[Any, ...] = RegexGroup()):
    await echo.send("22222")


echo.append_handler(handle_echo)

from toogle.index import export_plugins, linear_handler

if config.get("CONCURRENCY") == 'true':
    for plugin in export_plugins:
        matcher = on_regex(plugin.plugin.trigger)
        matcher.append_handler(plugin.ret)
        nonebot.logger.success(f"[{plugin.plugin.name}] imported") # type: ignore
else:
    matcher = on_message()
    matcher.append_handler(linear_handler.ret)
    nonebot.logger.success(f"Toogle linear handler imported") # type: ignore


get_help = on_regex("^#help#")


@get_help.handle()
async def handle_help():
    res = []
    for mod in export_plugins:
        res.append(
            f"{mod.plugin.name} :\n【触发正则】 {mod.plugin.trigger}\n【说明】 {mod.plugin.readme}"
        )
    res.append("\n大黄狗 Powered By BKN\n")
    await get_help.send(f"\n{'#'*15}\n".join(res))
