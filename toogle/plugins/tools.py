import datetime
import io
import math
import os
import re
import time
from typing import Optional, Union, no_type_check
from urllib.parse import urlencode

import bs4
import requests
import PIL.Image, PIL.ImageDraw, PIL.ImageFont
from matplotlib import pyplot as plt

from toogle.configs import config, proxies
from toogle.message import ForwardMessage, Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack, WaitCommandHandler
from toogle.nonebot2_adapter import bot_send_message
from toogle.plugins.compose.anime_calendar import save_anime_list
from toogle.plugins.compose.stock import get_search, get_stock_now, render_report
from toogle.plugins.others import baidu_index
from toogle.plugins.others.pcbench import get_compairison as get_pcbench_compairison
from toogle.plugins.others.weather import get_rainfall_graph
from toogle.utils import is_admin, modify_json_file


class StockReport(MessageHandler):
    name = "上市企业财报详情查询"
    trigger = r"^财报\s"
    thread_limit = True
    readme = "上市企业财报查询，包含A股、美股、港股"

    async def ret(self, message: MessagePack) -> MessageChain:
        search_content = message.message.asDisplay()[2:].strip()
        search_list = get_search(search_content)
        if len(search_list) == 0:
            return MessageChain.create([Plain("没有搜到对应 A股/港股/美股 上市公司")])
        elif len(search_list) > 1:
            res_text = f"存在多个匹配，请精确搜索:\n" + f"\n".join(
                [f"{x[2]} {x[1]}" for x in search_list]
            )
            return MessageChain.create([Plain(res_text)])
        else:
            img_bytes = render_report(search_list[0][0])
            return MessageChain.create([Image(bytes=img_bytes)])

class StockTrace(MessageHandler):
    name = "黄狗自选股"
    trigger = r"^自选股$|^添加自选股 |^删除自选股 "
    readme = "大黄狗股票快速查看\n可通过`添加自选股 [股票名称] [可选:成本价] [可选:持有股数]`添加自选股\n通过`删除自选股 [股票名称]`删除自选股"

    async def ret(self, message: MessagePack) -> MessageChain:
        message_content = message.message.asDisplay()

        with modify_json_file("stock") as f:
            stock_list = f.get(str(message.member.id), {
                '1.000001': {
                    'name': '上证指数',
                    'price': 0,
                    'hold': 0,
                },
            })

        if message_content == "自选股":
            stock_info = get_stock_now(list(stock_list.keys()))
            if isinstance(stock_info, str):
                return MessageChain.plain(stock_info, quote=message.as_quote())
            else:
                res = ""
                for k, v in stock_info.items():
                    base_ratio = 100 if k.startswith('1.') else 1000
                    res += f"{v['企业名']} {v['最新价']/base_ratio:<10.2f}{v['涨跌幅']/100:>7.2f}%"
                    if stock_list[k]['price'] and stock_list[k]['hold'] > 0:
                        total_earn = (v['最新价']/base_ratio - stock_list[k]['price']) * stock_list[k]['hold']
                        today_earn = v['涨跌额'] * stock_list[k]['hold'] / base_ratio
                        res += f" [收益]{int(total_earn)}/{int(today_earn)}\n"
                    else:
                        res += "\n"
                return MessageChain.plain(res, quote=message.as_quote())

        elif message_content.startswith("添加自选股"):
            search_name = message.message.asDisplay()[5:].strip()
            search_arr = search_name.split(' ')
            if len(search_arr) == 3:
                search_name = search_arr[0]
                stock_price = float(search_arr[1])
                stock_hold = float(search_arr[2])
            else:
                stock_price = 0
                stock_hold = 0

            search_list = get_search(search_name)

            if len(search_list) == 0:
                return MessageChain.plain("没有搜到对应 A股/港股/美股 上市公司", quote=message.as_quote())
            elif len(search_list) > 1:
                res_text = f"存在多个匹配，请精确搜索:\n" + f"\n".join(
                    [f"{x[2]} {x[4]}" for x in search_list]
                )
                return MessageChain.plain(res_text, quote=message.as_quote())
            else:
                with modify_json_file("stock") as f:
                    stock = search_list[0]
                    if str(message.member.id) not in f:
                        f[str(message.member.id)] = {
                            '1.000001': {
                                'name': '上证指数',
                                'price': 0,
                                'hold': 0,
                            }
                        }
                    f[str(message.member.id)][stock[3]] = {
                        'name': stock[4],
                        'price': stock_price,
                        'hold': stock_hold,
                    }
                return MessageChain.plain(f"成功添加自选股: {stock[4]}", quote=message.as_quote())
        elif message_content.startswith("删除自选股"):
            stock_name = message.message.asDisplay()[5:].strip()
            for k, v in stock_list.items():
                if v['name'] == stock_name:
                    with modify_json_file("stock") as f:
                        f[str(message.member.id)].pop(k)
                    return MessageChain.plain(f"成功删除自选股: {stock_name}", quote=message.as_quote())
            else:
                return MessageChain.plain(f"没有找到对应自选股: {stock_name}", quote=message.as_quote())
        return MessageChain.plain("指令错误", quote=message.as_quote())


class BaiduIndex(MessageHandler):
    name = "百度指数"
    trigger = r"^百度指数\s"
    thread_limit = True
    interval = 600
    readme = "百度指数查询" 

    async def ret(self, message: MessagePack) -> MessageChain:
        search_content = message.message.asDisplay()[4:].strip()
        res = baidu_index.search_index(search_content)
        if isinstance(res, bytes):
            return MessageChain.create([message.as_quote(), Image(bytes=res)])
        else:
            return MessageChain.create([message.as_quote(), Plain(str(res))])


class GetRainfallWeatherGraph(MessageHandler):
    name = "全国降水天气预告图"
    trigger = r"^全国降水$"
    thread_limit = True
    interval = 600
    readme = "全国降水天气预告图" 

    async def ret(self, message: MessagePack) -> MessageChain:
        rainfall = get_rainfall_graph()
        if isinstance(rainfall, bytes):
            return MessageChain.create([Image(bytes=rainfall)])
        else:
            return MessageChain.create([Plain(str(rainfall))])


class HealthCalculator(MessageHandler):
    name = "健康计算器"
    trigger = r"^(\d{1,3}岁)?(男|m|M|女|f|F)?(\d{1,3}\.?\d{0,3}cm)(\d{1,3}\.?\d{0,3}kg)$"
    thread_limit = True
    interval = 600
    readme = "健康计算器" 

    async def ret(self, message: MessagePack) -> Union[MessageChain, None]:
        message_content = message.message.asDisplay()
        re_match = re.match(self.trigger, message_content)
        if re_match:
            age, sex, height, weight = re_match.groups()
            age = float(age.replace('岁', '')) if age else 0
            sex_is_male = True if sex in ['男', 'm', 'M'] else False
            height = float(height[:-2])
            weight = float(weight[:-2])
        else:
            return

        res_str = ""

        bmi = weight / (height / 100) ** 2
        status = "偏瘦" if bmi < 18.5 else "正常" if bmi < 24 else "偏胖" if bmi < 28 else "肥胖"
        res_str += f"体重指数(BMI): {bmi:.3f} ({status})\n"

        if age:
            max_heartbeat_rate = 205.8 - 0.685 * age
            anaerobic_heartbeat_rate = max_heartbeat_rate * 0.85
            aerobic_heartbeat_rate = max_heartbeat_rate * 0.7
            res_str += f"最大心率: {max_heartbeat_rate:.1f}BPM\n"
            res_str += f"无氧运动心率: {anaerobic_heartbeat_rate:.1f}BPM\n"
            res_str += f"有氧运动心率: {aerobic_heartbeat_rate:.1f}BPM\n"

        if age and sex:
            bmr = 10 * weight + 6.25 * height - 5 * age + (5 if sex_is_male else 161)
            res_str += f"基础代谢率(BMR): {bmr:.2f}千卡/天\n"

            est_bodyfat_rate = 1.2 * bmi + 0.23 * age - 5.4 - (10.8 if sex_is_male else 0)
            res_str += f"估算体脂率: {est_bodyfat_rate:.2f}%\n"

        return MessageChain.plain(res_str)


class PCBenchCompare(MessageHandler):
    name = "PC硬件对比"
    trigger = r"^\.it (.*?)(vs|$)(.*?)$"
    thread_limit = True
    readme = "PC硬件对比" 

    async def ret(self, message: MessagePack) -> MessageChain:
        return MessageChain.plain(get_pcbench_compairison(message.message.asDisplay()))


class AnimeSchedule(MessageHandler):
    name = "当季新番"
    trigger = r"^当季新番$"
    thread_limit = True
    interval = 600
    readme = "查看当季新番，来源长门有C" 

    async def ret(self, message: MessagePack) -> MessageChain:
        try:
            pic_path = save_anime_list()
        except Exception as e:
            return MessageChain.plain(f"获取失败: {e}")
        return MessageChain.create([Image(path=pic_path)])


class AnimeDownloadSearch(MessageHandler):
    name = "动漫下载搜索"
    trigger = r"^动漫下载 (.*)"
    thread_limit = True
    interval = 10
    price = 5
    readme = "下载动漫，来源DMHY" 

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        search_content = message.message.asDisplay()[5:].strip()
        animes, url = AnimeDownloadSearch.search_anime(search_content)
        if not animes:
            return MessageChain.plain(f"没有找到资源:\n{url}")

        page, per_page = 0, 10
        def get_anime_page(page):
            start = page * per_page
            end = start + per_page
            anime_page = animes[start:end]
            if not anime_page:
                return MessageChain.plain(f'页数不正确! 范围({page+1}-{math.ceil(len(animes)/per_page)}')
            res = []
            for index, anime in enumerate(anime_page):
                title = anime['title']
                file_size = anime['file_size']
                res.append(f"【{index+1}】{title} [{file_size}]")
            return ForwardMessage.get_quick_forward_message([
                MessageChain.plain('\n'.join(res)),
                MessageChain.plain(f"页数[{page+1}/{math.ceil(len(animes)/per_page)}]\n使用'翻页[序号]'来翻页\n使用'下载[序号]'获取到磁链"),
                MessageChain.plain(url),
            ])

        bot_send_message(message, get_anime_page(page))

        further_instruction = r'^翻页|^下载'
        while True:
            waiter = WaitCommandHandler(message.group.id, message.member.id, further_instruction, timeout=120)
            res = await waiter.run()
            if res:
                instruct = res.message.asDisplay().strip()
                if instruct.startswith('翻页'):
                    try:
                        page = int(instruct[2:].strip()) - 1
                    except Exception as e:
                        bot_send_message(message, "页数不正确，请输入整数!")
                        continue
                    bot_send_message(message, get_anime_page(page))
                elif instruct.startswith('下载'):
                    try:
                        index = int(instruct[2:].strip())
                        download_res = animes[page * per_page + index - 1]
                    except Exception as e:
                        bot_send_message(message, "序号不正确!")
                        continue
                    res = ForwardMessage.get_quick_forward_message([
                        MessageChain.plain(f"{download_res['title']} [{download_res['file_size']}]"),
                        MessageChain.plain(download_res['url']),
                        MessageChain.plain(download_res['magnet']),
                    ])
                    bot_send_message(message, res)
                    break
            else:
                break


    @staticmethod
    @no_type_check
    def search_anime(search_content: str):
        page_url = f"https://share.dmhy.org/topics/list?keyword={search_content}&sort_id=2&team_id=0&order=date-desc"
        res = requests.get(page_url, proxies=proxies).text
        soup = bs4.BeautifulSoup(res, "html.parser")
        results = soup.find('tbody')
        if not results:
            return None, page_url
        else:
            results = results.findAll('tr', {'class': ''})
        res = []
        for line in results:
            title = line.find('td', {'class': 'title'}).find('a', {'target': '_blank'}).text.strip()
            url = line.find('td', {'class': 'title'}).find('a', {'target': '_blank'}).attrs['href']
            url = f"https://share.dmhy.org{url}"
            magnet = line.find('a', {'class': 'download-arrow arrow-magnet'}).attrs['href']
            file_size = line.findAll('td')[4].text
            res.append({
                'title': title,
                'magnet': magnet,
                'url': url,
                'file_size': file_size,
            })
        return res, page_url


class FilmDownloadSearch(MessageHandler):
    name = "影视下载搜索"
    trigger = r"^影视下载 (.*)"
    thread_limit = True
    interval = 10
    price = 5
    readme = "下载动漫，来源BT之家" 

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        search_content = message.message.asDisplay()[5:].strip()
        content = urlencode({"search": search_content}).split("=")[1].replace("%", "_")
        url = f"https://www.1lou.info/search-{content}-1.htm"
        res = requests.get(url).text
        soup = bs4.BeautifulSoup(res, "html.parser")
        search_res_raw = soup.findAll('li', {'class': 'media thread tap'})
        if not search_res_raw:
            return MessageChain.plain("没有找到资源", quote=message.as_quote())
        else:
            search_res = []
            for line in search_res_raw:
                title = line.text.strip().split("\n")[0]
                tags = []
                for tag in line.text.strip().split("\n")[1:]:
                    if tag:
                        tags.append(tag)
                    else:
                        break
                link = f"https://www.1lou.info/" + line.attrs.get("data-href", '没有链接')
                search_res.append(f"{title}\n{'/'.join(tags)}\n{link}")
        return ForwardMessage.get_quick_forward_message([ # type: ignore
            MessageChain.plain(message) for message in search_res
        ] + [MessageChain.plain(url)])


class DateCalculator(MessageHandler):
    name = "日期计算器"
    trigger = r"^(\d{1,4}年\d+月\d+日)到(\d{1,4}年\d+月\d+日)$"
    thread_limit = True
    # interval = 10
    readme = "日期计算器" 

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        content = message.message.asDisplay()
        re_match = re.match(self.trigger, content)
        if re_match:
            start_date, end_date = re_match.groups()
            start_date = datetime.datetime.strptime(start_date, "%Y年%m月%d日")
            end_date = datetime.datetime.strptime(end_date, "%Y年%m月%d日")
            delta = end_date - start_date
            return MessageChain.plain(f"{delta.days}天")
