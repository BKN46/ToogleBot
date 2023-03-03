import math
import re
import io
from typing import List, Tuple

import numpy as np
from matplotlib import pyplot as plt

ADV_PROB_TABLE = [(2*x-1)/400 for x in range(1, 21)]

def get_normal_hit_pos(ac: int, modifier: int, mode:str=""):
    tmp = ac - modifier
    if mode == 'kh':
        return max(sum(ADV_PROB_TABLE[min(tmp - 1, 20):]) - ADV_PROB_TABLE[19], 0)
    elif mode == 'kl':
        return max(sum(ADV_PROB_TABLE[:max(21 - tmp, 0)]) - ADV_PROB_TABLE[0], 0)
    else:
        return max(0, (21 - tmp) / 20)


def get_avg_damage(dice_str: str) -> Tuple[int, int]:
    dices = []
    def rd(dice_str) -> str:
        if type(dice_str) == re.Match:
            dice_str = dice_str.group()
        num, maxium = dice_str.split("d")
        if 'r' in maxium:
            maxium, low_reroll = maxium.split('r')
            res = int(num) * ((low_reroll / maxium) * (maxium + 1) / 2 + (1 - low_reroll / maxium) * (low_reroll + 1 + maxium) / 2)
        else:
            res = (1 + int(maxium)) / 2 * int(num)
        dices.append(res)
        return str(res)

    while re.match(r"\d*d\d+(r|)(\d*)", dice_str):
        dice_str = re.sub(r"(\d*)d(\d+)(r|)(\d*)", rd, dice_str)

    res = eval(dice_str)
    return res, res+sum(dices)


def get_dpr(atk: str, dice_str: str, ac_range:list=[12, 26]):
    if '+' in atk:
        atk_modifier = int(atk.split('+')[1])
        kh = atk.split('+')[0]
    else:
        atk_modifier = int(atk)
        kh = ''
    dmg_norm, dmg_crit = get_avg_damage(dice_str)
    res = []
    for ac in range(*ac_range):
        dpr = (
            dmg_norm * get_normal_hit_pos(ac, atk_modifier, kh)
            + dmg_crit * 0.05
        )
        res.append(dpr)
    return res


def draw_dpr(dpr_list: List[Tuple[str, list]], ac_range:list=[12, 26]):
    fig = plt.figure()
    plt.title(f'DRP graph')
    plt.xlabel("Enemy AC") 
    plt.ylabel("Estimated Damage Per Round") 
    plt.rcParams["font.sans-serif"]=["toogle/plugins/compose/Arial Unicode MS Font.ttf"]
    plt.xticks(range(*ac_range), range(*ac_range))

    y_max = max([max(i[1]) for i in dpr_list])
    y_min = min([min(i[1]) for i in dpr_list])
    plt.yticks(np.arange(math.floor(y_min), math.ceil(y_max), 2.0))

    x = range(*ac_range)
    for dpr in dpr_list:
        plt.plot(x, dpr[1], label=dpr[0])
    plt.legend()
    # plt.show()
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png')
    plt.close()
    return img_buf.getvalue()


if __name__ == "__main__":
    import PIL.Image
    dpr_list = [
        ('kensei', get_dpr('5', '2d8+4d6+3')),
        ('hex', get_dpr('5', '2d8+6')),
        ('great weapon', get_dpr('5', 'd12r2'))
    ]
    img = draw_dpr(dpr_list)
    PIL.Image.open(img).show()
