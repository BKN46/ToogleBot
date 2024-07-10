import base64
import datetime
import io
import json
import os
import random
import sys

import PIL.Image
import PIL.ImageColor
import PIL.ImageDraw
import PIL.ImageFont

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


FONT_PATH = "/root/repos/ToogleBot/toogle/plugins/compose/fonts/zixiaohun.ttf"
TARROT_DATA_PATH = "/root/repos/ToogleBot/data/tarrot.json"
if not os.path.exists(TARROT_DATA_PATH):
    with open(TARROT_DATA_PATH, "w") as f:
        f.write("{}")

TARROT_DATA = json.load(open(TARROT_DATA_PATH, "r"))
'''
{
    "name": str,
    "format": str,
    "base64: str,
    "meaning": List[str],
    "can_reverse": bool,
}
'''

TARROT_SPREADS = {
    "单张": [[0, 0]],
    "时间之箭": [[0, 0.5], [1.5, 0], [3, 0.5]],
    "圣三角": [[0, 0], [1, 1], [2, 0]],
    "身心灵": [[1.7, 0], [1, 1, 1], [0, 2], [3.5, 2]],
    "恋爱圣三角": [[2, 0], [1.3, 1, 2], [0, 1.2], [3.2, 1.6]],
    "万能": [[1.5, 0], [0, 1.3], [1.5, 1.6], [3, 1.3]],
    "四元素": [[0, 0], [2, 0], [1, 1, 1], [0, 2], [2, 2]],
    "大十字": [[1, 0], [1, 1, 1], [0, 1], [2, 1], [1, 2]],
    "二则一": [[0, 0], [0.8, 1], [1.7, 2], [2.6, 1], [3.4, 0]],
    "爱情十字": [[0, 0, 2], [0.4, 1], [1.4, 0], [1.4, 1], [2.4, 1], [1.4, 2]],
    "未来恋人": [[0, 2], [0.8, 1], [1.7, 0, 2], [2.6, 1], [3.4, 2], [1.7, 2.7]],
    "周运": [[0, 0], [1, 0], [2, 0], [3, 0], [1, 1], [2, 1], [3, 1]],
}

TARROT_SIZE = (300, 500)
TABLE_MARGIN = 100
TARROT_MARGIN = 70
CARD_FONT_SIZE = 30

def random_low_sat_dark_color():
    color = PIL.ImageColor.getrgb(f"hsl({random.randint(0, 360)}, {random.randint(20, 100)}%, {random.randint(10, 30)}%)")
    return color


def get_tarrot(spread_name: str, header="", return_deck=False):
    spread = TARROT_SPREADS.get(spread_name, [])
    if not spread:
        raise Exception("未知塔罗牌阵")
    draw = random.sample(TARROT_DATA, len(spread))
    detail = [spread_name]
    random.shuffle(draw)

    max_h, max_v = max([x[0] for x in spread]) + 1, max([x[1] for x in spread]) + 1
    table = PIL.Image.new(
        "RGB",
        (
            int((TARROT_SIZE[0] + TARROT_MARGIN) * max_h + 2 * TABLE_MARGIN),
            int((TARROT_SIZE[1] + TARROT_MARGIN) * max_v + 2 * TABLE_MARGIN),
        ),
        color=random_low_sat_dark_color(),
    )
    font = PIL.ImageFont.truetype(FONT_PATH, CARD_FONT_SIZE)
    pic_draw = PIL.ImageDraw.Draw(table)

    pic_draw.text(
        (2, 2),
        f"{header} ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})",
        fill="#FFFFFF",
        font=font,
    )

    for index, card in enumerate(draw):
        card_pic = PIL.Image.open(io.BytesIO(base64.b64decode(card["base64"])))
        card_pic = card_pic.resize(TARROT_SIZE)
        card_reverse = False
        if random.random() > 0.5:
            card_pic = card_pic.rotate(180)
            card_reverse = True

        if len(spread[index]) >= 3:
            pos_type = spread[index][2]
        else:
            pos_type = 0

        card_pos = (
            int(spread[index][0] * (TARROT_SIZE[0] + TARROT_MARGIN) + TABLE_MARGIN + TARROT_MARGIN / 2),
            int(spread[index][1] * (TARROT_SIZE[1] + TARROT_MARGIN) + TABLE_MARGIN + TARROT_MARGIN / 2),
        )
        if pos_type:
            if pos_type == 1:
                type_color = "#666"
            elif pos_type == 2:
                type_color = "#BC4031"
            else:
                type_color = "#000"
            pic_draw.rounded_rectangle(
                (
                    int(card_pos[0] - TARROT_MARGIN / 4),
                    int(card_pos[1] - TARROT_MARGIN / 4),
                    int(card_pos[0] + TARROT_SIZE[0] + TARROT_MARGIN / 4),
                    int(card_pos[1] + TARROT_SIZE[1] + TARROT_MARGIN / 4),
                ),
                fill=type_color,
                width=10,
                radius=5,
            )

        table.paste(
            card_pic,
            card_pos,
        )

        card_text = card["name"].split(".")[0]
        while card_text[0].isdigit():
            card_text = card_text[1:]
        if card_reverse:
            card_text += "（逆位）"
        detail.append(card_text)

        pic_draw.text(
            (
                card_pos[0],
                card_pos[1] - CARD_FONT_SIZE - 5,
            ),
            card_text,
            fill="#FFFFFF",
            font=font,
        )

        if card_reverse:
            desc = card["meaning"][1]
        else:
            desc = card["meaning"][0]

        desc = desc[:30] + "..." if len(desc) > 30 else desc
        pic_draw.text(
            (
                card_pos[0],
                card_pos[1] + TARROT_SIZE[1] - 5,
            ),
            desc,
            fill="#FFFFFF",
            font=font,
        )

    output_bytes = io.BytesIO()
    table.save(output_bytes, format="PNG")
    # output_bytes.seek(0)

    if return_deck:
        return output_bytes.getvalue(), detail
    return output_bytes.getvalue()


if __name__ == "__main__":
    test = get_tarrot("身心灵")
    with open("test.png", "wb") as f:
        f.write(test) # type: ignore
