from datetime import datetime
import json
from typing import Any, Tuple

from nonebot import get_bot, get_bots
from nonebot.params import RegexGroup, EventMessage
from nonebot.plugin import on_message, on_regex
from nonebot.adapters.mirai2.event.message import MessageEvent
from nonebot.adapters.mirai2.event.message import MessageSource

from toogle.configs import config
from toogle.message import MessageChain
from toogle.nonebot2_adapter import bot_get_all_group, bot_send_group
from toogle.utils import get_main_groups, is_admin


echo = on_regex("^broadcast (.*)$")

async def handle_debug(foo: Tuple[Any, ...] = RegexGroup()):
    content = foo[0]
    for group_id in get_main_groups():
        await bot_send_group(group_id, MessageChain.plain(content))
    await echo.send("Done")

echo.append_handler(handle_debug)
