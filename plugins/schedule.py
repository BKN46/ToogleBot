from nonebot import require

require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler

from toogle.index import schedule_plugins

for plugin in schedule_plugins:
    plugin.regist(scheduler)
