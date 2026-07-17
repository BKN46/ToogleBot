import datetime

from toogle.logger import logger
from toogle.message_handler import MESSAGE_HISTORY, MessagePack
from toogle.index import active_plugins
from configs import config
from toogle.adapter import bot_send_message
from toogle.msg_proc import chat_earn


async def message_post_process(message_pack: MessagePack):
    history_key = (
        message_pack.group.id
        if message_pack.message_type == "group"
        else f"private_{message_pack.member.id}"
    )
    try:
        MESSAGE_HISTORY.add(history_key, message_pack) # type: ignore
    except Exception:
        logger.exception("Failed to record message history")

    for plugin in active_plugins:
        try:
            if (
                message_pack.message_type == "group"
                and str(message_pack.group.id) in config.get('CHAT_GROUP_LIST', [])
                and plugin.is_trigger_random(message=message_pack)
            ):
                message_ret = await plugin.ret_wrapper(message_pack)
                if message_ret:
                    bot_send_message(message_pack, message_ret)
        except Exception:
            logger.exception("Active plugin failed: %s", plugin.name)

    try:
        await chat_earn(message_pack)
    except Exception:
        logger.exception("Message economy/audit post-process failed")


async def on_shutdown():
    MESSAGE_HISTORY.save(config.get("HISTORY_SAVE_PATH", "data/history.pkl"))


async def on_startup():
    try:
        MESSAGE_HISTORY.load(config.get("HISTORY_SAVE_PATH", "data/history.pkl"))
    except Exception as e:
        logger.warning(f"Something went wrong in loading history, reset history file: {repr(e)}") # type: ignore
        MESSAGE_HISTORY.save(config.get("HISTORY_SAVE_PATH", "data/history.pkl"))


async def on_bot_connect(bot):
    # send message when done module init
    now_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for admin in config.get('ADMIN_LIST', []):
        bot_send_message(int(admin), f"[{now_time}] Toogle已启动", friend=True)
