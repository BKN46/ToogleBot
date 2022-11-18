import json
import math
import os
import random
import re

from toogle.exceptions import ErrException
from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack
from toogle.utils import create_path

try:
    from toogle.plugins.dnd.search_5e import search_magic
    from toogle.plugins.dnd.search_chm import search_chm
except Exception as e:
    raise ErrException('导入DND组件出现问题，请确data/dnd5e_data存在')

create_path('data/dice_table')

DND_IMAGES_PATH = "toogle/data/dnd/chm_jpg/"  # 图片集地址


class Search5EMagic(MessageHandler):
    name = "DND5E 魔法查询"
    trigger = r"^5em"
    white_list = False
    readme = "DND5E 魔法查询"

    async def ret(self, message: MessagePack) -> MessageChain:
        msg = message.message.asDisplay()[3:].strip()
        return MessageChain.create([Plain(search_magic(msg))])


class CustomDiceTable(MessageHandler):
    name = "创建自定义骰表"
    trigger = r"^(创建骰表|骰表)"
    white_list = False
    readme = "骰表"

    table_reg = r"^(\d+)(-([1-9]\d*)|)\s(.+)"

    async def ret(self, message: MessagePack) -> MessageChain:
        message_content = message.message.asDisplay().split("\n")
        cmd, content = message_content[0], "\n".join(message_content[1:])
        table_path = "data/dice_table/" + cmd.split()[1] + ".txt"
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
