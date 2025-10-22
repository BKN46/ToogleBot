import math
import random
import re
from typing import Optional

import numpy as np
from matplotlib import pyplot as plt
from scipy.signal import fftconvolve

from toogle.message import Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack

pic_path = "data/dice_tmp.jpg"


class Dice(MessageHandler):
    name = "骰子"
    trigger = r"(^(\.|。|\.r|。r|/r)(`|)(\d|d|D))|(#.{0,5}[d|D|/].{0,5}#)"
    readme = (
        f"骰娘，可以使用 .d20 .1d20 .rd20 /r d20等方式触发\n"
        f"支持如.1d6+1d20+3这样的简单组合运算\n"
        f"使用.1d20kh或者.1d20kl来指定优劣势，支持类似.3d20kh2来制定取复数优劣势\n"
        f"使用.2d6r2来指定低于点数可重骰\n"
        f"使用.2d6e6来指定高于点数可爆炸(多投一颗)\n"
        f"使用.2d6>5或.2d6<2来统计大于等于或小于等于某数值的骰子个数\n"
        f"使用.2d6>5i1来统计低于某数值的骰子个数，如果骰子小于等于某一值则额外减1\n"
        f"使用.`1d20来查看概率分布"
    )

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        self.roll_res = []
        org_str = message.message.asDisplay().lower()
        dice_str = org_str[1:]
        if "#" in message.message.asDisplay():
            if len(org_str) > 50:
                return
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
                res = (
                    f"{self.roll(dice_str)}"
                    f" ({', '.join([str(x) for x in self.roll_res]) if len(self.roll_res) < 100 else 'too many dices'})"
                    f" [avg≈{self.cal_roll_avg(dice_str)}]"
                    if len(self.roll_res) < 100
                    else f""
                )
                return MessageChain.create([Plain(res)])

    # Roll dice
    def rd(self, maxium: int, do_save=False, low_reroll=0, min=0, cs=0) -> int:
        res = random.randint(1, maxium)
        if do_save:
            self.roll_res.append(res)
        if low_reroll and res <= low_reroll:
            res = random.randint(1, maxium)
            if do_save:
                self.roll_res.append(res)
        if res < min:
            res = min
        if cs:
            res = 1 if res >= cs else 0
        return res

    # Parse single dice
    def psd(self, dice_str):
        if type(dice_str) == re.Match:
            dice_str = dice_str.group()
        num, sides = dice_str.split("d")
        if "kl" in sides or "kh" in sides:
            kh = True if "kh" in sides else False
            if num == "" or num == "1":
                num = 2
            elif int(num) > 10000:
                raise Exception("Exceed maximum dice num")
            if kh:
                sides, k_num = int(sides.split("kh")[0]), sides.split("kh")[1]
            else:
                sides, k_num = int(sides.split("kl")[0]), sides.split("kl")[1]
            if not k_num:
                k_num = 1
            else:
                k_num = min(int(k_num), int(num))
            if sides >= 10000:
                raise Exception("Exceed maximum dice sides")
            return str(
                sum(
                    sorted(
                        [
                            Dice.rd(self, int(sides), do_save=True)
                            for _ in range(int(num))
                        ],
                        reverse=kh,
                    )[:k_num]
                )
            )
        else:
            if num == "":
                num = 1
            elif int(num) > 10000:
                raise Exception("Exceed maximum dice num")
            low_reroll = 0
            explode_roll = -1
            if "r" in sides:
                sides, low_reroll = int(sides.split("r")[0]), int(
                    sides.split("r")[1] or 0
                )
            elif "e" in sides:
                sides, explode_roll = int(sides.split("e")[0]), int(
                    sides.split("e")[1] or 0
                )
            if int(sides) > 10000:
                raise Exception("Exceed maximum dice sides")
            roll_result = [
                Dice.rd(self, int(sides), do_save=True, low_reroll=low_reroll)
                for _ in range(int(num))
            ]
            if explode_roll > 0:
                extra_roll_num = len([i for i in roll_result if i >= explode_roll])
                roll_result += [
                    Dice.rd(self, int(sides), do_save=True, low_reroll=low_reroll)
                    for _ in range(extra_roll_num)
                ]
            return str(
                sum(roll_result)
            )

    # Parse whole dice phrase
    def roll(self, dice_str: str, reset_history=False) -> int:
        if reset_history:
            self.roll_res = []
        while re.match(r"\d*d(\d+)(kh|kl|r|)(\d*)", dice_str):
            dice_str = re.sub(r"\d*d(\d+)(kh|kl|r|e|)(\d*)", self.psd, dice_str)
        if '>' in dice_str:
            l_tmp = dice_str.split('>')[1]
            if "i" in l_tmp:
                l_num, inner_explode = int(l_tmp.split("i")[0]), int(
                    l_tmp.split("i")[1] or 0
                )
            else:
                l_num, inner_explode = int(l_tmp), 0
            return len([i for i in self.roll_res if i >= int(l_num)]) - len([i for i in self.roll_res if i <= inner_explode])
        elif '<' in dice_str:
            l_tmp = dice_str.split('<')[1]
            if "i" in l_tmp:
                l_num, inner_explode = int(l_tmp.split("i")[0]), int(
                    l_tmp.split("i")[1] or 0
                )
            else:
                l_num, inner_explode = int(l_tmp), 0
            return len([i for i in self.roll_res if i <= l_num]) - len([i for i in self.roll_res if i <= inner_explode])
        else:
            return int(eval(dice_str))

    def cal_roll_avg(self, dice_str: str, times=1000):
        roll_res = []
        for _ in range(times):
            roll_res.append(self.roll(dice_str, reset_history=True))
        return round(sum(roll_res) / times, 1)

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

        # random
        random_res = [
            self.roll(
                dice_str,
                reset_history=True,
            )
            for _ in range(30000)
        ]
        random_y = []
        dice_x = [i + min(random_res) for i in range(max(random_res) - min(random_res) + 1)]

        plt.xlim(min(random_res), max(random_res))
        plt.xticks(
            np.arange(
                min(random_res),
                max(random_res),
                math.ceil((max(random_res) - min(random_res)) / 20),
            )
        )

        plt.xlabel("Dice result")
        for x in dice_x:
            random_y.append(random_res.count(x))

        random_avg = self.cal_roll_avg(dice_str)
        plt_ylim = 1

        # resolve
        # base, dice_res = dice_pdf(dice_str)
        # dice_x = [i + base for i in range(len(dice_res))]
        # plt_ylim = max(dice_res) * 1.2

        plt.ylim(top=plt_ylim)
        plt.yticks(np.arange(0, 1, 0.05))
        plt.ylabel("CDF Probability")
        plt.grid(True)

        def get_cdf(res):
            tmp, tmp_c = [], 0
            for i in res:
                tmp_c += i
                tmp.append(tmp_c)
            return tmp

        random_cdf = get_cdf(pdf_unify(random_y))
        random_y = [x / len(random_res) for x in random_y]
        # random_cdf = pdf_unify(random_cdf)

        # dice_cdf = get_cdf(dice_res)

        # plt.plot(dice_x, dice_res, label="Resolve PDF", zorder=4)
        # plt.plot(
        #     dice_x, [x * plt_ylim for x in dice_cdf], label="Resolve CDF", zorder=3
        # )
        plt.plot(dice_x, random_cdf, label="Random-30k-CDF", zorder=2)
        plt.legend(loc="upper left")
        ax2 = plt.twinx()
        ax2.plot(dice_x, random_y, label="Random-30k", c="lightblue", zorder=1)
        ax2.set_ylabel("Random Probability")
        ax2.set_ylim(top=max(random_y))
        ax2.set_yticks(np.arange(0, max(random_y), round(max(random_y) / 20, 3)))
        # plt.vlines(random_avg, 0, plt_ylim, colors = "gray", linestyles = "dashed", label="avg.", zorder = 2)
        # plt.vlines(
        #     resolve_avg,
        #     0,
        #     plt_ylim,
        #     colors="gray",  # type: ignore
        #     linestyles="dashed",
        #     label="avg.",
        #     zorder=2,
        # )

        self.roll_res = []
        roll_res = self.roll(dice_str)
        plt.vlines(
            roll_res,
            0,
            plt_ylim,
            colors="red",  # type: ignore
            linestyles="dashed",
            label="Roll point",
            zorder=2,
        )
        plt.legend(loc="upper right")

        roll_detail = (
            ", ".join([str(x) for x in self.roll_res])
            if len(self.roll_res) <= 15
            else ", ".join([str(x) for x in self.roll_res[:16]]) + ", ... "
        )
        plt.title(f"{dice_str}\n{roll_res} ({roll_detail})")
        plt.xlabel(
            f"min: {min(random_res)} | "
            # f"max: {len(dice_res)+base-1} | "
            f"max: {max(random_res)} | "
            # f"resolve avg.: {resolve_avg:.1f} | "
            f"random avg.: {random_avg}"
        )

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


class WarhammerD20DiceMigrate(MessageHandler):
    name = "战锤d6骰转d20计算"
    trigger = r"^\.whd20 "
    readme = (
        f"战锤d6骰转d20计算，输入骰子数量、造伤大于等于、防御大于等于，类似.whd20 6 4 5，输出d20映射表和KL散度"
    )
    
    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        msg = message.message.asDisplay().strip()[6:].strip()
        params = msg.split(" ")
        if len(params) != 3:
            n = int(params[0])
            a = 4
            d = 5
        else:
            n = int(params[0])
            a = int(params[1])
            d = int(params[2])
        distribution = WarhammerD20DiceMigrate.d6roll(n, a, d)
        mapping_string, kl_divergence, ori_exp, map_exp = WarhammerD20DiceMigrate.d20_mapping(distribution)
        res = f"d20映射表：\n{mapping_string}\n原始期望：{ori_exp:.3f}\n映射后期望：{map_exp:.3f}\nKL散度：{kl_divergence}"
        return MessageChain.plain(res)
    
    @staticmethod
    def d6roll(n, attack=4, defense=5):
        possibility = (7-attack)/6 * (defense-1)/6
        distribution = [
            math.factorial(n) / (math.factorial(x) * math.factorial(n - x)) * possibility**x * (1 - possibility)**(n - x)
            for x in range(0, n+1)
        ]
        return distribution        

    @staticmethod
    def d20_mapping(distribution):
        """
        将d6分布映射到20面骰子，输出映射字符串、KL散度、原始期望和映射后期望
        :param distribution: 分布，概率求和为1
        :return: (mapping_string, kl_divergence, original_expectation, mapped_expectation)
        """
        total_faces = 20
        num_groups = len(distribution)
        
        # 每个组至少1个面
        sizes = [1] * num_groups
        remaining = total_faces - num_groups  # 13
        
        # 按比例分配剩余面
        extra_sizes = [round(p * remaining) for p in distribution]
        sizes = [sizes[i] + extra_sizes[i] for i in range(num_groups)]
        
        # 调整使总和为20
        total_size = sum(sizes)
        diff = total_size - total_faces
        if diff > 0:
            # 减去多的，从后往前
            for i in range(num_groups-1, -1, -1):
                if sizes[i] > 1:
                    sizes[i] -= 1
                    diff -= 1
                    if diff == 0:
                        break
        elif diff < 0:
            # 加到多的，从前往后
            for i in range(num_groups):
                sizes[i] += 1
                diff += 1
                if diff == 0:
                    break
        
        # 生成映射字符串
        mapping_lines = []
        start = 1
        for val, size in enumerate(sizes):
            if size == 0:
                continue
            end = start + size - 1
            if start == end:
                mapping_lines.append(f"{start} {val}")
            else:
                mapping_lines.append(f"{start}-{end} {val}")
            start = end + 1
        mapping_string = "\n".join(mapping_lines)
        
        # 新分布
        new_dist = [size / total_faces for size in sizes]
        
        # 计算KL散度
        kl_div = 0.0
        for p, q in zip(distribution, new_dist):
            if p > 0 and q > 0:
                kl_div += p * math.log(p / q)
        
        # 计算期望
        original_expectation = sum(i * p for i, p in enumerate(distribution))
        mapped_expectation = sum(val * (size / total_faces) for val, size in enumerate(sizes))
        
        return mapping_string, kl_div, original_expectation, mapped_expectation