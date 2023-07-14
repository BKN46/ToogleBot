import datetime
import io
from queue import Queue
import time
import traceback
from typing import List, Union

from matplotlib import pyplot as plt
import matplotlib.dates as mdates
from qdata.baidu_index import (
    get_feed_index,
    get_news_index,
    get_search_index,
    get_live_search_index
)
from qdata.baidu_index.common import check_keywords_exists
from qdata.baidu_login import get_cookie_by_qr_login


try:
    cookies = open("data/baidu_cookie", "r").read()
except Exception as e:
    raise Exception("无data/baidu_cookie文件，请先运行toogle/plugins/others/baidu_index.py获取cookie")


def get_clear_keywords_list(keywords_list: List[List[str]]) -> List[List[str]]:
    q = Queue(-1)

    cur_keywords_list = []
    for keywords in keywords_list:
        cur_keywords_list.extend(keywords)
    
    # 先找到所有未收录的关键词
    for start in range(0, len(cur_keywords_list), 15):
        q.put(cur_keywords_list[start:start+15])
    
    not_exist_keyword_set = set()
    while not q.empty():
        keywords = q.get()
        check_result={}
        try:
            check_result = check_keywords_exists(keywords, cookies)
            time.sleep(5)
        except:
            traceback.print_exc()
            q.put(keywords)
            time.sleep(90)

        for keyword in check_result["not_exists_keywords"]:
            not_exist_keyword_set.add(keyword)
    
    # 在原有的keywords_list拎出没有收录的关键词
    new_keywords_list = []
    for keywords in keywords_list:
        not_exists_count = len([None for keyword in keywords if keyword in not_exist_keyword_set])
        if not_exists_count == 0:
            new_keywords_list.append(keywords)

    return new_keywords_list


def grasp_search_index(keyword_list: list) -> bytes:
    """获取搜索指数"""
    to_date = datetime.datetime.now()
    from_date = to_date - datetime.timedelta(days=365)
    data = get_search_index(
        keywords_list=keyword_list,
        start_date=from_date.strftime("%Y-%m-%d"),
        end_date=to_date.strftime("%Y-%m-%d"),
        cookies=cookies
    )
    res = []
    for line in data:
        if line['type'] == 'wise':
            res.append(float(line['index']))

    dates = mdates.drange(from_date, to_date, datetime.timedelta(days=1))

    plt.close()
    fig, host = plt.subplots()
    fig.set_size_inches(18, 6)
    fig.set_dpi(80)

    host.xaxis.set_major_formatter(mdates.DateFormatter("%y/%m/%d"))
    host.xaxis.set_minor_locator(mdates.MonthLocator())
    plt.title(f"Baidu Index")
    plt.grid(True)
    host.plot_date(dates, res, 'b-', linewidth=1)
    # plt.tight_layout()
    bytes = io.BytesIO()
    plt.savefig(bytes, format='png')
    plt.close()
    return bytes.getvalue()

def search_index(keywords: str) -> Union[bytes, str]:
    keyword_list = [[x for x in keywords.split(' ')]]
    try:
        keyword_list = get_clear_keywords_list(keyword_list)
        if not keyword_list:
            return "关键词未收录"
        bytes = grasp_search_index(keyword_list)
        return bytes
    except Exception as e:
        return f"发生错误：{repr(e)}"

if __name__ == "__main__":
    print(get_cookie_by_qr_login())
    # keywords_list = [
    #     ["的角度讲"], ["男方女方发广告"], ["张艺兴", "极限挑战"], ["你是大哥你牛"], ["英雄联盟"],
    #     ["永劫无间"], ["网易"], ["任正非"], ["企鹅"], ["北极熊"], ["疫情"], ["古装剧"]
    # ]
    # print(get_clear_keywords_list(keywords_list))
    # test_get_search_index(['博得之门'])
