import base64
import io
import random

import PIL.Image
import PIL.ImageColor
import PIL.ImageDraw
import PIL.ImageFont

from toogle.plugins.waifu_utils.waifu_random import text_on_image, buffered_url_pic, max_resize


def width_resize(img, max_width, min_height):
    if img.size[1] < img.size[0] and int(img.size[1] * max_width / img.size[0]) < min_height:
        return img.resize(
            (int(img.size[0] * min_height / img.size[1]), min_height),
            PIL.Image.Resampling.LANCZOS,
        )
    else:
        return img.resize(
            (max_width, int(img.size[1] * max_width / img.size[0])),
            PIL.Image.Resampling.LANCZOS,
        )


def circle_corner(img, radii, trans, border=0):
    # 画圆（用于分离4个角）
    circle = PIL.Image.new('L', (radii * 2, radii * 2))  # 创建一个黑色背景的画布
    draw = PIL.ImageDraw.Draw(circle)
    draw.ellipse((0, 0, radii * 2, radii * 2), fill=trans)  # 画白色圆形
    # 原图
    w, h = img.size
    # 画4个角（将整圆分离为4个部分）
    alpha = PIL.Image.new('L', img.size, trans)
    alpha.paste(circle.crop((0, 0, radii, radii)), (0, 0))  # 左上角
    alpha.paste(circle.crop((radii, 0, radii * 2, radii)), (w - radii, 0))  # 右上角
    alpha.paste(circle.crop((radii, radii, radii * 2, radii * 2)), (w - radii, h - radii))  # 右下角
    alpha.paste(circle.crop((0, radii, radii, radii * 2)), (0, h - radii))  # 左下角
    img.putalpha(alpha)  # 白色区域透明可见，黑色区域不可见

    if border:
        draw = PIL.ImageDraw.Draw(img)
        draw.rounded_rectangle(img.getbbox(), outline="black", width=border, radius=radii)

    return img


def add_noise(im: PIL.Image.Image):
    for i in range( round(im.size[0]*im.size[1]/20) ):
        im.putpixel(
            (random.randint(0, im.size[0]-1), random.randint(0, im.size[1]-1)),
            (random.randint(0,255),random.randint(0,255),random.randint(0,255))
        )
    return im


def add_circle_texture(im: PIL.Image.Image):
    new_img = PIL.Image.new("RGBA", im.size, (0, 0, 0, 0))
    img_draw = PIL.ImageDraw.Draw(new_img, 'RGBA')
    x_space, length = 50, 50
    for x in range(- x_space // 2, new_img.size[0] + x_space, x_space):
        for y in range(- length // 2, new_img.size[1] + length, length):
            # img_draw.arc([(x, y), (x, y + length)], 30, -30, fill=(230, 230, 230, 255))
            img_draw.ellipse([(x - x_space, y - length), (x + x_space, y + length)], (230, 230, 230, 0), outline=(30, 30, 30, 50))
    im.paste(new_img, (0, 0), new_img)
    return im


def generate_shine(src_img: PIL.Image.Image):
    img = PIL.Image.new("RGBA", (src_img.size[0] * 2, src_img.size[1] * 2), (0,0,0,0))
    img_draw = PIL.ImageDraw.Draw(img)
    colors = [
        (254,1,254),
        (0,245,246),
        (89,255,182),
        (255,253,101),
    ] * 2
    rotation = 45
    width, height = img.size
    single_color_height = (height // len(colors))
    for y in range(0, height):
        color_index = y // single_color_height
        first_color = colors[color_index]
        second_color = colors[(color_index + 1) % len(colors)]
        def color_select(index):
            return round(first_color[index] + (second_color[index] - first_color[index]) / single_color_height * (y % single_color_height))
        bg_r, bg_g, bg_b = color_select(0), color_select(1), color_select(2)
        img_draw.line([(0, y),(width, y)],fill = (bg_r,bg_g,bg_b))
    img = img.rotate(rotation, expand=True)
    src_img.paste(img, (-img.size[0] // 3, -img.size[1] // 3), img)
    return src_img


TYPE_COLOR_MAP = {
    "game": (243, 245, 114),
    "h-game": (222, 255, 78),
    "mobile game": (146, 153, 230),
    "visual novel": (159, 238, 245),
    "light novel": (235, 196, 141),
    "ova": (89, 255, 157),
    "anime": (255, 149, 120),
}

RANK_COLOR = {
    "UR": (230, 100, 203),
    "SSR": (250, 174, 89),
    "SR": (250, 245, 97),
    "R": (207, 212, 250),
    "N": (80, 80, 80),
}


def get_waifu_card(
    owner: str,
    name: str,
    pic_url: str,
    src_name: str,
    src_type: str,
    desc: str,
    cv: str,
    font_path: str = 'toogle/plugins/compose/FangZhengKaiTi-GBK-1.ttf',
    is_new: bool = True,
    is_female: bool = True,
    waifu_score: float = 0,
    waifu_rank: str = '',
    is_repeat: str = '',
    is_shine: bool = False,
    no_center_box: bool = False,
):
    CARD_SIZE = (630, 880)
    PADDING = 20
    font = PIL.ImageFont.FreeTypeFont(font_path, size=30)
    font2 = PIL.ImageFont.FreeTypeFont(font_path, size=20)

    if ',' in cv:
        cv = cv.split(',')[1].strip()

    gen_image = PIL.Image.new(
        "RGBA",
        CARD_SIZE,
        (30, 30, 30),
    )
    if is_shine:
        gen_image = generate_shine(gen_image)
    gen_image = circle_corner(gen_image, 30, 255)

    if no_center_box:
        center_box = PIL.Image.new(
            "RGBA",
            (CARD_SIZE[0] - PADDING * 2, CARD_SIZE[1] - PADDING * 2),
            (0, 0, 0, 0),
        )
    else:
        center_box = circle_corner(add_noise(PIL.Image.new(
            "RGBA",
            (CARD_SIZE[0] - PADDING * 2, CARD_SIZE[1] - PADDING * 2),
            TYPE_COLOR_MAP.get(src_type.lower(), (3, 169, 244)),
        )), 10, 255)
    image_draw = PIL.ImageDraw.Draw(center_box)

    # ======== name ========
    name_slot = circle_corner(PIL.Image.new(
        "RGBA",
        (CARD_SIZE[0] - PADDING * 4, 40),
        (230, 230, 230, 200),
    ), 20, int(255 * 1), border=2)
    center_box.paste(
        name_slot,
        (PADDING, PADDING),
        name_slot
    )

    image_draw.text(
        (PADDING + 25, PADDING + 5),
        name,
        font=font,
        fill=(0, 0, 0)
    )

    # ======== pic ========
    figure_slot = PIL.Image.new(
        "RGBA",
        (CARD_SIZE[0] - PADDING * 4 - 40, int(CARD_SIZE[1] * 0.5)),
        (230, 230, 230),
    )
    figure_pic = width_resize(
        buffered_url_pic(pic_url),
        max_width = figure_slot.size[0],
        min_height = figure_slot.size[1],
    ).convert("RGBA")
    figure_slot.paste(figure_pic, (0, -20), figure_pic)
    figure_slot = circle_corner(figure_slot , 0, int(255 * 1), border=2)

    center_box.paste(
        figure_slot,
        (PADDING + 20, PADDING + 40),
        figure_slot
    )

    # ======== src ========
    src_slot = circle_corner(PIL.Image.new(
        "RGBA",
        (CARD_SIZE[0] - PADDING * 4, 40),
        (230, 230, 230, 200),
    ), 20, int(255 * 1), border=2)
    center_box.paste(
        src_slot,
        (PADDING, PADDING + int(CARD_SIZE[1] * 0.5) + 40),
        src_slot
    )

    image_draw.text(
        (PADDING + 25, PADDING + 45 + int(CARD_SIZE[1] * 0.5)),
        src_name,
        font=font,
        fill=(0, 0, 0)
    )

    # ======== desc ========
    desc_slot = PIL.Image.new(
        "RGBA",
        (CARD_SIZE[0] - PADDING * 4 - 40, int(CARD_SIZE[1] * 0.3)),
        (230, 230, 230),
    )
    desc_slot = add_circle_texture(desc_slot)
    desc_slot = circle_corner(desc_slot, 0, int(255 * 1), border=2)

    desc = '\n'.join([x for x in desc.split('\n') if not any(
        x.startswith(y) for y in ['CV', '姓名', '来源', '类型', 'score', 'rank']
    )])

    if is_repeat:
        owner = is_repeat

    text_on_image(
        desc_slot,
        f"{owner}的{'老婆' if is_female else '老公'}\n{desc}",
        font_path=font_path,
        word_size=20,
        max_size=(CARD_SIZE[0] - PADDING * 4 - 70, int(CARD_SIZE[1] * 0.3 - 20)),
        pos=(15, 10),
        # bg_color=bg_color,
        font_color=(0, 0, 0),
        font_height_adjust=6,
    )

    center_box.paste(
        desc_slot,
        (PADDING + 20, PADDING + int(CARD_SIZE[1] * 0.5) + 80),
        desc_slot
    )


    # ======== 底边文本 ========
    image_draw.text(
        (10, CARD_SIZE[1] - PADDING - 45),
        src_type.capitalize(),
        font=font2,
        fill=(0, 0, 0)
    )
    cv = f"CV: {cv.capitalize()}"
    cv_text_len = font2.getbbox(cv)[2]
    image_draw.text(
        (CARD_SIZE[0] - PADDING * 2 - cv_text_len - 5, CARD_SIZE[1] - PADDING - 45),
        cv,
        font=font2,
        fill=(0, 0, 0)
    )

    # Rank标签
    if waifu_rank:
        rank_slot = circle_corner(PIL.Image.new(
            "RGBA",
            (130, 30),
            (30, 30, 30),
        ), 15, int(255 * 1), border=0)
        rank_slot_pos = (CARD_SIZE[0] - PADDING * 2 - 140, PADDING + int(CARD_SIZE[1] * 0.8) + 55)
        center_box.paste(
            rank_slot,
            rank_slot_pos,
            rank_slot
        )

        image_draw.text(
            (rank_slot_pos[0] + 10, rank_slot_pos[1] + 2),
            f"{waifu_rank} [{waifu_score:.1f}]",
            font=font2,
            fill=RANK_COLOR.get(waifu_rank, (80, 80, 80))
        )

    gen_image.paste(
        center_box,
        (PADDING, PADDING),
        center_box
    )

    # NEW标签
    if is_new and not is_repeat:
        new_band = PIL.Image.new(
            "RGBA",
            (300, 80),
            (255, 64, 64)
        )
        band_draw = PIL.ImageDraw.Draw(new_band)
        band_draw.text(
            (120, 5),
            "NEW",
            font=font,
            fill=(255, 255, 255),
        )
        band_draw.text(
            (60, 50),
            "输入'锁定老婆'来锁定",
            font=font2,
            fill=(255, 255, 255),
        )
        new_band = new_band.rotate(-45,expand=True, resample=PIL.Image.Resampling.BICUBIC)
        gen_image.paste(
            new_band,
            (CARD_SIZE[0] - 200, -70),
            new_band
        )
    
    # 重复标签
    if is_repeat:
        repeat_band = PIL.Image.new(
            "RGBA",
            (CARD_SIZE[0], 120),
            (120, 120, 120, int(255 * 0.8))
        )
        band_draw = PIL.ImageDraw.Draw(repeat_band)
        band_draw.text(
            (CARD_SIZE[0] // 2 - 50, 25),
            "被抢先了",
            font=font,
            fill=(255, 255, 255),
        )
        text = f"被{is_repeat}抢先一步"
        text_length = font2.getbbox(text)[2]
        band_draw.text(
            (CARD_SIZE[0] // 2 - text_length // 2, 60),
            text,
            font=font2,
            fill=(255, 255, 255),
        )
        gen_image.paste(
            repeat_band,
            (0, CARD_SIZE[1] // 2 - 60),
            repeat_band
        )

    img_bytes = io.BytesIO()
    gen_image.save(img_bytes, format="PNG")
    # gen_image.show()
    return img_bytes.getvalue()


def ranking_compose(waifu_data_list, highlight=0) -> bytes:
    FONT_TYPE = "toogle/plugins/compose/Arial Unicode MS Font.ttf"
    SIZE = [1500, 4000]
    PIC_SIZE = [350, int(SIZE[1] / 10)]
    BG_COLOR = [
        (255, 255, 255),
        (235, 235, 235),
        (200, 238, 243),
    ]

    SIZE[1] = PIC_SIZE[1] * len(waifu_data_list)
    gen_image = PIL.Image.new("RGBA", tuple(SIZE), (255, 255, 255))

    bg_num_font = PIL.ImageFont.truetype(FONT_TYPE, 200)
    name_font = PIL.ImageFont.truetype(FONT_TYPE, 60)
    src_font = PIL.ImageFont.truetype(FONT_TYPE, 30)
    score_font = PIL.ImageFont.truetype(FONT_TYPE, 70)
    rank_font = PIL.ImageFont.truetype(FONT_TYPE, 180)
    user_font = PIL.ImageFont.truetype(FONT_TYPE, 50)

    for index, waifu_data in enumerate(waifu_data_list):
        user_name = waifu_data["id"]
        ac_data = waifu_data["data"]
        ac_stand = waifu_data["rank"]

        pic_base64 = ac_data.get("pic_bytes", "")
        if pic_base64:
            image = max_resize(PIL.Image.open(io.BytesIO(base64.b64decode(pic_base64)))).convert("RGBA")
        else:
            image = max_resize(buffered_url_pic(ac_data["pic"])).convert("RGBA")
        ac_name = ac_data["name"]
        ac_src = ac_data["src"]
        ac_score = ac_data["score"]
        ac_rank = ac_data["rank"]

        word_box = PIL.Image.new(
            "RGBA", (SIZE[0] - PIC_SIZE[0], PIC_SIZE[1]), (255, 255, 255, 0)
        )
        draw = PIL.ImageDraw.Draw(word_box)

        std_text = f"{ac_stand}"
        # std_text_size = draw.textsize(std_text, font=bg_num_font)
        draw.text(
            (SIZE[0] - 350 - len(std_text) * 120, 200),
            std_text,
            BG_COLOR[(index + 1) % 2],
            font=bg_num_font,
        )
        if ac_stand == highlight:
            pic_bg = PIL.Image.new("RGBA", (SIZE[0], PIC_SIZE[1]), BG_COLOR[2])
        else:
            pic_bg = PIL.Image.new("RGBA", (SIZE[0], PIC_SIZE[1]), BG_COLOR[index % 2])
        gen_image.paste(pic_bg, (0, index * PIC_SIZE[1]))

        offset_x = int((PIC_SIZE[0] - image.size[0]) / 2)
        offset_y = int((PIC_SIZE[1] - image.size[1]) / 2)
        gen_image.paste(image, (offset_x, index * PIC_SIZE[1] + offset_y), image)

        draw.text((20, 40), f"{ac_name}", (0, 0, 0), font=name_font)
        draw.text((20, 110), f"《{ac_src}》", (0, 0, 0), font=src_font)
        draw.text((0, 160), f"{ac_rank}", RANK_COLOR[ac_rank], font=rank_font)
        draw.text((370, 180), f"SCORE {ac_score: .2f}", (0, 0, 0), font=score_font)
        draw.text((370, 260), f"对象是 {user_name}", (0, 0, 0), font=user_font)
        draw.text((540, 310), f"{waifu_data['qq']}", (50, 50, 50), font=src_font)
        draw.text(
            (900, 40),
            f"[ {ac_data.get('def', 'NONE')} ]",
            BG_COLOR[(index + 1) % 2],
            font=score_font,
        )
        gen_image.paste(word_box, (PIC_SIZE[0], index * PIC_SIZE[1]), word_box)

    img_bytes = io.BytesIO()
    gen_image.save(img_bytes, format="PNG")
    return img_bytes.getvalue()


if __name__ == "__main__":
    from toogle.plugins.waifu.waifu import get_random_anime_character
    res_pic_url, res_text, res_id, res_raw  = get_random_anime_character('f')
    pic_bytes = get_waifu_card(
        'BKN',
        res_raw['姓名'],
        res_pic_url or '',
        res_raw['来源'],
        res_raw['类型'],
        res_text,
        res_raw['CV'],
        "FangZhengKaiTi-GBK-1.ttf",
        waifu_score=1164.4,
        waifu_rank='UR',
        is_repeat='Test',
    )
    open('tmp.png', 'wb').write(pic_bytes)
