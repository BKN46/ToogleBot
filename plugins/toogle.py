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
from toogle.message import ForwardMessage
from toogle.message import MessageChain as ToogleChain
from toogle.message_handler import MESSAGE_HISTORY, RECALL_HISTORY
from toogle.nonebot2_adapter import PluginWrapper, bot_send_message
from toogle.msg_proc import chat_earn
from plugins.load import load_plugins
from toogle.utils import is_admin

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
    pre_filter_plugins = [x for x in export_plugins if not x.plugin.admin_only or (is_admin(event.sender.id) and x.plugin.admin_only)]
    
    def get_plugin_desc(plugin, simplify=False):
        if simplify:
            return f"{plugin.name}\n【触发正则】 {plugin.trigger}"
        return f"{plugin.name}\n【触发正则】 {plugin.trigger}\n【说明】 {plugin.readme}\n【触发花费】 {plugin.price}gb\n【触发间隔】 {plugin.interval}秒"
    
    def get_help_page(page):
        res = []
        if page >= total_page:
            page = total_page - 1
        elif page < 0:
            page = 0
        p1, p2 = page * page_size, min((page + 1) * page_size, len(pre_filter_plugins))
        for mod in pre_filter_plugins[p1:p2]:
            res.append(
                f"{mod.plugin.name}\n【触发正则】 {mod.plugin.trigger}\n【说明】 {mod.plugin.readme}"
            )
        return ForwardMessage.get_quick_forward_message([
            ToogleChain.plain(get_plugin_desc(mod.plugin))
            for mod in pre_filter_plugins[p1:p2]
            ], people_name="大黄狗")

    def fuzz_search(content):
        res = []
        for mod in pre_filter_plugins:
            if content in mod.plugin.name or content in mod.plugin.trigger or content in mod.plugin.readme:
                line = get_plugin_desc(mod.plugin)
                if mod.plugin.price > 0:
                    line += f"\n【触发花费】 {mod.plugin.price}gb"
                if mod.plugin.interval > 0:
                    line += f"\n【触发间隔】 {mod.plugin.interval}秒"
                res.append(line)
        return f"\n{'#'*15}\n".join(res)

    message_pack = PluginWrapper.get_message_pack(event, message)

    page_size=30
    total_page = math.ceil(len(pre_filter_plugins)/page_size)

    search_content = re.search(get_help_regex, message_pack.message.asDisplay()).groups()[1].strip() # type: ignore
    if search_content == "--markdown":
        res = '\n'.join([f"{mod.__class__.__name__}: {mod.plugin.name}" for mod in pre_filter_plugins])
    elif not search_content:
        res = get_help_page(0)
        res.root[0].add(ToogleChain.plain(f'当前为第{1}页, 共{total_page}页')) # type: ignore
    elif str.isdigit(search_content):
        res = get_help_page(int(search_content) - 1)
        res.root[0].add(ToogleChain.plain(f'当前为第{search_content}页, 共{total_page}页')) # type: ignore
    else:
        res = fuzz_search(search_content)
    bot_send_message(message_pack, res)

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
                bot_send_message(message_pack, message_ret)

    # economy
    await chat_earn(message_pack)


@event_postprocessor
async def all_event_handler(event: Event):
    if event.type == "GroupRecallEvent":
        # 撤回事件
        recalled_message = MESSAGE_HISTORY.search(group_id=event.group.id, msg_id=event.message_id) # type: ignore
        if recalled_message:
            RECALL_HISTORY.add(recalled_message.group.id, recalled_message)
            # bot_send_message(recalled_message, f"【{recalled_message.member.name}】撤回了一条消息：\n{recalled_message.message.asDisplay()}")
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
    elif event.type == "FriendRequestEvent":
        # 加好友请求事件
        pass
    elif event.type == "BotInvitedJoinGroupRequestEvent":
        # 邀请加入群聊事件
        for admin in config.get('ADMIN_LIST', []):
            bot_send_message(int(admin), f".accept_invite {event.eventId} {event.invitorId} {event.groupId}", friend=True) # type: ignore
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
        bot_send_message(int(admin), f"[{now_time}] Toogle已启动", friend=True)
