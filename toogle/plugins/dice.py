import random
import re

from matplotlib import pyplot as plt
from scipy.signal import fftconvolve

from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack

pic_path = "data/dice_tmp.jpg"

class Dice(MessageHandler):
    name = "骰子"
    trigger = r"(^(\.|。|\.r|。r)(`|)(\d|d))|(#.*[d|/].*#)"
    readme = "骰娘，.1d20kh或者.1d20kl来指定优劣势，支持如.1d6+1d20+3这样的简单组合运算。使用`来查看概率分布"

    async def ret(self, message: MessagePack) -> MessageChain:
        self.roll_res = []
        org_str = message.message.asDisplay()
        dice_str = org_str[1:]
        if "#" in message.message.asDisplay():
            return MessageChain.create([self.get_insertion_dice(org_str)])
        elif dice_str.startswith("`"):
            dice_str = dice_str[1:]
            return MessageChain.create([self.show_dice_distribute(dice_str)])
        else:
            if dice_str.startswith("r"):
                dice_str = dice_str[1:]
            if "|" in dice_str:
                dice_str = dice_str.split("|")
                choices = dice_str[1].strip().split(",")
                roll_res = self.roll(dice_str[0].strip())
                return MessageChain.create(
                    [Plain(choices[min(len(choices), roll_res) - 1])]
                )
            else:
                res = f"{self.roll(dice_str)} ({', '.join([str(x) for x in self.roll_res])}) [avg≈{self.cal_roll_avg(dice_str)}]"
                return MessageChain.create([Plain(res)])

    # Roll dice
    def rd(self, maxium: int, do_save=False) -> int:
        res = random.randint(1, maxium)
        if do_save:
            self.roll_res.append(res)
        return res

    # Parse single dice
    def psd(self, dice_str):
        if type(dice_str) == re.Match:
            dice_str = dice_str.group()
        num, sides = dice_str.split("d")
        if dice_str.endswith("kh") or dice_str.endswith("kl"):
            kh = True if sides.endswith("kh") else False
            sides = int(sides[:-2])
            if sides >= 10000:
                raise Exception("Exceed maximum dice sides")
            if num == "" or num == "1":
                num = 2
            elif int(num) > 10000:
                raise Exception("Exceed maximum dice num")
            if kh:
                return str(
                    max(
                        [
                            Dice.rd(self, int(sides), do_save=True)
                            for _ in range(int(num))
                        ]
                    )
                )
            else:
                return str(
                    min(
                        [
                            Dice.rd(self, int(sides), do_save=True)
                            for _ in range(int(num))
                        ]
                    )
                )
        else:
            if num == "":
                num = 1
            elif int(num) > 10000:
                raise Exception("Exceed maximum dice num")
            if int(sides) > 10000:
                raise Exception("Exceed maximum dice sides")
            return str(
                sum([Dice.rd(self, int(sides), do_save=True) for _ in range(int(num))])
            )

    # Parse whole dice phrase
    def roll(self, dice_str: str) -> int:
        while re.match(r"\d*d\d+(kh|kl|)", dice_str):
            dice_str = re.sub(r"(\d*)d(\d+)(kh|kl|)", self.psd, dice_str)
        return int(eval(dice_str))

    def cal_roll_avg(self, dice_str: str, times=1000):
        return round(sum([self.roll(dice_str) for _ in range(times)]) / times, 1)

    def show_dice_distribute(self, dice_str: str):
        def pdf_unify(x):
            total = sum(x)
            return [i / total for i in x]

        def dice_pdf(dice_str):
            base = 0

            def sdp(dstr):
                if "d" not in dstr:
                    return 0, eval(dstr)
                dstr = dstr.strip()
                num, sides = dstr.split("d")
                if num == "":
                    num = 1
                if sides.endswith("kh") or sides.endswith("kl"):
                    kh = True if sides.endswith("kh") else False
                    num = int(num)
                    if num < 2:
                        num = 2
                    base = 1
                    sides = int(sides[:-2])
                    res = [(i / sides) ** (num - 1) for i in range(1, sides + 1)]
                    if not kh:
                        res.reverse()
                else:
                    num, sides = int(num), int(sides)
                    base = num
                    x = [1 for _ in range(sides)]
                    res = [1 for _ in range(sides)]
                    for _ in range(num - 1):
                        res = fftconvolve(res, x)
                return base, pdf_unify(res)

            res = []
            dice_str = dice_str.replace("+", "$+").replace("-", "$-")
            dice_str_split = dice_str.split("$")
            for dstr in dice_str_split:
                symbol = dstr[0]
                if symbol in ["+", "-"]:
                    dstr = dstr[1:]
                nbase, sp = sdp(dstr)
                if symbol == "-":
                    base -= nbase
                else:
                    base += nbase
                res.append(sp)
            final_res = res[0]
            for line in res[1:]:
                if type(line) == list:
                    final_res = fftconvolve(final_res, line)
                else:
                    base += line
            return base, final_res

        def dichotomy(arr, l: int, r: int) -> float:
            if abs(r - l) <= 1:
                return ((0.5 - arr[l]) / (arr[r] - arr[l])) * (r - l) + l
            mid = int((l + r) / 2)
            if arr[mid] == 0.5:
                return mid
            elif arr[mid] > 0.5:
                return dichotomy(arr, l, mid)
            elif arr[mid] < 0.5:
                return dichotomy(arr, mid, r)
            return 0

        base, dice_res = dice_pdf(dice_str)
        dice_x = [i + base for i in range(len(dice_res))]
        plt_ylim = max(dice_res) * 1.2
        plt.ylim(top=plt_ylim)

        dice_cdf, tmp_c = [], 0
        for i in dice_res:
            tmp_c += i
            dice_cdf.append(tmp_c)

        random_res = [
            self.roll(
                dice_str,
            )
            for _ in range(30000)
        ]
        random_y = []
        for x in dice_x:
            random_y.append(random_res.count(x))
        random_y = pdf_unify(random_y)

        balanced_res = [x * (i + base) for i, x in enumerate(dice_res)]
        resolve_avg = sum(balanced_res)
        random_avg = self.cal_roll_avg(dice_str)

        plt.plot(dice_x, dice_res, label="Resolve PDF", zorder=4)
        plt.plot(
            dice_x, [x * plt_ylim for x in dice_cdf], label="Resolve CDF", zorder=3
        )
        plt.plot(dice_x, random_y, label="Random-30k", c="lightblue", zorder=1)
        # plt.vlines(random_avg, 0, plt_ylim, colors = "gray", linestyles = "dashed", label="avg.", zorder = 2)
        plt.vlines(
            resolve_avg,
            0,
            plt_ylim,
            colors="gray",  # type: ignore
            linestyles="dashed",
            label="avg.",
            zorder=2,
        )

        self.roll_res = []
        roll_res = self.roll(dice_str)
        plt.vlines(
            roll_res,
            0,
            plt_ylim,
            colors="mistyrose",  # type: ignore
            linestyles="dashed",
            label="Roll point",
            zorder=2,
        )

        roll_detail = (
            ", ".join([str(x) for x in self.roll_res])
            if len(self.roll_res) <= 15
            else ", ".join([str(x) for x in self.roll_res[:16]]) + ", ... "
        )
        plt.title(f"{dice_str}\n{roll_res} ({roll_detail})")
        plt.xlabel(
            f"min: {base} | max: {len(dice_res)+base-1} | resolve avg.: {resolve_avg:.1f} | random avg.: {random_avg}"
        )
        plt.legend()

        plt.savefig(pic_path)
        plt.close()
        return Image.fromLocalFile(pic_path)

    def rd_sel(self, rd_str):
        rd_str = rd_str.group()
        if "/" in rd_str:
            rd_list = rd_str.replace("#", "").split("/")
            return random.choice(rd_list)
        else:
            return rd_str

    def get_insertion_dice(self, insert_str: str):
        res_str = re.sub(r"#.*?#", self.rd_sel, insert_str)
        res_str = re.sub(r"(\d*)d(\d+)(kh|kl|)", self.psd, res_str)
        return Plain(res_str.replace("#", ""))
