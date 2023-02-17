import os
import pickle
import random

import jieba.analyse
from tqdm import tqdm

from toogle.message import At, Image, Member, MessageChain, Plain, Quote
from toogle.message_handler import MessageHandler, MessagePack
from toogle.utils import create_path

create_path('data/markov')

MARKOV_DATA_PATH = "data/markov/"
MARKOV_SAVE = {
    f: pickle.load(open(MARKOV_DATA_PATH + f, "rb"))
    for f in os.listdir(MARKOV_DATA_PATH)
}


class ChatMarkov:
    class ContentNode:
        def __init__(self, tag, origin):
            self.tag = tag
            self.origin = [origin]
            self.next = {}

        def add_posfix(self, posfix):
            if posfix.tag in self.next:
                self.next[posfix.tag] += 1
            else:
                self.next[posfix.tag] = 1

        def get_next(self) -> str:
            total = sum(self.next.values())
            total = random.randint(1, total)
            for k in self.next:
                total -= self.next[k]
                if total <= 0:
                    return k
            return "[E]"

        def add_origin(self, origin):
            if origin not in self.origin:
                self.origin.append(origin)

    def __init__(self):
        self.root = {"[E]": self.ContentNode("[E]", "...")}
        self.last_node = self.root["[E]"]

    def add_next(self, posfix, posfix_origin):
        if posfix in self.root:
            current_node = self.root[posfix]
            current_node.add_origin(posfix_origin)
        else:
            current_node = self.ContentNode(posfix, posfix_origin)
            self.root[posfix] = current_node
        self.last_node.add_posfix(current_node)
        self.last_node = current_node

    def get_reply(self, tag):
        def get_next_origin(tag):
            return self.root[self.root[tag].get_next()].origin

        if tag in self.root:
            return get_next_origin(tag)
        else:
            return get_next_origin("[E]")


def data_clean(in_str):
    censor = ["xxxxxxxxxxx", "系统消息(10000)"]
    for c in censor:
        if c in in_str:
            return False
    return True


def line_clean(in_str):
    censor = ["@"]
    for c in censor:
        if c in in_str:
            return False
    return True


def line_replace(line):
    del_list = ["[图片]", "[表情]"]
    for d in del_list:
        line = line.replace(d, "")
    return line


def parse_qq_message(file_path):
    start_line = 10
    data = [
        "".join(line.split("\n")[1:])
        for line in tqdm(
            "\n".join(open(file_path, "r").readlines()[start_line:]).split("\n\n2"),
            desc=f"Parsing {file_path}:",
        )
        if data_clean(line)
    ]
    data = [
        line_replace(line)
        for line in data
        if len(line.replace("[图片]", "")) > 1 and line_clean(line)
    ]
    print(f"All data: {len(data)}")
    return data


def generate_markov_model(text_list):
    markov = ChatMarkov()
    for line in tqdm(text_list, desc="Generating markov model"):
        tags = jieba.analyse.extract_tags(line)
        tag = tags[0] if tags else "[E]"
        markov.add_next(tag, line)
    return markov


class Markov(MessageHandler):
    # markov = pickle.load(open("/root/repos/qqbot_graia/markov_save", "rb"))
    # white_list = True
    name = "对话机器人"
    trigger = r"^\s\s"
    readme = "基于马尔可夫链与隐含狄利克雷关系的垃圾话回答生成"

    async def ret(self, message: MessagePack) -> MessageChain:
        self.markov = MARKOV_SAVE.get(str(message.group.id))
        if not self.markov:
            raise Exception('No markov in this group')
        message_plain = message.message.asDisplay()
        return MessageChain.create(
            [Plain(Markov.get_reply(message_plain, self.markov))]
        )

    @staticmethod
    def get_reply(text, markov):
        debug = False
        if text.strip().startswith("`"):
            debug = True
            text = text.strip()[1:]

        text = jieba.analyse.extract_tags(text)
        if text:
            reply = markov.get_reply(text[0])
            print(text, reply[0])
            if debug:
                if text[0] not in markov.root:
                    return f"【回退逻辑】\n{random.choice(reply)}"
                return f"keyword: {text}\nnext: {markov.root[text[0]].next if len(markov.root[text[0]].next) <= 20 else '预选长度超过20'}\nlist: {reply if len(reply) <= 20 else '预选长度超过20'}\nres: {random.choice(reply)}"
        else:
            reply = markov.get_reply("[E]")
            print("[E]", reply[0])
            if debug:
                return f"【回退逻辑】\n{random.choice(reply)}"
        return random.choice(reply)

    @staticmethod
    def markov_learn(text, markov: ChatMarkov):
        tag = jieba.analyse.extract_tags(text)
        if tag:
            tag = tag[0]
        else:
            tag = "[E]"
        last = markov.last_node
        markov.add_next(tag, text)
        return {"last": last.tag, "tag": tag, "text": text}

    @staticmethod
    def markov_save(markov):
        with open("markov_save", "wb") as markov_f:
            pickle.dump(markov, markov_f)
