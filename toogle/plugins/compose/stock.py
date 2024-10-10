import io
from typing import Tuple

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import requests

font_path = "toogle/plugins/compose/fonts/TW-Sung-98-1-2.ttf"
chn_space = chr(12288)
divide = "-" * 70 + "\n"

def get_quarter_report(code: str):
    url = f"http://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/ZYZBAjaxNew?type=0&code={code}"
    res = requests.get(url)
    return res.json()["data"]


def get_bussiness(code: str):
    url = f"http://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/PageAjax?code={code}"
    res = requests.get(url)
    bussiness_range = res.json()["zyfw"][0]["BUSINESS_SCOPE"]
    return bussiness_range, res.json()["zygcfx"]


def get_search(original_text: str):
    classify_map = {
        "沪A": "SH",
        "深A": "SZ",
        "北A": "BJ",
        "港股": "HK",
        "美股": "US",
    }
    text = original_text.replace('.', '')
    for k, v in classify_map.items():
        if text.startswith(v):
            text = text[2:]
            classify_map = {k: v}
            break

    url = (
        f"https://searchapi.eastmoney.com/api/suggest/get?input={text}&type=14&count=10"
    )
    res = requests.get(url)

    def get_code(code: str):
        url = (
            f"https://datacenter.eastmoney.com/securities/api/data/v1/get?"
            f"reportName=RPT_USF10_INFO_ORGPROFILE&columns=SECUCODE"
            f"&quoteColumns=&filter=(SECURITY_CODE=\"{code}\")&pageNumber=1&pageSize=200&sortTypes=&sortColumns=&source=SECURITIES"
        )
        return requests.get(url).json()['result']['data'][0]['SECUCODE']

    def get_secucode(x):
        if x["SecurityTypeName"] == "港股":
            return f"{x['Code']}.HK"
        if x["SecurityTypeName"] == "美股":
            return get_code(x['Code'])
        else:
            return classify_map[x["SecurityTypeName"]] + x["Code"]

    try:
        search_list = []
        for x in res.json()["QuotationCodeTable"]["Data"]:
            if x["SecurityTypeName"] in classify_map.keys():
                line = (
                    get_secucode(x),
                    classify_map[x["SecurityTypeName"]] + x["Name"],
                    classify_map[x["SecurityTypeName"]] + x["Code"],
                    f"{x['QuoteID']}",
                    x["Name"],
                    )
                if any([
                    line[0] == original_text,
                    x["Code"] == original_text,
                    x["Name"] == original_text
                ]):
                    return [line]
                search_list.append(line)
    except Exception as e:
        return []

    return search_list


def get_stock_now(codes: list[str]):
    dimension_map = {
        'f2': '最新价',
        'f3': '涨跌幅',
        'f4': '涨跌额',
        'f14': '企业名',
    }
    url = "https://push2.eastmoney.com/api/qt/ulist/get"
    params = {
        'fltt': 1,
        'invt': 2,
        'fields': 'f14,f12,f13,f1,f2,f4,f3,f152',
        'secids': ",".join(codes),
        'pn': 1,
        'np': 1,
        'pz': 20,
        'dect': 1,
    }
    try:
        res = requests.get(url, params=params).json()['data']['diff']
    except Exception as e:
        return f"获取出错\n{repr(e)}"
    
    # res = "\n".join([
    #     f"{line['f14']} {line['f2']/1000:.3f} {line['f3']/100}% ({line['f4']/1000:.3f})"
    #     for line in res
    # ])
    res = {
        codes[i]: {
            v: line[k]
            for k, v in dimension_map.items()
        }
        for i, line in enumerate(res)
    }
    return res


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


def get_topic(code: str):
    url = f"http://emweb.securities.eastmoney.com/PC_HSF10/CoreConception/PageAjax?code={code}"
    res = requests.get(url)
    block = " ".join([x["BOARD_NAME"] for x in res.json()["ssbk"]])
    return block


def get_HK_gerneral(code: str):
    general_info = {
        "代码": "SECUCODE",
        "名称": "SECURITY_NAME_ABBR",
        "报告时间": "REPORT_DATE",
        "总市值": "TOTAL_MARKET_CAP",
        "发行股本": "HK_COMMON_SHARES",
        "市盈率": "PE_TTM",
    }
    url = (
        f"https://datacenter.eastmoney.com/securities/api/data/v1/get?"
        f"reportName=RPT_HKF10_FN_MAININDICATOR&columns=HKF10_FN_MAININDICATOR_NEW&filter=(SECUCODE=\"{code}\")"
        f"&pageNumber=1&pageSize=1&sortTypes=-1&sortColumns=STD_REPORT_DATE&source=F10"
    )
    res = requests.get(url).json()['result']['data']
    result_text = "[港股](单位：人民币)\n"
    for t1_key, t1_content in general_info.items():
        value = num_parse(res[0][t1_content], divided=10000, precision=2)
        result_text += f"{t1_key + ':':{chn_space}<9}{value:{chn_space}<15}\n"
    return result_text


def get_HK_quarter_report(code: str):
    key_refer = {
        "股票指标": {
            "基本每股收益": "BASIC_EPS",
            "每股净资产": "BPS",
            "每股经营现金流": "PER_NETCASH_OPERATE",
            "总资产回报率": "ROA",
        },
        "营业指标": {
            "营业总收入": "OPERATE_INCOME",
            "营业利润": "OPERATE_PROFIT",
            "净利润": "HOLDER_PROFIT",
        },
        "财务指标": {
            "资产总额": "TOTAL_ASSETS",
            "负债总额": "TOTAL_LIABILITIES",
        },
    }
    url = (
        f"https://datacenter.eastmoney.com/securities/api/data/v1/get?"
        f'reportName=RPT_HKF10_FN_MAININDICATOR&columns=HKF10_FN_MAININDICATOR_DATA&filter=(SECUCODE="{code}")'
        f"&pageNumber=1&pageSize=4&sortTypes=-1&sortColumns=STD_REPORT_DATE&source=F10"
    )
    res = requests.get(url)
    result_text = ""
    quarter_report = res.json()['result']['data']
    report_range = len(quarter_report) if len(quarter_report) < 4 else 4
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
    return result_text


def get_HK_quarter_future(code: str):
    url = (
        f"https://datacenter.eastmoney.com/securities/api/data/v1/get"
        f"?reportName=RPT_HKF10_ORG_BUSSINESS&columns=SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,ORG_CODE,SECURITY_INNER_CODE,REPORT_DATE,FUTURE_EXPECT&quoteColumns="
        f"&filter=(SECUCODE=\"{code}\")&pageNumber=1&pageSize=1&sortTypes=-1&sortColumns=REPORT_DATE&source=F10"
    )
    res = requests.get(url).json()
    if res['result']['data']:
        result_text = f"业绩展望:\n\n" + str(res['result']['data'][0]['FUTURE_EXPECT'])
    else:
        result_text = f"业绩展望:\n\n暂无"
    return result_text


def get_US_general(code: str):
    general_info = {
        "代码": "SECUCODE",
        "名称": "SECURITY_NAME_ABBR",
        "报告时间": "REPORT_DATE",
        "总市值": "TOTAL_MARKET_CAP",
        "每股净资产": "BVPS",
        "毛利率": "SALE_GPR",
        "净利率": "SALE_NPR",
        "市盈率": "PE_TTM",
    }
    url = (
        f"https://datacenter.eastmoney.com/securities/api/data/v1/get?"
        f"reportName=RPT_USF10_DATA_MAININDICATOR&columns=SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,REPORT_DATE,CURRENCY,PE_TTM,RATIO_EPS_TTM,DPS_USD,SALE_GPR,TURNOVER,HOLDER_PROFIT,ISSUED_COMMON_SHARES,PB,BVPS,DIVIDEND_RATE,SALE_NPR,TURNOVER_YOY,HOLDER_PROFIT_YOY,TOTAL_MARKET_CAP,ORG_TYPE,SECURITY_TYPE&quoteColumns=&"
        f"filter=(SECUCODE=\"{code}\")&pageNumber=1&pageSize=200&sortTypes=-1&sortColumns=REPORT_DATE&source=INTLSECURITIES"
    )
    res = requests.get(url).json()['result']['data']
    result_text = f"[美股](单位：美元)\n"
    for t1_key, t1_content in general_info.items():
        value = num_parse(res[0][t1_content], divided=10000, precision=2)
        result_text += f"{t1_key + ':':{chn_space}<9}{value:{chn_space}<15}\n"
    return result_text


def get_US_bussiness(code: str):
    bussiness_refer = {
        "经营模块": "PRODUCT_NAME",
        "营收金额（美元）": "MAIN_BUSINESS_INCOME",
        "占比": "MBI_RATIO",
    }
    url = (
        f"https://datacenter.eastmoney.com/securities/api/data/v1/get?"
        f"reportName=RPT_USF10_INFO_PRODUCTSTRUCTURE&columns=SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,ORG_CODE,REPORT_DATE,CURRENCY,PRODUCT_NAME,MAIN_BUSINESS_INCOME,MBI_RATIO,IS_TOTAL&quoteColumns="
        f"&filter=(SECUCODE=\"{code}\")(IS_TOTAL=\"0\")&pageNumber=1&pageSize=200&sortTypes=&sortColumns=&source=SECURITIES"
    )
    bussiness_report = requests.get(url).json()['result']['data']
    result_text = f"经营内容\n\n"
    if len(bussiness_report) > 0:
        for t1_key, t1_content in bussiness_refer.items():
            result_text += f"{t1_key:{chn_space}^15}"
        result_text += "\n"
        last_date = bussiness_report[0]["REPORT_DATE"]
        for part in bussiness_report:
            if last_date != part["REPORT_DATE"]:
                break
            for t1_key, t1_content in bussiness_refer.items():
                if t1_content in part:
                    result_text += (
                        f"{num_parse(part[t1_content], divided=100000000, precision=1):{chn_space}^15}"
                    )
                else:
                    result_text += f"{'---':^15}"
            result_text += "\n"
    return result_text


def get_US_quarter_report(code: str):
    def get_report(url, key_refer):
        res = requests.get(url)
        quarter_report = res.json()['result']['data']
        return report_render(quarter_report, key_refer)

    def report_render(data_list, key_refer, header=True):
        report_range = len(data_list) if len(data_list) < 4 else 4
        result_text = ""
        if header:
            result_text += f"{'':{chn_space}^16}"
            for q_index in range(report_range):
                q_name = data_list[q_index]["REPORT_DATE"].split()[0]
                result_text += f"{q_name:^24}"

        for t1_key, t1_content in key_refer.items():
            result_text += f"\n{t1_key}\n\n"
            for t2_key, t2_content in t1_content.items():
                result_text += f"{t2_key:{chn_space}^16}"
                for q_index in range(report_range):
                    value = num_parse(data_list[q_index].get(t2_content) or '---')
                    result_text += f"{value:^24}"
                result_text += "\n"
        return result_text
    
    def get_us_report(url, key_refer):
        res = requests.get(url).json()['result']['data']
        report_dict = {}
        for line in res:
            report_date = line["REPORT_DATE"]
            code = line["STD_ITEM_CODE"]
            value = line["AMOUNT"]
            if report_date not in report_dict.keys():
                report_dict[report_date] = {
                    "REPORT_DATE" : report_date
                }
            report_dict[report_date].update({
                code: value
            })
        return report_render(list(report_dict.values()), key_refer, header=False)

    result_text = ""
    result_text += get_report((
        f"https://datacenter.eastmoney.com/securities/api/data/v1/get?"
        f"reportName=RPT_USF10_FN_GMAININDICATOR&columns=USF10_FN_GMAININDICATOR&quoteColumns=&"
        f"filter=(SECUCODE=\"{code}\")"
        f"&pageNumber=1&pageSize=4&sortTypes=-1&sortColumns=REPORT_DATE&source=SECURITIES"
    ), {
        "盈利能力": {
            "收入": "OPERATE_INCOME",
            "收入环比增长": "OPERATE_INCOME_YOY",
            "毛利": "GROSS_PROFIT",
            "毛利环比增长": "GROSS_PROFIT_YOY",
            "归母净利润": "PARENT_HOLDER_NETPROFIT",
            "归母净利润环比增长": "PARENT_HOLDER_NETPROFIT_YOY",
            "基本每股收益": "BASIC_EPS",
            "销售毛利率": "GROSS_PROFIT_RATIO",
            "销售净利率": "NET_PROFIT_RATIO",
        },
        "投资回报": {
            "净资产收益率": "ROE_AVG",
            "总资产净利率": "ROA",
        },
        "资本结构" : {
            "资产负债率": "DEBT_ASSET_RATIO",
        }
    })
    result_text += f"\n{divide}"
    result_text += get_us_report((
        f"https://datacenter.eastmoney.com/securities/api/data/v1/get?"
        f"reportName=RPT_USSK_FN_CASHFLOW&columns=SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,REPORT,REPORT_DATE,STD_ITEM_CODE,AMOUNT&quoteColumns=&"
        f"filter=(SECUCODE=\"{code}\")&pageNumber=&pageSize=&sortTypes=1,-1&sortColumns=STD_ITEM_CODE,REPORT_DATE&source=SECURITIES"
    ),{
        "现金流": {
            "净利润": "001001",
            "经营活动现金流净额": "003999",
            "投资活动现金流净额": "005999",
            "筹资活动现金流净额": "007999",
            "现金及等价物变化": "011001",
            "现金及等价物期末余额": "011003",
        },
    })
    result_text += get_us_report((
        f"https://datacenter.eastmoney.com/securities/api/data/v1/get?"
        f"reportName=RPT_USF10_FN_INCOME&columns=SECUCODE%2CSECURITY_CODE%2CSECURITY_NAME_ABBR%2CREPORT%2CREPORT_DATE%2CSTD_ITEM_CODE%2CAMOUNT&quoteColumns=&"
        f"filter=(SECUCODE=\"{code}\")&pageNumber=&pageSize=&sortTypes=1,-1&sortColumns=STD_ITEM_CODE,REPORT_DATE&source=SECURITIES"
    ),{
        "经营费用": {
            "研发费用": "004007001",
            "营销费用": "004007002",
            "一般行政费用": "004007003",
            "折旧与摊销": "004007004",
            "其他营业费用": "004007006",
            "营业费用": "004007999",
        },
    })
    result_text += get_us_report((
        f"https://datacenter.eastmoney.com/securities/api/data/v1/get?"
        f"reportName=RPT_USF10_FN_BALANCE&columns=SECUCODE%2CSECURITY_CODE%2CSECURITY_NAME_ABBR%2CREPORT_DATE%2CREPORT_TYPE%2CREPORT%2CSTD_ITEM_CODE%2CAMOUNT&quoteColumns=&"
        f"filter=(SECUCODE=\"{code}\")&pageNumber=&pageSize=&sortTypes=1,-1&sortColumns=STD_ITEM_CODE,REPORT_DATE&source=SECURITIES"
    ),{
        "流动资产": {
            "现金及现金等价物": "004001001",
            "短期投资": "004001003",
            "应收账款": "004001004",
            "流动资产合计": "004001999",
        },
        "非流动资产": {
            "物业/厂房/设备": "004003001",
            "无形资产": "004003003",
            "商誉": "004003004",
            "非流动资产合计": "004003999",
        },
        "负债": {
            "流动负债合计": "004007999",
            "非流动负债合计": "004009999",
            "股东权益合计": "004013999",
        },
    })
    return result_text


def get_news(code: str):
    url = f"http://emweb.securities.eastmoney.com/PC_HSF10/NewsBulletin/PageAjax?code={code}"
    res = requests.get(url)
    news = [x["title"] for x in res.json()["gsgg"]]
    return news


def get_text_size(font, text):
    text_width = max([font.getbbox(x)[2] for x in text.split("\n")])  # type: ignore
    text_height = sum([font.getbbox(x)[3] for x in text.split("\n")])  # type: ignore
    return text_width, text_height


def text2img(
    text: str,
    font_path: str = "toogle/plugins/compose/fonts/Arial Unicode MS Font.ttf",
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
            new_string += chr(codes + 65248)  # 则转为全角
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


def render_A_stock(code: str):
    general_info = {
        "代码": "zxzb.SECUCODE",
        "名称": "zxzb.SECURITY_NAME_ABBR",
        "报告时间": "zxzb.REPORT_DATE",
        "总市值": "zxzbOther.TOTAL_MARKET_CAP",
        "总股本": "zxzb.TOTAL_SHARE",
        "流通股本": "zxzb.FREE_SHARE",
        "市盈率": "zxzbOther.PE_DYNAMIC",
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
    report_range = len(quarter_report) if len(quarter_report) < 4 else 4

    # 基本数据
    result_text = "[A股]\n"
    for key, content in general_info.items():
        index = content.split(".")
        if isinstance(general_report[index[0]], list):
            value = general_report[index[0]][0][index[1]]
        else:
            value = general_report[index[0]][index[1]]
        value = num_parse(value, divided=10000, precision=2)
        result_text += f"{key + ':':{chn_space}<9}{value:{chn_space}<15}\n"
    result_text += f"{'相关板块:':{chn_space}<9}{get_topic(code)}\n"
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
                    result_text += (
                        f"{num_parse(part[t1_content], divided=10000, precision=1):^15}"
                    )
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
    result_text += divide

    # 公告
    result_text += "公司公告:\n\n"
    news_all = get_news(code)
    for news in news_all[: min(10, len(news_all))]:
        result_text += f"{news}\n"

    text = result_text
    pic = text2img(text, font_path=font_path, max_size=(1000, 5000), word_size=14)
    return pic


def render_HK_stock(code: str):
    result_text = get_HK_gerneral(code)
    result_text += f"\n{divide}" + get_HK_quarter_report(code)
    result_text += f"\n{divide}" + get_HK_quarter_future(code)
    pic = text2img(result_text, font_path=font_path, max_size=(1000, 5000), word_size=14)
    return pic


def render_US_stock(code: str):
    result_text = get_US_general(code)
    result_text += f"\n{divide}" + get_US_bussiness(code)
    result_text += f"\n{divide}" + get_US_quarter_report(code)
    pic = text2img(result_text, font_path=font_path, max_size=(1000, 5000), word_size=14)
    return pic


def search_report(code: str):
    if "." in code:
        code = code.split(".")[1] + code.split(".")[0]
    try:
        res = render_report(code)
    except Exception as e:
        pass


def render_report(code: str):
    if any([x in code for x in ["SZ", "SH", "BJ"]]):
        return render_A_stock(code)
    elif any([x in code for x in ["HK"]]):
        return render_HK_stock(code)
    else:
        return render_US_stock(code)


if __name__ == "__main__":
    # res = render_report("SZ301061")
    # res = render_HK_stock("00700.HK")
    # res = render_US_stock("MSFT.O")
    # PIL.Image.open(io.BytesIO(res)).show()
    # print(get_search("腾讯"))
    print(get_stock_now(["116.03969"]))
    # search_name = '添加自选股 中国通号 2.885 13000'[5:].strip()
    # search_arr = search_name.split(' ')
    # print(search_arr)