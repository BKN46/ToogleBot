import importlib
import inspect
import os
import time
from typing import List

import nonebot

from toogle.configs import config
from toogle.message_handler import MessageHandler, ActiveHandler
from toogle.nonebot2_adapter import PluginWrapper
from toogle.scheduler import ScheduleModule, copied_plugin_list

plugin_list = os.listdir("toogle/plugins/")
export_plugins: List[PluginWrapper] = []
active_plugins: List[ActiveHandler] = []
schedule_plugins: List[ScheduleModule] = []


def reload_plugins():
    export_plugins.clear()
    active_plugins.clear()
    schedule_plugins.clear()
    copied_plugin_list.clear()

    total_start_time = time.time()
    start_time = time.time()
    
    for index, plugin_name in enumerate(plugin_list):
        if not plugin_name.endswith(".py"):
            continue
        nonebot.logger.info(f"[{plugin_name}] ==>")  # type: ignore
        plugin_name = plugin_name.replace(".py", "")
        try:
            plugin_module = importlib.import_module(f"toogle.plugins.{plugin_name}")
            importlib.reload(plugin_module)
        except Exception as e:
            nonebot.logger.error(f"[{plugin_name}] failed to import: {repr(e)}")  # type: ignore
            continue

        for x in dir(plugin_module):
            tmp = getattr(plugin_module, x)
            import_type = "None"
            if inspect.isclass(tmp) and [
                x for x in export_plugins if x.plugin_class.__name__ == tmp.__name__  # type: ignore
            ]:
                continue
            # Normal plugin
            if inspect.isclass(tmp) and all([
                tmp.__name__ != 'MessageHandler',
                tmp.__name__ not in config.get('DISABLED_MODULE', []),
                issubclass(tmp, MessageHandler),
            ]):
                export_plugins.append(PluginWrapper(tmp))  # type: ignore
                copied_plugin_list.append(PluginWrapper(tmp))  # type: ignore
                import_type = "Normal"

            # Active plugin
            elif inspect.isclass(tmp) and all([
                tmp.__name__ != 'ActiveHandler',
                tmp.__name__ not in config.get('DISABLED_MODULE', []),
                issubclass(tmp, ActiveHandler),
            ]):
                active_module = tmp()
                active_plugins.append(active_module)  # type: ignore
                import_type = "Active"

            # Scheduled job
            elif inspect.isclass(tmp) and all([
                tmp.__name__ != 'ScheduleModule',
                tmp.__name__ not in config.get('DISABLED_MODULE', []),
                issubclass(tmp, ScheduleModule),
            ]):
                schedule_module = tmp()
                schedule_plugins.append(schedule_module)
                if schedule_module.trigger:
                    export_plugins.append(PluginWrapper(tmp))  # type: ignore
                    copied_plugin_list.append(PluginWrapper(tmp))  # type: ignore
                import_type = "Scheduled"

            import_time = (time.time() - start_time) * 1000
            if import_type != "None":
                nonebot.logger.success(f"[{import_type}][{tmp.__name__}] imported ({index + 1}/{len(plugin_list)}) ({import_time:.2f}ms)")  # type: ignore
            start_time = time.time()

        start_time = time.time()

    total_use_time = (time.time() - total_start_time) * 1000

    return total_use_time

reload_plugins()

def reload_designated_export_module(plugin_name, module_name=""):
    plugin_module = importlib.import_module(f"toogle.plugins.{plugin_name}")
    for x in dir(plugin_module):
        tmp = getattr(plugin_module, x)
        if inspect.isclass(tmp) and all([
            tmp.__name__ != 'MessageHandler',
            tmp.__name__ not in config.get('DISABLED_MODULE', []),
            issubclass(tmp, MessageHandler),
            module_name in tmp.__name__,
        ]):
            for p in export_plugins:
                if p.plugin_class.__name__ == tmp.__name__: # type: ignore
                    export_plugins.remove(p)
                    copied_plugin_list.remove(p)
            export_plugins.append(PluginWrapper(tmp))  # type: ignore
            copied_plugin_list.append(PluginWrapper(tmp))  # type: ignore
            nonebot.logger.success(f"[Reload Module][{tmp.__name__}] imported")  # type: ignore
