
import datetime
from typing import List
import nonebot
from nonebot.matcher import Matcher
from nonebot.rule import to_me
from nonebot.plugin import on_message, on_regex

from toogle.configs import config
from toogle.index import export_plugins

MATCHERS: List[Matcher] = []

def load_plugins():
    for m in MATCHERS:
        m.expire_time = datetime.datetime.now()
    MATCHERS.clear()

    for plugin in export_plugins:
        try:
            matcher = on_regex(plugin.plugin.trigger)
            matcher.append_handler(plugin.ret)
            MATCHERS.append(matcher) # type: ignore
            if plugin.plugin.to_me_trigger:
                to_me_matcher = on_message(rule=to_me())
                to_me_matcher.append_handler(plugin.ret)
                MATCHERS.append(to_me_matcher) # type: ignore
                nonebot.logger.success(f"[{plugin.plugin.name}] Also loaded as to_me trigger")  # type: ignore
        except Exception as e:
            nonebot.logger.error(f"[{plugin.plugin.name}] failed to add matcher/handler: {repr(e)}") # type: ignore
