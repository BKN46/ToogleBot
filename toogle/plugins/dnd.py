import json
import random
import os
import math
import re


from message_handler import MessageHandler, MessagePack
from toogle.message_handler import MessagePack, MessageHandler
from toogle.message import MessageChain, Plain, Image

DND_IMAGES_PATH = "/root/repos/qqbot_graia/large_utils/femagic/chm_jpg/"  # 图片集地址


class Search5EMagic(MessageHandler):
    trigger = r"^5em"
    white_list = False
    readme = "DND5E 魔法查询"

    async def ret(self, message: MessagePack) -> MessageChain:
        msg = message.message.asDisplay()[3:].strip()
        return MessageChain.create([Plain(search_magic(msg))])


class CustomDiceTable(MessageHandler):
    trigger = r"^(创建骰表|骰表)"
    white_list = False
    readme = "骰表"

    table_reg = r"^(\d+)(-([1-9]\d*)|)\s(.+)"

    async def ret(self, message: MessagePack) -> MessageChain:
        message_content = message.message.asDisplay().split("\n")
        cmd, content = message_content[0], "\n".join(message_content[1:])
        table_path = settings.BASE_PATH + "tmp/dice_table/" + cmd.split()[1] + ".txt"
        table_exist = os.path.isfile(table_path)
        if cmd.startswith("骰表"):
            if not table_exist:
                return MessageChain.create([Plain(f"骰表{cmd.split()[1]}不存在")])
            text = open(table_path, "r").read()
            effects = []
            for line in text.split("\n"):
                content = re.search(self.table_reg, line)
                if content:
                    effects.append(
                        [
                            int(content.group(1)),
                            int(content.group(3) or content.group(1)),
                            content.group(4),
                        ]
                    )
            dice_low, dice_high = min([i[0] for i in effects]), max(
                [i[1] for i in effects]
            )
            roll_res = random.randint(dice_low, dice_high)
            hits = [i for i in effects if roll_res >= i[0] and roll_res <= i[1]]
            hits_str = "\n".join([f"{i[0]}-{i[1]} {i[2]}" for i in hits])
            return MessageChain.create([Plain(f"掷骰: {roll_res} 结果为:\n{hits_str}")])
        elif cmd.startswith("创建骰表"):
            if table_exist:
                return MessageChain.create([Plain(f"骰表{cmd.split()[1]}已存在")])
            for line in content.split("\n"):
                if not re.search(self.table_reg, line):
                    return MessageChain.create(
                        [Plain(f"骰表语法不合法:\n{line}\n确保每行都符合正则 {self.table_reg}")]
                    )
            with open(table_path, "w") as f:
                f.write(content)
            return MessageChain.create([Plain("创建骰表成功")])
        return MessageChain.create([Plain("?")])


class FastPythagorean(MessageHandler):
    trigger = r"^勾股 (([1-9]\d*\.?\d*)|(0\.\d*[1-9]))"
    white_list = False
    readme = "直角边快速勾股，方便跑团立体空间计算"

    async def ret(self, message: MessagePack) -> MessageChain:
        n = message.message.asDisplay()[2:].strip().split()
        res = math.sqrt(float(n[0]) ** 2 + float(n[1]) ** 2)
        return MessageChain.create([Plain(f"长{n[0]} 高{n[1]} 斜边为{res:.3f}")])


class FastFallCal(MessageHandler):
    unit_conversion = {
        "尺": 0.3048,
        "ft": 0.3048,
        "米": 1,
        "m": 1,
    }
    unit_reg_str = "|".join(k for k in unit_conversion.keys())
    trigger = f"^(([1-9]\d*\.?\d*)|(0\.\d*[1-9]))({unit_reg_str})掉落$"
    white_list = False
    readme = "英尺掉落回合数计算，方便跑团"

    async def ret(self, message: MessagePack) -> MessageChain:
        message_content = message.message.asDisplay()
        matchs = re.search(self.trigger, message_content)
        if not matchs:
            raise Exception(f"No matchs: {message_content}")
        height, unit = float(matchs.group(1)), matchs.group(4)
        x = height * self.unit_conversion[unit]
        k = 1 / 2 * 0.865 * 1.293 * 0.4
        m = 80
        drop_time = math.acosh(math.e ** (k * x / m)) ** 2 / math.sqrt(9.8 * k / m)
        res_str = (
            f"掉落高度{height}{unit} ({x:.2f}m)\n"
            f"耗时{drop_time:.2f}sec ({math.ceil(drop_time/6)}回合)"
        )
        return MessageChain.create([Plain(res_str)])


class UnitConversion(MessageHandler):
    trans_mapping = {
        "英磅": ["公斤", 0.45359237],
        "磅": ["公斤", 0.45359237],
        "lb": ["公斤", 0.45359237],
        "英尺": ["米", 0.3048],
        "ft": ["米", 0.3048],
        "英寸": ["厘米", 2.54],
        "加仑": ["升", 3.78541178],
        "海里": ["公里", 1.852],
        "knot": ["公里每小时", 1.852],
        "nmi": ["公里", 1.852],
        "英里": ["公里", 1.609344],
        "mile": ["公里", 1.609344],
        "yard": ["米", 0.9144],
        "品脱": ["毫升", 568],
        "盎司": ["克", 28.349523125],
        "光年": ["千米", 9.4605284e15],
        "天文单位": ["千米", 149597871],
        "地月距离": ["千米", 384403.9],
    }
    trans_reg_str = "|".join([k for k in trans_mapping.keys()])
    trigger = f"(([1-9]\d*\.?\d*)|(0\.\d*[1-9]))({trans_reg_str})"
    white_list = False
    readme = "快速英/美制单位转换，方便跑团"

    async def ret(self, message: MessagePack) -> MessageChain:
        message_content = message.message.asDisplay()
        matchs = re.search(self.trigger, message_content)
        if not matchs:
            raise Exception(f"No matchs: {message_content}")
        num, unit = matchs.group(1), matchs.group(4)
        cal_res = f"{self.trans_mapping[unit][1] * float(num):.3f}{self.trans_mapping[unit][0]}"
        return MessageChain.create([Plain(f"{matchs.group(0)} 折合 {cal_res}")])


class Search5ECHM(MessageHandler):
    trigger = r"^dnd5e"
    white_list = False
    readme = "DND5E 天麟不全书查询"

    async def ret(self, message: MessagePack) -> MessageChain:
        msg = message.message.asDisplay()[5:].strip()
        res = search_chm(msg)
        if res.endswith("jpg"):
            res = Image.fromLocalFile(DND_IMAGES_PATH + res)
        else:
            res = Plain(res)
        return MessageChain.create([res])

'''
class Hangman5EMagic(MessageHandler):
    trigger = r"^5ehangman"
    white_list = False
    readme = "DND5E 魔法hangman字谜"

    async def ret(self, message: MessagePack) -> MessageChain:
        magic = random_magic()
        guess_list = []
        await message.base.app.sendGroupMessage(
            message.group,
            MessageChain.create([Plain(self.draw_text(magic[0], guess_list))]),
        )

        @Waiter.create_using_function([GroupMessage])
        def waiter(
            event: GroupMessage,
            waiter_group: Group,
            waiter_member: Member,
            waiter_message: MessageChain,
        ):
            guess_text = waiter_message.asDisplay()
            if all(
                [
                    len(guess_text) == 1,
                    guess_text.isalpha(),
                    waiter_group.id == message.group.id,
                ]
            ):
                guess_list.append(guess_text.lower())
                return True
            return False

        while self.is_end(magic[0], guess_list) == 0:
            if await message.base.inc.wait(waiter):
                send = f"{self.draw_text(magic[0], guess_list)}\n{guess_list}\n{self.hangman_pic(self.error_num(magic[0],guess_list))}"
                await message.base.app.sendGroupMessage(
                    message.group, MessageChain.create([Plain(send)])
                )

        if self.is_end(magic[0], guess_list) == 1:
            return MessageChain.create(
                [Plain(f"Success! Answer is {magic[0]} ({magic[1]})")]
            )
        else:
            return MessageChain.create(
                [Plain(f"Failed! Answer is {magic[0]} ({magic[1]})")]
            )

    def draw_text(self, text, guess_word):
        res = ""
        for ch in text:
            if ch.lower() in guess_word:
                res += ch + " "
            elif ch == " ":
                res += ch + " "
            else:
                res += "_" + " "
        return res

    def error_num(self, text, guess_word):
        error_list = [ch for ch in guess_word if ch not in text]
        return len(error_list)

    def is_end(self, text, guess_word):
        if self.error_num(text, guess_word) >= 6:
            return -1
        for ch in text:
            if ch.lower() not in guess_word:
                break
        else:
            return 1
        return 0

    def hangman_pic(self, num):
        pic = [
            " ----\n |\n |\n |\n/ \\",
            " ----\n |  6\n |\n |\n/ \\",
            " ----\n |  6\n |  |\n |\n/ \\",
            " ----\n |  6\n | /|\n |\n/ \\",
            " ----\n |  6\n | /|\\\n |\n/ \\",
            " ----\n |  6\n | /|\\\n | /\n/ \\",
            " ----\n |  6\n | /|\\\n | / \\\n/ \\",
        ]
        return pic[num]
'''
