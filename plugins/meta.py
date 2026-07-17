import math
import re

from configs import config
from toogle.message import ForwardMessage
from toogle.message import MessageChain
from toogle.message_handler import ActiveHandler, MessageHandler, MessagePack
from toogle.logger import logger
from toogle.utils import is_admin


def _configured_self_id() -> str:
    value = config.get("BOT_QQ") or config.get("QQ_ACCOUNT") or ""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value).strip()


def _help_regex() -> str:
    prefixes = [r"#help#", r"\.help", "/help"]
    self_id = _configured_self_id()
    if self_id:
        prefixes.append(f"@{re.escape(self_id)}")
    return rf"^(?:{'|'.join(prefixes)})(?P<query>.*)$"


HELP_REGEX = _help_regex()


class ActivePathProbe(ActiveHandler):
    name = "主动消息链路探针"
    readme = "仅在显式验证配置下启用"

    def is_trigger_random(self, message: MessagePack | None = None) -> bool:
        enabled = str(config.get("NAPCAT_ACTIVE_PROBE_ENABLED", "")).lower()
        if enabled not in {"1", "true", "yes"} or message is None:
            return False

        sender = str(config.get("NAPCAT_SENDER_ACCOUNT", "")).strip()
        group = str(config.get("NAPCAT_TEST_GROUP", "")).strip()
        trigger = str(config.get("NAPCAT_ACTIVE_PROBE_TRIGGER", "")).strip()
        reply = str(config.get("NAPCAT_ACTIVE_PROBE_REPLY", "")).strip()
        if not all((sender, group, trigger, reply)):
            return False
        if str(message.member.id) != sender or str(message.group.id) != group:
            return False
        if message.message.asDisplay().strip() != trigger:
            return False

        logger.info("Triggered [%s]", self.name)
        return True

    async def ret(self, message: MessagePack) -> MessageChain | None:
        reply = str(config.get("NAPCAT_ACTIVE_PROBE_REPLY", "")).strip()
        return MessageChain.plain(reply) if reply else None


class GetResponse(MessageHandler):
    name = "ping"
    trigger = "^33333$"

    async def ret(self, message: MessagePack) -> MessageChain:
        return MessageChain.plain("33333")


class GetHelp(MessageHandler):
    name = "帮助列表"
    trigger = HELP_REGEX
    readme = "获取大黄狗全功能列表"

    async def ret(self, message: MessagePack) -> MessageChain:
        from toogle.index import get_export_plugins

        pre_filter_plugins = [
            x for x in get_export_plugins()
            if not x.plugin.admin_only
            or (is_admin(message.member.id) and x.plugin.admin_only)
        ]
        
        def get_plugin_desc(plugin, simplify=False):
            if simplify:
                return f"{plugin.name}\n【触发正则】 {plugin.trigger}"
            return f"{plugin.name}\n【触发正则】 {plugin.trigger}\n【说明】 {plugin.readme}\n【触发花费】 {plugin.price}gb\n【触发间隔】 {plugin.interval}秒"
        
        def get_help_page(page):
            if not pre_filter_plugins:
                return MessageChain.plain("当前没有可用插件")
            if page >= total_page:
                page = total_page - 1
            elif page < 0:
                page = 0
            p1, p2 = page * page_size, min((page + 1) * page_size, len(pre_filter_plugins))
            return ForwardMessage.get_quick_forward_message([
                MessageChain.plain(get_plugin_desc(mod.plugin))
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
            return MessageChain.plain(
                f"\n{'#'*15}\n".join(res) if res else "未找到匹配插件"
            )

        page_size=30
        total_page = max(1, math.ceil(len(pre_filter_plugins)/page_size))

        matched = re.search(self.trigger, message.message.asDisplay())
        if not matched:
            return MessageChain.plain("帮助命令格式错误")
        search_content = matched.group("query").strip()
        if search_content == "--markdown":
            res = MessageChain.plain('\n'.join([
                f"{mod.plugin_class.__module__}.{mod.plugin_class.__name__}: {mod.plugin.name}"
                for mod in pre_filter_plugins
            ]))
        elif not search_content:
            res = get_help_page(0)
            res.root[0].add(MessageChain.plain(f'当前为第{1}页, 共{total_page}页')) # type: ignore
        elif str.isdigit(search_content):
            res = get_help_page(int(search_content) - 1)
            res.root[0].add(MessageChain.plain(f'当前为第{search_content}页, 共{total_page}页')) # type: ignore
        else:
            res = fuzz_search(search_content)
        return res
