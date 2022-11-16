import re

from toogle.message import Image as GImage
from toogle.message import Member, MessageChain, Plain, Quote
from toogle.message_handler import MessageHandler, MessagePack
from toogle.plugins.thunderskill.get_wt_data import get_line_cost
from toogle.plugins.thunderskill.main import get_player_recent_data


class WTVehicleLine(MessageHandler):
    name = "战雷开线资源查询"
    trigger = r"^研发(.*)到(.*)"
    white_list = False
    thread_limit = True
    readme = "战雷开线需求快查"

    async def ret(self, message: MessagePack) -> MessageChain:
        re_match = re.match(self.trigger, message.message.asDisplay())
        res = get_line_cost(re_match.group(1), re_match.group(2))  # type: ignore
        return MessageChain.create([Plain(res)])


class ThunderSkill(MessageHandler):
    name = "快速Thunder Skill查询"
    trigger = r"^TS\s"
    white_list = False
    readme = "快查Thunder Skill近期战绩"

    async def ret(self, message: MessagePack) -> MessageChain:
        search_id = message.message.asDisplay().split()[1]
        try:
            return MessageChain.create([Plain(get_player_recent_data(search_id))])
        except AttributeError as e:
            return MessageChain.create([Plain(f"{search_id}：ID错误或无数据，或者TS挂了")])
        except Exception as e:
            return MessageChain.create([Plain(f"{search_id}：未知错误，可能TS挂了\n{repr(e)}")])
