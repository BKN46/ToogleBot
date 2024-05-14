import math
import re

import numpy as np
from matplotlib import pyplot as plt

from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack
from toogle.utils import handle_TLE, set_timeout
from toogle.plugins.compose.wolfram_alpha import get_wolfram_alpha_query

pic_path = "data/math_plt.jpg"


class Mathematica(MessageHandler):
    name = "数学绘图"
    trigger = r"^#math#"
    # white_list = True
    readme = "数学用"

    async def ret(self, message: MessagePack) -> MessageChain:
        if message.message.asDisplay() == "#math#close":
            plt.close()
            return MessageChain.create([Plain("Done")])
        elif "y" in message.message.asDisplay():
            func_str = message.message.asDisplay()[7:].strip().split("\n")
            return MessageChain.create([self.draw_function3d(func_str)])
        else:
            func_str = message.message.asDisplay()[7:].strip().split("\n")
            return MessageChain.create([self.draw_function(func_str)])

    def func_preproc(self, func_str):
        opts = {
            "^": "**",
            "√": "sqrt",
            "²": "**2",
            "³": "**3",
        }
        for k, v in opts.items():
            func_str = func_str.replace(k, v)
        return func_str

    def draw_function(self, func_strs):
        llim, rlim, ACC = -2, 2, 0.01
        x_list = [x * ACC for x in range(int(llim / ACC), int(rlim / ACC))]
        tmp_ylim_bot, tmp_ylim_top = [], []
        for func_str in func_strs:
            func_str = self.func_preproc(func_str)
            y, err_index = [], []
            for x in x_list:
                try:
                    tmp_y = eval(func_str, {**vars(math).copy(), "x": x})
                    y.append(tmp_y)
                except Exception as e:
                    err_index.append(x)
            plt.plot([x for x in x_list if x not in err_index], y, label=func_str)
            tmp_ylim_bot.append(min(y))
            tmp_ylim_top.append(max(y))
        ylim = (max(tmp_ylim_bot), min(tmp_ylim_top))
        plt.ylim(ylim)

        # plt.vlines(0, ylim[0], ylim[1])
        plt.grid(linestyle=":", color="b")

        plt.legend()
        plt.savefig(pic_path)
        plt.close()
        return Image.fromLocalFile(pic_path)

    def draw_function3d(self, func_strs):
        llim, rlim, ACC = -2, 2, 0.02
        y_list, x_list = [x * ACC for x in range(int(llim / ACC), int(rlim / ACC))], [
            x * ACC for x in range(int(llim / ACC), int(rlim / ACC))
        ]

        ax = plt.axes(projection="3d")
        tmp_zlim_bot, tmp_zlim_top = [], []

        for func_str in func_strs:
            func_str = self.func_preproc(func_str)
            z, err_index = [], []
            for x in x_list:
                z_y = []
                for y in y_list:
                    try:
                        tmp_z = eval(
                            func_str,
                            {
                                **vars(math).copy(),
                                "x": x,
                                "y": y,
                            },
                        )
                        z_y.append(tmp_z)
                    except Exception as e:
                        err_index.append(x)
                z.append(z_y)
            z = np.array(z)
            x_list, y_list = [x for x in x_list if x not in err_index], [
                y for y in y_list if y not in err_index
            ]
            x_list, y_list = np.meshgrid(x_list, y_list)
            ax.plot_surface(  # type: ignore
                x_list,
                y_list,
                z,
                rstride=1,
                cstride=1,
                cmap="viridis",
                edgecolor="none",
            )
            tmp_zlim_bot.append(np.min(z))
            tmp_zlim_top.append(np.max(z))
        plt.savefig(pic_path)
        plt.close()
        return Image.fromLocalFile(pic_path)


class Calculator(MessageHandler):
    name = "计算器"
    trigger = r"=$"
    readme = "计算器"
    price = 2

    async def ret(self, message: MessagePack) -> MessageChain:
        text = message.message.asDisplay()
        running_res: str = Calculator.get_exec(Calculator.func_preproc(text[:-1]))
        return MessageChain.create([message.as_quote(), Plain(running_res)])

    @staticmethod
    def func_preproc(func_str):
        opts = {
            "（": "(",
            "）": ")",
            "x": "*",
            "^": "**",
            "√": "sqrt",
            "²": "**2",
            "³": "**3",
            "k": "000",
            "w": "0000",
            "K": "000",
            "W": "0000",
            "千": "000",
            "万": "0000",
            "亿": "00000000",
            "\n": "",
        }
        for k, v in opts.items():
            func_str = func_str.replace(k, v)
        return func_str

    @staticmethod
    @set_timeout(2, handle_TLE)
    def get_exec(text) -> str:
        try:
            if any(
                [
                    x in text
                    for x in [
                        "os",
                        "attr",
                        "sys",
                        "__",
                        "dir",
                        "exit",
                        "ls",
                        "rm",
                        "exec",
                        "eval",
                        "proc",
                        "open",
                        "file",
                        "write",
                        "PIPE",
                        "std",
                        "time",
                    ]
                ]
            ):
                raise Exception("含有危险词!")
            running_res = eval(text)
            if len(str(running_res)) > 200:
                raise Exception("输出字数过多!")
        except Exception as e:
            running_res = ""
            # running_res = repr(e)
        return running_res


class WolframAlpha(MessageHandler):
    name = "Wolfram Alpha"
    trigger = r"\.wolfram"
    thread_limit = True
    readme = "Wolfram Alpha计算数学调用"

    async def ret(self, message: MessagePack) -> MessageChain:
        query = message.message.asDisplay()[8:].strip()
        image_byte = await get_wolfram_alpha_query(query)
        return MessageChain.create([Image(bytes=image_byte)])


class FastPythagorean(MessageHandler):
    name = "快速勾股计算"
    trigger = r"^勾股 (([1-9]\d*\.?\d*)|(0\.\d*[1-9]))"
    white_list = False
    readme = "直角边快速勾股，方便跑团立体空间计算"

    async def ret(self, message: MessagePack) -> MessageChain:
        n = message.message.asDisplay()[2:].strip().split()
        res = math.sqrt(float(n[0]) ** 2 + float(n[1]) ** 2)
        return MessageChain.create([message.as_quote(), Plain(f"长{n[0]} 高{n[1]} 斜边为{res:.3f}")])


class FastFallCal(MessageHandler):
    name = "快速坠落时间计算"
    unit_conversion = {
        "尺": 0.3048,
        "ft": 0.3048,
        "米": 1,
        "m": 1,
    }
    unit_reg_str = "|".join(k for k in unit_conversion.keys())
    trigger = f"^(([1-9]\d*\.?\d*)|(0\.\d*[1-9]))({unit_reg_str})掉落$" # type: ignore
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
    name = "单位转换"
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
    trigger = f"(([1-9]\d*\.?\d*)|(0\.\d*[1-9]))({trans_reg_str})" # type: ignore
    white_list = False
    readme = "快速英/美制单位转换，方便跑团"
    price = 2

    async def ret(self, message: MessagePack) -> MessageChain:
        message_content = message.message.asDisplay()
        matchs = re.search(self.trigger, message_content)
        if not matchs:
            raise Exception(f"误触发: {message_content}")
        num, unit = matchs.group(1), matchs.group(4)
        cal_res = f"{self.trans_mapping[unit][1] * float(num):.3f}{self.trans_mapping[unit][0]}"
        return MessageChain.create([Plain(f"{matchs.group(0)} 折合 {cal_res}")])
