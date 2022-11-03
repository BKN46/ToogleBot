import time
import os
import threading
import pickle
from queue import Queue

from bs4 import BeautifulSoup
from thefuzz import process
from tqdm import tqdm

# from html2image import Html2Image

# hti = Html2Image(output_path='chm_jpg', size=(630,1800))

CHM_BASE_PATH = "chm/"
CHM_DATA = {}
FILE_QUEUE = Queue()


def item_name_parse(name):
    return name.replace(".html", "").replace("/", "-").replace("chm-", "")


def read_chm(path):
    global CHM_DATA, FILE_LIST
    if not path:
        path = CHM_BASE_PATH
    for item in os.listdir(path):
        item = f"{path}{item}"
        if os.path.isdir(item):
            read_chm(f"{item}/")
        elif item.endswith(".html"):
            item_name = item_name_parse(item)
            htmlfile = open(item, "r", encoding="gb2312", errors="ignore")
            htmlhandle = htmlfile.read()
            CHM_DATA[item_name] = BeautifulSoup(htmlhandle, "lxml").text
            # FILE_QUEUE.put(item)


# def queue_trans(q: Queue):
#     while not q.empty():
#         f = q.get()
#         item_name = item_name_parse(f)
#         hti.screenshot(html_file=f"{f}", save_as=f"{item_name}.jpg")
#         print(q.qsize())


def do_transition(q: Queue):
    thread_pool = []
    for i in range(6):
        t = threading.Thread(target=queue_trans, args=[q])
        t.start()
        thread_pool.append(t)

    for t in thread_pool:
        t.join()


# read_chm('')
CHM_LIST = pickle.load(open("chm.pickle", "rb"))
# CHM_LIST = []
# for k, v in CHM_DATA.items():
#     CHM_LIST.append({'title': k, 'content': v})
# open('chm.pickle', 'wb').write(pickle.dumps(CHM_LIST))
# do_transition(FILE_QUEUE)


def search_chm(text):
    res = process.extract(text, CHM_LIST, limit=10)
    res = "\n".join([x[0]["title"] for x in res])
    return (
        # f"没有匹配到具体法术，可能是:\n"
        f"{res}"
    )


if __name__ == "__main__":
    print(search_chm("剑咏"))
    # htmlfile = open(path, 'r', encoding='gb2312', errors='ignore')
    # htmlhandle = htmlfile.read()
    # soup = BeautifulSoup(htmlhandle, 'lxml')
    # print(soup.prettify())
