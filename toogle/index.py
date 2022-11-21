import importlib
import inspect
import os

import nonebot

from toogle.message_handler import MessageHandler
from toogle.nonebot2_adapter import LinearHandler, PluginWrapper

plugin_list = os.listdir("toogle/plugins/")
export_plugins = []
for index, plugin_name in enumerate(plugin_list):
    if not plugin_name.endswith(".py"):
        continue
    plugin_name = plugin_name.replace(".py", "")
    try:
        plugin_module = importlib.import_module(f"toogle.plugins.{plugin_name}")
    except Exception as e:
        nonebot.logger.error(f"[{plugin_name}] failed to import: {repr(e)}")  # type: ignore
        continue
    for x in dir(plugin_module):
        tmp = getattr(plugin_module, x)
        if inspect.isclass(tmp) and issubclass(tmp, MessageHandler):
            export_plugins.append(PluginWrapper(tmp))  # type: ignore
            nonebot.logger.success(f"[{tmp.__name__}] imported ({index + 1}/{len(plugin_list)})")  # type: ignore


linear_handler = LinearHandler(export_plugins)
