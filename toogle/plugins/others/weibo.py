import datetime
import json
import random
import time

import requests

headers = {
    'Referer': 'https://weibo.com/',
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
    'cache-control': 'max-age=0',
    'priority': 'u=0, i',
    'sec-ch-ua': '"Chromium";v="136", "Microsoft Edge";v="136", "Not.A/Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0',
    'x-xsrf-token': 'Wm2CiDPVTAgrYOYHlcTtw5jZ',
}

def get_xsrf_token():
    url = "https://weibo.com/u/1855501681"
    req = requests.get(url, headers={
        **headers,
        'upgrade-insecure-requests': '1',
    })
    return req

def get_tid():
    """
    获取tid,c,w
    :return:tid
    """
    tid_url = "https://passport.weibo.com/visitor/genvisitor"
    data = {
        "cb": "gen_callback",
        "fp": {
            "os": "3",
            "browser": "Chrome69,0,3497,100",
            "fonts": "undefined",
            "screenInfo": "1920*1080*24",
            "plugins": "Portable Document Format::internal-pdf-viewer::Chrome PDF Plugin|::mhjfbmdgcfjbbpaeojofohoefgiehjai::Chrome PDF Viewer|::internal-nacl-plugin::Native Client"
        }
    }
    req = requests.post(url=tid_url, data=data, headers=headers)
    if req.status_code == 200:
        ret = eval(req.text.replace("window.gen_callback && gen_callback(", "").replace(");", "").replace("true", "1"))
        return ret.get('data').get('tid')
    return None


def read_cache_cookie():
    cookie = open('./data/weibo_cookie', 'r').read().strip()
    headers.update({
        'Cookie': cookie,
    })
    sub = cookie.split('SUB=')[1].split(';')[0]
    subp = cookie.split('SUBP=')[1].split(';')[0]
    return sub, subp


def get_cookie(use_cache=True):
    if use_cache:
        return read_cache_cookie()
    tid = get_tid()
    if not tid:
        return None
    cookies = {
        "tid": tid + "__095" # + tid_c_w[1]
    }
    url = f"https://passport.weibo.com/visitor/visitor?a=incarnate&t={tid}&w=2&c=095&gc=&cb=cross_domain&from=weibo&_rand={random.random()}"
    req = requests.get(url, cookies=cookies, headers=headers)
    if req.status_code != 200:
        return None
    ret = eval(req.text.replace("window.cross_domain && cross_domain(", "").replace(");", "").replace("null", "1"))
    try:
        sub = ret['data']['sub']
        if sub == 1:
            return None
        subp = ret['data']['subp']
    except KeyError:
        return None
    headers.update({
        'Cookie': f"SUB={sub}; SUBP={subp}; XSRF-TOKEN={headers['x-xsrf-token']};"
    })
    return sub, subp


def get_web_page(uid, page=1, feature=0):
    url = f"https://weibo.com/ajax/statuses/mymblog?uid={uid}&page={page}&feature={feature}"
    cookie = get_cookie()
    if not cookie:
        return None
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        raise Exception("鉴权失败")
    return res.json()


def get_save_old_otaku(json_dict={}, time_limit=0.0, bearable_time=60.0):
    if not json_dict:
        json_dict = get_web_page(1855501681)
        if not json_dict:
            return []
    res = []
    if json_dict.get('error'):
        return []
    for msg in json_dict['data']['list']:
        create_time = datetime.datetime.strptime(msg['created_at'], "%a %b %d %H:%M:%S %z %Y")
        if create_time.timestamp() < time_limit - bearable_time:
            continue
        msg_raw = msg['text_raw'].replace("\\n", "\n").replace("\u200b", "")
        if not '求脱单' in msg_raw:
            continue
        key_info = msg_raw.split("\n")[1]
        if 'pic_infos' in msg:
            pic_url_list = [v['original']['url'] for k, v in msg['pic_infos'].items()]
        else:
            pic_url_list = [
                item['data']['original']['url']
                for item in msg['mix_media_info']['items']
                if item['type'] == 'pic'
            ]
        detail_page = f"https://weibo.com/{msg['user']['id']}/{msg['mblogid']}#comment"
        comments = get_comments(msg['user']['id'], msg['id'])
        res.append((create_time, msg_raw, pic_url_list, detail_page, comments, key_info))
    return res


def get_comments(user_id, comment_id, limit=5, refresh_cookie=False, time_order=False):
    time_order = 'flow=1&' if time_order else ''
    url = f'https://weibo.com/ajax/statuses/buildComments?{time_order}is_reload=1&id={comment_id}&is_show_bulletin=2&is_mix=0&count=20&uid={user_id}&fetch_level=0&locale=zh-CN'
    if refresh_cookie:
        cookie = get_cookie()
        if not cookie:
            return 0, ['获取cookie失败']
    res = requests.get(url, headers=headers).json()
    total_number = res['total_number']
    msg = [f"{x['text_raw']} [{x['like_counts']}点赞][{x['source']}]" for x in res['data'][:limit]]
    return total_number, msg


if __name__ == "__main__":
    res = get_save_old_otaku(time_limit=time.time() - 3600 * 12)
    print(res[0])
    pass

