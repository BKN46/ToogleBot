import datetime
import json
import os
import re
import sys
import time

import thulac

self_path = os.path.dirname(os.path.abspath(__file__))
log_path = "../mirai/logs"
log_path = os.path.join(self_path, log_path)

def read_logs(start_time: datetime.datetime, end_time: datetime.datetime):
    all_logs = os.listdir(log_path)
    all_logs = list(sorted(all_logs))
    rec_time = time.time()
    for log_file in all_logs:
        log_day = datetime.datetime.strptime(log_file.split('.')[0], "%Y-%m-%d")
        if log_day < start_time or log_day > end_time:
            continue
        with open(os.path.join(log_path, log_file), "r") as f:
            print(f"Reading {log_file}")
            file_line_cnt = 0
            while True:
                line = f.readline()
                if not line:
                    break
                file_line_cnt += 1
                if '->' not in line:
                    continue
                if 'mirai:app' in line or '聊天记录' in line or 'http' in line:
                    continue
                chat_line = line.split('->')[1]
                chat_line = re.sub(r'\[.*\]', '', chat_line)
                chat_line = re.sub(r'\{.*\}', '', chat_line)
                chat_line = chat_line.strip()
                if not chat_line:
                    continue
                chat_info = re.findall(r'\(\d+\)', line)
                try:
                    group_id, member_id = chat_info[0][1:-1], chat_info[1][1:-1]
                except Exception as e:
                    continue
                yield chat_line, group_id, member_id
                if file_line_cnt % 1000 == 0:
                    use_time = (time.time() - rec_time) * 1000
                    rec_time = time.time()
                    print(f"Read {file_line_cnt} lines, use {use_time:.2f} ms")


def analysis(self_member_id, group_id_list):
    thu1 = thulac.thulac()
    # jieba.enable_parallel(2)
    # jieba.enable_paddle()

    start_time = datetime.datetime(2025, 1, 1)
    end_time = datetime.datetime(2025, 12, 1)
    word_stats = {}
    for line, group_id, member_id in read_logs(start_time, end_time):
        if member_id in [self_member_id]:
            continue
        if group_id not in group_id_list:
            continue
        for word, flag in thu1.cut(line):
            if flag not in ['v', 'i', 'j', 'x', 'y'] and not flag.startswith('n'):
                continue
            word = word.strip()
            if any([
                len(word) < 1,
                word.isdigit(),
                word.isascii() and len(word) < 2,
                word.encode('utf-8').isalpha() and len(word) < 2,
                ]):
                continue
            if word in word_stats:
                word_stats[word] += 1
            else:
                word_stats[word] = 1
    word_stats = sorted(word_stats.items(), key=lambda x: x[1], reverse=True)
    word_stats = dict(word_stats[:10000])
    print(json.dumps(word_stats, ensure_ascii=False, indent=4), file=open("res/word_stats.json", "w", encoding="utf-8"))


if __name__ == "__main__":
    analysis(sys.argv[1], sys.argv[2:])
