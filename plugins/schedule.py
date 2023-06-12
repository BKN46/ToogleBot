from nonebot import require

require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler

from toogle.index import schedule_plugins
from toogle.scheduler import reload_manual_schedular

for plugin in schedule_plugins:
    plugin.regist(scheduler)

reload_manual_schedular()
