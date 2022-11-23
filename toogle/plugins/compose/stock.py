import io
from typing import Tuple

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import requests

font_path = "toogle/plugins/compose/TW-Sung-98-1-2.ttf"
chn_space = chr(12288)


def get_quarter_report(code: str):
    url = f"http://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/ZYZBAjaxNew?type=0&code={code}"
    res = requests.get(url)
    return res.json()["data"]


def get_bussiness(code: str):
    url = f"http://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/PageAjax?code={code}"
    res = requests.get(url)
    bussiness_range = res.json()["zyfw"][0]["BUSINESS_SCOPE"]
    return bussiness_range, res.json()["zygcfx"]


def get_search(text: str):
    url = (
        f"https://searchapi.eastmoney.com/api/suggest/get?input={text}&type=14&count=10"
    )
    res = requests.get(url)

    classify_map = {
        "沪A": "SH",
        "深A": "SZ",
        "北A": "BJ",
    }

    search_list = [
        (classify_map[x["SecurityTypeName"]] + x["Code"], x["Name"])
        for x in res.json()["QuotationCodeTable"]["Data"]
        if x["SecurityTypeName"] in classify_map.keys()
    ]

    return search_list


def get_font_wrap(text: str, font: PIL.ImageFont.ImageFont, box_width: int):
    res = []
    for line in text.split("\n"):
        line_width = font.getbbox(line)[2]  # type: ignore
        while box_width < line_width:
            split_pos = int(box_width / line_width * len(line)) - 1
            while True:
                lw = font.getbbox(line[:split_pos])[2]  # type: ignore
                rw = font.getbbox(line[: split_pos + 1])[2]  # type: ignore
                if lw > box_width:
                    split_pos -= 1
                elif rw < box_width:
                    split_pos += 1
                else:
                    break
            res.append(line[:split_pos])
            line = line[split_pos:]
            line_width = font.getbbox(line)[2]  # type: ignore
        res.append(line)
    return "\n".join(res)


def get_general_info(code: str):
    url = f"http://emweb.securities.eastmoney.com/PC_HSF10/OperationsRequired/PageAjax?code={code}"
    res = requests.get(url)
    return res.json()


def get_text_size(font, text):
    text_width = max([font.getbbox(x)[2] for x in text.split("\n")])  # type: ignore
    text_height = sum([font.getbbox(x)[3] for x in text.split("\n")])  # type: ignore
    return text_width, text_height


def text2img(
    text: str,
    font_path: str = "toogle/plugins/compose/Arial Unicode MS Font.ttf",
    word_size: int = 20,
    max_size: Tuple[int, int] = (500, 1000),
    padding: Tuple[int, int] = (20, 20),
    bg_color: Tuple[int, int, int] = (255, 255, 255),
    font_color: Tuple[int, int, int] = (20, 20, 20),
) -> bytes:
    font = PIL.ImageFont.truetype(font_path, word_size)
    text = get_font_wrap(text, font, max_size[0] - 2 * padding[0])  # type: ignore
    text_width = max([font.getbbox(x)[2] for x in text.split("\n")])
    # text_height = sum([font.getbbox(x)[3] for x in text.split("\n")])  # type: ignore
    text_height = (word_size + 3) * len(text.split("\n"))

    gen_image = PIL.Image.new(
        "RGBA",
        (text_width + 2 * padding[0], min(max_size[1], text_height + 2 * padding[1])),
        bg_color,
    )
    draw = PIL.ImageDraw.Draw(gen_image)

    draw.text(
        (padding[0], padding[1]),
        text,
        font_color,
        font=font,
    )
    img_bytes = io.BytesIO()
    gen_image.save(img_bytes, format="PNG")
    return img_bytes.getvalue()


def chr2full(text):
    new_string = ""
    for i in text:
        codes = ord(i)  # 将字符转为ASCII或UNICODE编码
        if codes <= 126:  # 若是半角字符
            new_string += chr(codes+65248) # 则转为全角
        else:
            new_string += i
    return new_string


def num_parse(num, divided: int = 1, precision: int = 4):
    if divided == 1e8:
        divided_sign = "亿"
    elif divided == 1e4:
        divided_sign = "万"
    elif divided == 1e3:
        divided_sign = "千"
    else:
        divided_sign = ""
    if isinstance(num, int):
        if num < divided:
            res = f"{num:,d}"
        elif divided > 1:
            res = f"{num/divided:,.2f}{divided_sign}"
        else:
            res = f"{num:,d}"
    elif isinstance(num, float):
        if num < divided:
            res = f"{num:,.4f}"
        else:
            res = f"{num/divided:,.{precision}f}{divided_sign}"
    elif num == None:
        res = "---"
    else:
        res = num
    return res


def render_report(code: str):
    general_info = {
        "名称": "zxzb.SECUCODE",
        "代码": "zxzb.SECURITY_NAME_ABBR",
        "报告时间": "zxzb.REPORT_DATE",
        "总市值": "zxzbOther.TOTAL_MARKET_CAP",
        "总股本": "zxzb.TOTAL_SHARE",
        "流通股本": "zxzb.FREE_SHARE",
        "市盈率": "zxzbOther.PB_NEW_NOTICE",
    }
    bussiness_refer = {
        "收入模块": "ITEM_NAME",
        "收入": "MAIN_BUSINESS_INCOME",
        "收入占比": "MBI_RATIO",
        "成本": "MAIN_BUSINESS_COST",
        "成本占比": "MBC_RATIO",
        "利润": "MAIN_BUSINESS_RPOFIT",
        "利润占比": "MBR_RATIO",
        "毛利率": "GROSS_RPOFIT_RATIO",
    }
    key_refer = {
        "股票指标": {
            "基本每股收益": "EPSJB",
            "扣非每股收益": "EPSKCJB",
            "每股净资产": "BPS",
        },
        "营业指标": {
            "营业总收入": "TOTALOPERATEREVE",
            "归属净利润": "PARENTNETPROFIT",
            "营业总收入同比增长": "TOTALOPERATEREVETZ",
            "归属净利润同比增长": "PARENTNETPROFITTZ",
            "营业总收入环比增长": "YYZSRGDHBZC",
            "归属净利润环比增长": "NETPROFITRPHBZC",
        },
        "盈利指标": {
            "加权净资产收益率": "ROEJQ",
            "毛利率": "XSMLL",
            "净利率": "XSJLL",
        },
        "财务指标": {
            "现金流量比率": "XJLLB",
            "资产负债率": "ZCFZL",
        },
    }
    general_report = get_general_info(code)
    quarter_report = get_quarter_report(code)
    bussiness_info, bussiness_report = get_bussiness(code)
    report_range = len(quarter_report) if len(quarter_report) < 3 else 3

    divide = "-" * 70 + "\n"

    # 基本数据
    result_text = ""
    for key, content in general_info.items():
        index = content.split(".")
        if isinstance(general_report[index[0]], list):
            value = general_report[index[0]][0][index[1]]
        else:
            value = general_report[index[0]][index[1]]
        value = num_parse(value)
        result_text += f"{key + ':':{chn_space}<9}{value:{chn_space}<15}\n"
    result_text += divide

    # 经营内容
    result_text += f"经营内容\n{bussiness_info}\n\n"
    if len(bussiness_report) > 0:
        for t1_key, t1_content in bussiness_refer.items():
            result_text += f"{t1_key:^13}"
        result_text += "\n"
        last_date = bussiness_report[0]["REPORT_DATE"]
        for part in bussiness_report:
            if last_date != part["REPORT_DATE"]:
                break
            for t1_key, t1_content in bussiness_refer.items():
                if t1_content in part:
                    result_text += f"{num_parse(part[t1_content], divided=10000, precision=1):^15}"
                else:
                    result_text += f"{'---':^15}"
            result_text += "\n"
    result_text += divide

    # 财报
    result_text += f"季度报\n"
    result_text += f"{'':{chn_space}^16}"
    for q_index in range(report_range):
        q_name = quarter_report[q_index]["REPORT_DATE"].split()[0]
        result_text += f"{q_name:^24}"

    for t1_key, t1_content in key_refer.items():
        result_text += f"\n{t1_key}\n\n"
        for t2_key, t2_content in t1_content.items():
            result_text += f"{t2_key:{chn_space}^16}"
            for q_index in range(report_range):
                value = num_parse(quarter_report[q_index][t2_content])
                result_text += f"{value:^24}"
            result_text += "\n"

    text = result_text
    pic = text2img(text, font_path=font_path, max_size=(1000, 5000), word_size=14)
    # PIL.Image.open(io.BytesIO(pic)).show()
    return pic


def search_report(code: str):
    if "." in code:
        code = code.split(".")[1] + code.split(".")[0]
    try:
        res = render_report(code)
    except Exception as e:
        pass


if __name__ == "__main__":
    render_report("SZ301061")
    # get_search("中顺")
