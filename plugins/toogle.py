from curses.ascii import isdigit
import datetime
import math
import re
from typing import Any, Tuple

import nonebot
from nonebot.matcher import Matcher
from nonebot.params import RegexGroup, EventMessage
from nonebot.plugin import on_message, on_regex
from nonebot.message import event_postprocessor

from nonebot.adapters.mirai2.event.message import MessageEvent, GroupMessage
from nonebot.adapters.mirai2.event import Event
from nonebot.adapters.mirai2 import MessageChain

from toogle.configs import config
from toogle.index import export_plugins, active_plugins
from toogle.message_handler import MESSAGE_HISTORY, RECALL_HISTORY
from toogle.nonebot2_adapter import PluginWrapper, bot_send_message
from toogle.msg_proc import chat_earn
from plugins.load import load_plugins

# ping trigger
echo = on_regex("^22222$")

async def handle_echo(foo: Tuple[Any, ...] = RegexGroup()):
    await echo.send("22222")

echo.append_handler(handle_echo)

# load plugins
load_plugins()

# /help
get_help_regex = f"^(#help#|\.help|/help|@{config['MIRAI_QQ'][0]})(.*)" # type: ignore
get_help = on_regex(get_help_regex)

async def handle_help(
    matcher: Matcher,
    event: MessageEvent,
    message: MessageChain = EventMessage(),
):
    def get_help_page(page, page_size=5):
        res = []
        total_page = math.ceil(len(export_plugins)/page_size)
        if page >= total_page:
            page = total_page - 1
        elif page < 0:
            page = 0
        p1, p2 = page * page_size, min((page + 1) * page_size, len(export_plugins))
        for mod in export_plugins[p1:p2]:
            res.append(
                f"{mod.plugin.name}\n【说明】 {mod.plugin.readme}"
            )
        return f"\n{'#'*15}\n".join(res) + f"\n\nPage {page + 1}/{total_page} (指令后加上序号翻页，也可具体查询功能名称)"

    def fuzz_search(content):
        res = []
        for mod in export_plugins:
            if content in mod.plugin.name or content in mod.plugin.trigger or content in mod.plugin.readme:
                line = f"{mod.plugin.name}\n【触发正则】 {mod.plugin.trigger}\n【说明】 {mod.plugin.readme}"
                if mod.plugin.price > 0:
                    line += f"\n【触发花费】 {mod.plugin.price}gb"
                if mod.plugin.interval > 0:
                    line += f"\n【触发间隔】 {mod.plugin.interval}秒"
                res.append(line)
        return f"\n{'#'*15}\n".join(res)

    message_pack = PluginWrapper.get_message_pack(event, message)
    search_content = re.search(get_help_regex, message_pack.message.asDisplay()).groups()[1].strip() # type: ignore
    if search_content == "--markdown":
        res = '\n'.join([f"{mod.plugin_class}: {mod.plugin.name}" for mod in export_plugins])
    elif not search_content:
        res = get_help_page(0)
    elif str.isdigit(search_content):
        res = get_help_page(int(search_content) - 1)
    else:
        res = fuzz_search(search_content)
    await get_help.send(res)

get_help.append_handler(handle_help)


@event_postprocessor
async def message_post_process(event: MessageEvent, message: MessageChain = EventMessage()):
    # record history
    message_pack = PluginWrapper.get_message_pack(event, message)
    MESSAGE_HISTORY.add(message_pack.group.id, message_pack) # type: ignore

    # do active plugins
    for plugin in active_plugins:
        if str(message_pack.group.id) in config['CHAT_GROUP_LIST'] and plugin.is_trigger_random(message=message_pack):
            message_ret = await plugin.ret_wrapper(message_pack)
            if message_ret:
                await bot_send_message(message_pack, message_ret)

    # economy
    await chat_earn(message_pack)


@event_postprocessor
async def all_event_handler(event: Event):
    if event.type == "GroupRecallEvent":
        # 撤回事件
        recalled_message = MESSAGE_HISTORY.search(group_id=event.group.id, msg_id=event.message_id) # type: ignore
        if recalled_message:
            RECALL_HISTORY.add(recalled_message.group.id, recalled_message)
            # await bot_send_message(recalled_message, f"【{recalled_message.member.name}】撤回了一条消息：\n{recalled_message.message.asDisplay()}")
            pass
    elif event.type == "NudgeEvent":
        # 戳一戳事件
        pass
    elif event.type == "MemberJoinEvent":
        # 成员加入事件
        pass
    elif event.type == "MemberLeaveEventQuit":
        # 成员离开事件
        pass
    elif event.type == "MemberCardChangeEvent":
        # 成员群名片变动事件
        pass


@nonebot.get_driver().on_shutdown
async def on_shutdown():
    MESSAGE_HISTORY.save(config.get("HISTORY_SAVE_PATH", "data/history.pkl"))


@nonebot.get_driver().on_startup
async def on_startup():
    try:
        MESSAGE_HISTORY.load(config.get("HISTORY_SAVE_PATH", "data/history.pkl"))
    except Exception as e:
        nonebot.logger.warning(f"Something went wrong in loading history, reset history file: {repr(e)}") # type: ignore
        MESSAGE_HISTORY.save(config.get("HISTORY_SAVE_PATH", "data/history.pkl"))


@nonebot.get_driver().on_bot_connect
async def on_bot_connect(bot):
    # send message when done module init
    now_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for admin in config.get('ADMIN_LIST', []):
        await bot_send_message(int(admin), f"[{now_time}] Toogle已启动", friend=True)
