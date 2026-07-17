from toogle.index import schedule_plugins
from toogle.scheduler import reload_manual_scheduler


def register_schedules():
    for plugin in schedule_plugins:
        plugin.register()
    reload_manual_scheduler()
