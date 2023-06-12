from nonebot import require

from toogle.index import schedule_plugins
from toogle.scheduler import reload_manual_schedular

for plugin in schedule_plugins:
    plugin.regist()

reload_manual_schedular()
