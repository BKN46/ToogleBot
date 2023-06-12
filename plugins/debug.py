import json
import random
import re
import time
from typing import Any, Tuple
from datetime import datetime

import nonebot
from nonebot import get_bot, get_bots, get_driver
from nonebot.params import RegexGroup, EventMessage
from nonebot.plugin import on_message, on_regex
from nonebot.matcher import Matcher
from nonebot.adapters.mirai2.event.message import MessageEvent
from nonebot.adapters.mirai2.event.message import MessageSource

from toogle.configs import config
from toogle.message import MessageChain
from toogle.nonebot2_adapter import bot_get_all_group, bot_send_message, bot_exec, PluginWrapper, admin_user_checker, worker_shutdown
from toogle.utils import get_main_groups, is_admin

driver = get_driver()
broadcast_matcher = on_regex("^broadcast (.*)$", rule=admin_user_checker)

async def handle_broadcast(
    foo: Tuple[Any, ...] = RegexGroup(),
):
    content = foo[0]
    for group_id in get_main_groups():
        await bot_send_message(group_id, MessageChain.plain(content))
        time.sleep(random.random() * 4 + 1)
    await broadcast_matcher.send("Done")

broadcast_matcher.append_handler(handle_broadcast)


debug_matcher = on_regex(r"^debug (.*)\|?(.*)$", rule=admin_user_checker)

async def handle_debug(
    foo: Tuple[Any, ...] = RegexGroup(),
):
    content = foo[0]
    para = {}
    if foo[1]:
        para = {
            x.split("=")[0]: x.split("=")[1]
            for x in foo[1].split()
        }
    res = await bot_exec(content, **para)
    await debug_matcher.send(json.dumps(res, indent=2, ensure_ascii=False))

debug_matcher.append_handler(handle_debug)


shutdown_matcher = on_regex(r"^\.shutdown(.*)", rule=admin_user_checker)

async def handle_shutdown(
    foo: Tuple[Any, ...] = RegexGroup(),
):
    await worker_shutdown()
    await shutdown_matcher.send("Goodbye~")
    exit()

shutdown_matcher.append_handler(handle_debug)


@driver.on_shutdown
async def do_something():
    nonebot.logger.warning("Shutting down...") # type: ignore
    await worker_shutdown()
