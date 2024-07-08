import datetime
import json
import random

import requests
from PIL import Image, ImageDraw, ImageFont

from toogle.message import Image as GImage
from toogle.message import Member, MessageChain, Plain, Quote

pic_temp_path = "data/luck_tmp.png"
font_path = "toogle/plugins/compose/fonts/AaRunXing.ttf"

def circle_corner(img, radii, trans):
    # 画圆（用于分离4个角）
    circle = Image.new('L', (radii * 2, radii * 2))  # 创建一个黑色背景的画布
    draw = ImageDraw.Draw(circle)
    draw.ellipse((0, 0, radii * 2, radii * 2), fill=trans)  # 画白色圆形
    # 原图
    w, h = img.size
    # 画4个角（将整圆分离为4个部分）
    alpha = Image.new('L', img.size, trans)
    alpha.paste(circle.crop((0, 0, radii, radii)), (0, 0))  # 左上角
    alpha.paste(circle.crop((radii, 0, radii * 2, radii)), (w - radii, 0))  # 右上角
    alpha.paste(circle.crop((radii, radii, radii * 2, radii * 2)), (w - radii, h - radii))  # 右下角
    alpha.paste(circle.crop((0, radii, radii, radii * 2)), (0, h - radii))  # 左下角
    img.putalpha(alpha)  # 白色区域透明可见，黑色区域不可见
    return img


def max_resize(img, max_width=500, max_height=500):
    if img.size[0] >= img.size[1]:
        return img.resize((max_width, int(img.size[1] * max_width/img.size[0])), Image.ANTIALIAS) # type: ignore
    else:
        return img.resize((int(img.size[0] * max_height / img.size[1]), max_height), Image.ANTIALIAS) # type: ignore


def get_setu():
    url = "https://api.lolicon.app/setu/v2"
    pic_proxy = "https://pixiv.runrab.workers.dev/"
    pixiv_proxy = "https://i.pixiv.cat/"
    params = {}
    res = requests.get(url, params=params, timeout=3)
    res_dict = json.loads(res.text)
    pic_url = res_dict["data"][0]["urls"]["original"]
    # print(res.text)
    im = Image.open(requests.get(pic_url.replace(pixiv_proxy, pic_proxy), stream=True, timeout=5).raw)
    return im
    # return max_resize(im)


def get_font_wrap(text, font, box_width):
    res = []
    for line in text.split('\n'):
        line_width = font.getbbox(line)[2] # type: ignore
        while box_width < line_width:
            split_pos = int(box_width / line_width * len(line)) - 1
            while True:
                lw = font.getbbox(line[:split_pos])[2] # type: ignore
                rw = font.getbbox(line[:split_pos + 1])[2] # type: ignore
                if lw > box_width:
                    split_pos -= 1
                elif rw < box_width:
                    split_pos += 1
                else:
                    break
            res.append(line[:split_pos])
            line = line[split_pos:]
            line_width = font.getbbox(line)[2] # type: ignore
        res.append(line)
    return '\n'.join(res)


def get_luck_text(member: Member):
    hashStr = str(member.id) + datetime.datetime.now().strftime('%Y%m%d')
    random.seed(int(hashStr))

    luck_res = random.choice(
        '''大吉,吉,中吉,小吉,末吉,凶,大凶'''.split(',')
    )

    luck_detail = {
        '大吉': [
            '行正道能够被信赖、认同',
            '收获努力的结果，能够得到幸福',
            '追求高高的愿望，可以得到结果',
            '财富会随着新的愿望而到来'
        ],
        '吉': [
            '传递出自己的心意，好事就能接踵而来',
            '努力会以欣喜褒奖',
            '无法顺利运作的事物，能够向着好的方向前进',
            '能够邂逅很棒的人吧',
            '无论多么困难的事情都能得到周边人的帮助'
        ],
        '中吉': [
            '尝试努力就能得到收获',
            '遇到好的指引，慢慢向成功迈进',
            '去路上也许会有好事发生'
        ],
        '小吉': [
            '抱着强烈的信念的话，也许会有好事发生',
            '听听前辈或长辈的话，就会没事吧',
            '困难是能想象得到的吧',
        ],
        '末吉': [
            '事情难以进展，但有失必有得',
            '能够隐忍的话，就能看到事情的去向',
            '舍不得花凋谢的话，会被雨淋湿',
            '月有阴晴圆缺，困难会随时间离去'
        ],
        '凶': [
            '苦恼于回报，但行小善便可逃离灾厄',
            '愿望难以被人所听到',
            '困难的境地之中，请教他人便可摆脱',
            '可能会失去重要的东西，需要小心谨慎'
        ],
        '大凶': [
            '或许会遭遇到意想不到的变故',
            '欲望或会遭致痛苦',
            '不严格约束恐会失去效力',
            '是生灭法，多加小心',
            '悲伤的事情恐怕持续发生'
        ]
    }

    if 'name' in member.to_dict():
        return f"{member.name}的今日运势是:\n{luck_res}\n{random.choice(luck_detail[luck_res])}"
    else:
        return f"{member.id}的今日运势是:\n{luck_res}\n{random.choice(luck_detail[luck_res])}"


def get_luck_pic(member: Member):
    image = get_setu()
    gen_image = Image.new("RGBA", (image.size[0], image.size[1]))
    gen_image.paste(image, (0, 0))

    word_size = int(15 * max(image.size[0], image.size[1]) / 450)
    box_margin = word_size * 2
    word_box_alpha = 0.8
    word_box_alpha = int(word_box_alpha * 255)

    word_box_pos = (box_margin, int(gen_image.size[1] * 0.7))
    word_box_size = (gen_image.size[0] - 2 * box_margin, gen_image.size[1] - word_box_pos[1] - box_margin)

    font = ImageFont.truetype(font_path, word_size)
    word_box = Image.new("RGBA", (word_box_size[0], word_box_size[1]), (245, 245, 220, word_box_alpha))
    word_box = circle_corner(word_box, word_size, word_box_alpha)
    draw = ImageDraw.Draw(word_box)
    horizontal_margins, vertical_margins = min(30, word_box.size[0] * 0.1), min(30, word_box.size[1] * 0.1)
    draw.text(
        (horizontal_margins, vertical_margins),
        get_font_wrap(get_luck_text(member), font, word_box.size[0] - 2 * horizontal_margins),
        (205, 38, 38),
        font=font
    )
    gen_image.paste(word_box, (word_box_pos[0], word_box_pos[1]), word_box)
    gen_image.save(pic_temp_path)
    return GImage.fromLocalFile(pic_temp_path)
