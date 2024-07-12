import io
import json
import random
import re
import tempfile
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
import shshsh

from toogle.configs import config
from toogle.index import reload_plugins, export_plugins
from toogle.message import MessageChain
from toogle.message_handler import MESSAGE_HISTORY
from toogle.nonebot2_adapter import bot_get_all_group, bot_send_message, bot_exec, PluginWrapper, admin_user_checker, worker_shutdown
from toogle.utils import get_main_groups, is_admin
from plugins.load import MATCHERS, load_plugins

driver = get_driver()

# Broadcast
broadcast_matcher = on_regex("^broadcast (.*)$", rule=admin_user_checker)

async def handle_broadcast(
    foo: Tuple[Any, ...] = RegexGroup(),
):
    content = foo[0]
    for group_id in get_main_groups():
        bot_send_message(group_id, MessageChain.plain(content))
        time.sleep(random.random() * 4 + 1)
    await broadcast_matcher.send("Done")

broadcast_matcher.append_handler(handle_broadcast)

# Reload plugin
reload_plugin_matcher = on_regex("^\.reload$", rule=admin_user_checker)

async def handle_reload_plugin(
    foo: Tuple[Any, ...] = RegexGroup(),
):
    use_time = reload_plugins()
    load_plugins()
    await reload_plugin_matcher.send(f"Reloaded {len(export_plugins)} export modules ({len(MATCHERS)} in matcher) in {use_time:.2f}ms")

reload_plugin_matcher.append_handler(handle_reload_plugin)

# General debug
debug_matcher = on_regex(r"^debug \[(.*)\](.*)$", rule=admin_user_checker)

async def handle_debug(
    foo: Tuple[Any, ...] = RegexGroup(),
):
    content = foo[0]
    para = {}
    if foo[1]:
        para = {
            x.split("=")[0]: x.split("=")[1] if not x.split("=")[1].isnumeric() else int(x.split("=")[1])
            for x in foo[1].split()
        }
    await debug_matcher.send(f"Running: {content} with {para}")
    res = await bot_exec(content, **para)
    await debug_matcher.send(json.dumps(res, indent=2, ensure_ascii=False))

debug_matcher.append_handler(handle_debug)


# Shutdown
shutdown_matcher = on_regex(r"^\.shutdown(.*)", rule=admin_user_checker)

async def handle_shutdown(
    foo: Tuple[Any, ...] = RegexGroup(),
):
    await worker_shutdown()
    await shutdown_matcher.send("Goodbye~")
    exit()

shutdown_matcher.append_handler(handle_debug)


# Shell exec
sh_exec_matcher = on_regex(r"^\.sh(.*)", rule=admin_user_checker)

async def handle_sh_exec(
    foo: Tuple[Any, ...] = RegexGroup(),
):
    cmds = foo[0].split("|")
    res = shshsh.I >> cmds[0]
    if len(cmds) > 1:
        for cmd in cmds[1:]:
            res = res | cmd
    res.wait(timeout=3)
    await sh_exec_matcher.send(res.stdout.read().decode("utf-8"))

sh_exec_matcher.append_handler(handle_sh_exec)


# History debug
history_matcher = on_regex(r"^\.history(.*)", rule=admin_user_checker)

async def handle_debug_history(
    foo: Tuple[Any, ...] = RegexGroup(),
):
    history = MESSAGE_HISTORY.recent()
    if not history:
        await history_matcher.send("No history")
        return
    text = "\n-----\n".join([f"[{x.time:.2f}]{x.member.id}: {x.message.asDisplay()}" for x in history])
    await history_matcher.send(text)

history_matcher.append_handler(handle_debug_history)


@driver.on_shutdown
async def do_something():
    nonebot.logger.warning("Shutting down...") # type: ignore
    await worker_shutdown()
