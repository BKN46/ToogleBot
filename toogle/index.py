import importlib
import inspect
import os
import time

import nonebot

from toogle.configs import config
from toogle.message_handler import MessageHandler
from toogle.nonebot2_adapter import LinearHandler, PluginWrapper
from toogle.scheduler import ScheduleModule, schedular_start

plugin_list = os.listdir("toogle/plugins/")
export_plugins = []
start_time = time.time()
for index, plugin_name in enumerate(plugin_list):
    if not plugin_name.endswith(".py"):
        continue
    nonebot.logger.info(f"[{plugin_name}] ==>")  # type: ignore
    plugin_name = plugin_name.replace(".py", "")
    try:
        plugin_module = importlib.import_module(f"toogle.plugins.{plugin_name}")
    except Exception as e:
        nonebot.logger.error(f"[{plugin_name}] failed to import: {repr(e)}")  # type: ignore
        continue
    for x in dir(plugin_module):
        tmp = getattr(plugin_module, x)
        if inspect.isclass(tmp) and all([
            tmp.__name__ != 'MessageHandler',
            tmp.__name__ not in config.get('DISABLED_MODULE', []),
            issubclass(tmp, MessageHandler),
        ]):
            export_plugins.append(PluginWrapper(tmp))  # type: ignore
            import_time = (time.time() - start_time) * 1000
            nonebot.logger.success(f"[{tmp.__name__}] imported ({index + 1}/{len(plugin_list)}) ({import_time:.2f}ms)")  # type: ignore
            start_time = time.time()
        if inspect.isclass(tmp) and all([
            tmp.__name__ != 'ScheduleModule',
            tmp.__name__ not in config.get('DISABLED_MODULE', []),
            issubclass(tmp, ScheduleModule),
        ]):
            tmp().regist()
            import_time = (time.time() - start_time) * 1000
            nonebot.logger.success(f"[Schedule][{tmp.__name__}] imported ({index + 1}/{len(plugin_list)}) ({import_time:.2f}ms)")  # type: ignore
            start_time = time.time()
            pass
    start_time = time.time()

schedular_start()
linear_handler = LinearHandler(export_plugins)
