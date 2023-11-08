import os
import re
import subprocess
import sys
import time
import libtorrent
import requests

test_mag_link = "magnet:?xt=urn:btih:c9e15763f722f23e98a29decdfae341b98d53056&dn=Cosmos+Laundromat&tr=udp%3A%2F%2Fexplodie.org%3A6969&tr=udp%3A%2F%2Ftracker.coppersurfer.tk%3A6969&tr=udp%3A%2F%2Ftracker.empire-js.us%3A1337&tr=udp%3A%2F%2Ftracker.leechers-paradise.org%3A6969&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337&tr=wss%3A%2F%2Ftracker.btorrent.xyz&tr=wss%3A%2F%2Ftracker.fastcast.nz&tr=wss%3A%2F%2Ftracker.openwebtorrent.com&ws=https%3A%2F%2Fwebtorrent.io%2Ftorrents%2F&xs=https%3A%2F%2Fwebtorrent.io%2Ftorrents%2Fcosmos-laundromat.torrent"

torrent_dir = "data/magnet"

def parse_size(size):
    if size > 1024 * 1024 * 1024:
        return "%.2f GB" % (size / 1024 / 1024 / 1024)
    elif size > 1024 * 1024:
        return "%.2f MB" % (size / 1024 / 1024)
    elif size > 1024:
        return "%.2f KB" % (size / 1024)
    else:
        return "%d B" % size


def get_torrent(torrent_path, limit=10):
    info = libtorrent.torrent_info(torrent_path) # type: ignore
    res = []
    for f in info.files():
        res.append((f"[{parse_size(f.size)}]{f.path}", f.size))
    res = sorted(res, key=lambda x: x[1], reverse=True)
    return '\n'.join([x[0] for x in res[:limit]])


def mag2tor(magnet_link):
    cmd = f"webtorrent -p 3003 -o {torrent_dir} downloadmeta '{magnet_link}'"
    # p = subprocess.Popen(cmd, shell=True)
    p = subprocess.Popen(cmd, shell=True)
    for _ in range(10):
        time.sleep(1)
        if p.poll():
            break
    else:
        p.kill()
        return None
    return p.returncode


def parse_magnet(text, only_magnet=False):
    if only_magnet:
        regex = r"(magnet:\?xt=urn:[a-z0-9]+:[a-zA-Z0-9]+)"
    else:
        regex = r"(magnet:\?xt=urn:[a-z0-9]+:[a-zA-Z0-9].*)"
    for line in text.split("\n"):
        res = re.search(regex, line)
        if res:
            return res.group(1)
        

def do_magnet_parse(text):
    magnet_link = parse_magnet(text)
    now_torrent_list = [x for x in os.listdir(torrent_dir) if x.endswith(".torrent")]
    for torrent in now_torrent_list:
        os.remove(os.path.join(torrent_dir, torrent))
    if magnet_link:
        mag2tor(magnet_link)
        new_torrent_list = [x for x in os.listdir(torrent_dir) if x.endswith(".torrent")]
        if new_torrent_list:
            res = get_torrent(os.path.join(torrent_dir, new_torrent_list[0]))
            return f"磁链内容解析成功：\n{res}"
        return "解析磁链失败，可能以下原因导致：\n1. 服务器P2P网络问题\n2. 磁力链接无效"
    else:
        return "磁链不合法"
    

def do_magnet_preview(text):
    magnet_link = parse_magnet(text, only_magnet=True)
    url = f"https://whatslink.info/api/v1/link?url={magnet_link}"
    res = requests.get(url).json()
    if res['error']:
        return res['error']
    else:
        return res

    
if __name__ == "__main__":
    # print(mag2tor(test_mag_link))
    # get_torrent("magnet/test.torrent")
    # print(do_magnet_parse(test_mag_link))
    print(do_magnet_preview(test_mag_link))
