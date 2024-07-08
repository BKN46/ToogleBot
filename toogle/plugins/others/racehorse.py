import io
import random
import time
from typing import List, Union

from matplotlib import pyplot as plt
import PIL.Image, PIL.ImageDraw, PIL.ImageFont

FONT_PATH = "toogle/plugins/compose/fonts/Arial Unicode MS Font.ttf"
FONT = PIL.ImageFont.truetype(FONT_PATH, 20)


class Horse:
    def __init__(self, name, score, category, surface, form) -> None:
        self.name = name
        self.score = score
        # E/L/I/M/S
        self.category = category
        # Track/Dirt
        self.surface = surface
        self.form = form
        self.logs = []

    def race_init(self, race_length, race_type):
        self.speed = self.score + random.randint(-5, 5)

        if race_type != self.surface:
            self.speed *= 0.95

        length_seq = "ELIMS"
        length_index = length_seq.index(self.category)
        race_length_index = length_seq.index(race_length)
        self.speed *= length_index * 0.02 + 1

        self.distance = 0
        self.stamina = 100
        # idle/dash/save/finish
        self.state = "idle"
        self.finish = False

    def log(self, text):
        self.logs.append(text)

    def run(self, infront: Union["Horse", None], behind: Union["Horse", None], race_length: int):
        if race_length - self.distance <= self.speed * 3:
            if self.state != "finish":
                self.log(f"{self.name} 开始了最终冲刺")
            self.state = "finish"
        elif infront and infront.distance - self.distance <= self.speed:
            if self.state != "dash":
                self.log(f"{self.name} 准备超越 {infront.name}")
            self.state = "dash"
        elif infront and infront.distance - self.distance <= self.speed * 3 and random.random() < 0.2:
            if self.state != "dash":
                self.log(f"{self.name} 向身前的 {infront.name} 开始了冲刺")
            self.state = "dash"
        elif behind and self.distance - behind.distance >= 100 and random.random() < 0.5:
            if self.state != "save":
                self.log(f"{self.name} 慢了下来！")
            self.state = "save"
        elif infront and self.state == "dash" and infront.distance - self.distance > self.speed:
            self.state = "idle"

        if self.stamina <= 0 and not self.state == "finish":
            if  self.state != "save":
                self.log(f"{self.name} 开始体力不支了")
            self.state = "save"
            self.speed = self.speed * 0.95
        elif self.stamina <= 20 and random.random() < 0.2:
            self.speed = self.speed * 0.95
        elif self.stamina <= 50 and random.random() < 0.1:
            self.speed = self.speed * 0.95
        elif self.stamina <= 70 and random.random() < 0.05:
            self.speed = self.speed * 0.98

        if self.state == "dash":
            self.distance += self.speed + random.randint(-5, 17)
            self.stamina -= 10
        elif self.state == "idle":
            self.distance += self.speed + random.randint(-10, 10)
            self.stamina -= 5
        elif self.state == "save":
            self.distance += self.speed * 0.9
            self.stamina -= 2
        elif self.state == "finish":
            self.distance += self.speed * 1.2 + random.randint(-2, 15)
            self.stamina -= 15

        if self.distance >= race_length:
            self.finish = True
            return True

        if self.category == "E":
            self.stamina += 5
        elif self.category == "L":
            self.stamina += 4
        elif self.category == "I":
            self.stamina += 2
        elif self.category == "M":
            self.stamina += 1
        elif self.category == "S":
            self.stamina += 0
        return False


class Race:
    def __init__(self, name, category, surface, form) -> None:
        self.name = name
        # E/L/I/M/S
        self.category = category
        # Track/Dirt
        self.surface = surface
        self.form = form

    def get_race_length(self):
        if self.category == "E":
            return 2000
        elif self.category == "L":
            return 1800
        elif self.category == "I":
            return 1500
        elif self.category == "M":
            return 1200
        elif self.category == "S":
            return 800
        return 1500


horses_data = [
    Horse("春秋分", 129, "L", "T", "日本"),
    Horse("金枪十六", 125, "M", "T", "香港"),
    Horse("金钻贵人", 124, "S", "T", "香港"),
    Horse("领衔", 124, "L", "T", "日本"),
    Horse("浪漫勇士", 123, "M", "T", "香港"),
    Horse("加州星球", 122, "M", "T", "香港"),
    Horse("誉满迪拜", 122, "I", "T", "英国"),
    Horse("盈宝奇狱", 122, "I", "D", "日本"),
    Horse("Art Collector", 121, "M", "D", "美国"),
    Horse("胜愿", 121, "S", "T", "澳大利亚"),
    Horse("瞄准", 121, "I", "T", "英国"),
    Horse("礼物", 120, "M", "T", "澳大利亚"),
    Horse("胜局在望", 120, "L", "T", "日本"),
    Horse("尖子", 120, "S", "D", "美国"),
    Horse("猛击", 120, "M", "T", "澳大利亚"),
    Horse("鲜红叶", 120, "I", "T", "法国"),
    Horse("诺斯勋爵", 120, "M", "T", "英国"),
    Horse("争胜者", 120, "M", "T", "英国"),
    Horse("本初之海", 120, "M", "D", "日本"),
    Horse("初日高升", 120, "I", "T", "日本"),
    Horse("Up To The Mask", 120, "M", "T", "美国"),
    Horse("韦氏", 120, "L", "T", "英国"),
    Horse("斗士", 119, "M", "T", "澳大利亚"),
    Horse("新王朝", 119, "M", "T", "英国"),
    Horse("Cody's Wish", 119, "S", "D", "美国"),
    Horse("一战成名", 119, "M", "D", "美国"),
    Horse("野田猛鲸", 119, "M", "T", "日本"),
    Horse("飓风莱恩", 119, "L", "T", "英国"),
    Horse("骏天宫", 119, "E", "T", "日本"),
    Horse("Mage", 119, "I", "D", "美国"),
    Horse("探查", 119, "S", "T", "澳大利亚"),
    Horse("West Will Power", 119, "M", "D", "美国"),

    Horse("特别周", 120, "L", "T", "日本"),
    Horse("丸善斯基", 120, "M", "T", "日本"),
    Horse("东海帝皇", 120, "I", "T", "日本"),
    Horse("无声铃鹿", 120, "M", "T", "日本"),
    Horse("小栗帽", 120, "I", "T", "日本"),
    Horse("大和赤骥", 120, "I", "T", "日本"),
    Horse("大树快车", 120, "S", "T", "日本"),
    Horse("目白麦昆", 120, "L", "T", "日本"),
    Horse("神鹰", 120, "M", "D", "日本"),
    Horse("鲁道夫象征", 120, "E", "D", "日本"),
    Horse("美浦波旁", 120, "I", "D", "日本"),
    Horse("米浴", 120, "E", "D", "日本"),
    Horse("春乌拉拉", 120, "S", "D", "日本"),
]


races_data = [
    Race("二月锦标", "M", "D", "日本"),
    Race("大阪杯", "L", "T", "日本"),
    Race("皋月赏", "I", "T", "日本"),
    Race("樱花赏", "M", "T", "日本"),
    Race("东京优骏", "L", "T", "日本"),
    Race("菊花赏", "L", "T", "日本"),
    Race("日本杯", "L", "T", "日本"),
    Race("秋季天皇赏", "I", "T", "日本"),
    Race("有马纪念赛", "L", "T", "日本"),
    Race("春季天皇赏", "E", "T", "日本"),
    Race("日本冠军杯", "I", "D", "日本"),
    Race("香港短途锦标", "S", "T", "香港"),
    Race("马会短途锦标", "S", "T", "香港"),
    Race("香港一哩锦标", "M", "T", "香港"),
    Race("香港杯", "M", "T", "香港"),
    Race("香港瓶", "L", "T", "香港"),
    Race("英皇佐治六世及皇后伊利沙伯锦标", "L", "T", "英国"),
    Race("二千坚尼锦标", "M", "T", "英国"),
    Race("冠军锦标", "M", "T", "英国"),
    Race("凯旋门大赛", "L", "T", "法国"),
    Race("墨尔本杯", "L", "T", "澳大利亚"),
    Race("迪拜世界杯", "I", "D", "阿联酋"),
]


def init_race():
    race = random.choice(races_data)
    horses = random.sample(horses_data, 8)
    return race, horses

def do_race(race: Race, horses: List[Horse], sleep_interval = 1):
    for horse in horses:
        horse.race_init(race.category, race.surface)

    race_length = race.get_race_length()

    horses_rank = sorted(horses, key=lambda horse: horse.speed, reverse=True)

    motd = (
        f"欢迎来到位于{race.form}的{race.name}({race.category}/{race.surface})\n"
        f"本场参赛马匹有:\n" + "\n".join([f"{horse.name} ({horse.form})" for horse in horses]) +
        f"\n\n目前看今天状态最好的是: {horses_rank[0].name}\n让我们准备好比赛开始吧"
    )
    yield motd

    # time.sleep(1)
    # for i in range(3,0,-1):
    #     yield f"{i}..."
    #     time.sleep(1)
    # yield "GO!"

    final_res = []

    race_round = 0

    horse_history = {horse.name: [0] for horse in horses}

    while horses:
        race_round +=1
        round_output = []
        horses_rank = sorted(horses, key=lambda horse: horse.distance, reverse=True)

        for rank, horse in enumerate(horses_rank):
            infront = horses_rank[rank-1] if rank > 0 else None
            behind = horses_rank[rank+1] if rank < len(horses)-1 else None
            
            if not horse.finish:
                horse.run(infront, behind, race_length)

            round_output += horse.logs if random.random() < 0.5 else []
            horse.logs = []

        re_rank = sorted(horses, key=lambda horse: horse.distance, reverse=True)
        for rank, horse in enumerate(re_rank):
            old_rank = horses_rank.index(horse)
            if rank < old_rank:
                round_output.append(f"{horse.name} 超越了 {re_rank[rank+1].name}")

            if horse.finish:
                round_output.append(f"{horse.name} 完成了比赛")
                horse.distance = min(horse.distance, race.get_race_length())
                horses.remove(horse)
                final_res.append(horse)


        if race_round == 2:
            round_output.append(
                f"比赛开局前五位排名是:\n"
                + "\n".join([f"{rank+1}. {horse.name} ({horse.distance:.2f}m)" for rank, horse in enumerate(re_rank[:5])])
            )
        elif race_round % 5 == 0:
            round_output.append(
                f"比赛已经进行了一段时间，目前未完赛的前五位排名是:\n"
                + "\n".join([f"{rank+1}. {horse.name} ({horse.distance:.2f}m)" for rank, horse in enumerate(re_rank[:5])])
            )

        horse_history = {horse.name: horse_history[horse.name] + [horse.distance] for horse in final_res + horses}
        plt.figure(figsize=(6, 6))
        plt.rcParams['font.sans-serif'] = ["Arial Unicode MS"]
        for horse_name, history in horse_history.items():
            plt.plot(history, label=horse_name)
        plt.xlabel("Time")
        plt.ylabel("Distance")
        plt.legend(loc="best")
        pic_buf = io.BytesIO()
        plt.savefig(pic_buf, format="png")
        plt.close()
        graph_pic = PIL.Image.open(pic_buf)

        if round_output:
            draw_text = "\n".join(round_output)
        else:
            draw_text = f"比赛进行中... 目前领先的是: {horses_rank[0].name}"
        text_height = FONT.getbbox(draw_text)[3] * len(draw_text.split("\n"))     
        pic = PIL.Image.new("RGBA", (graph_pic.width, graph_pic.height + text_height + 20), (255, 255, 255, 255))
        draw = PIL.ImageDraw.Draw(pic)
        draw.text((10, 10), draw_text, font=FONT, fill=(0, 0, 0, 255))
        pic.paste(graph_pic, (0, text_height + 20))

        pic_buf = io.BytesIO()
        pic.save(pic_buf, format="png")
        yield pic_buf.getvalue()

        time.sleep(sleep_interval)

    yield (
        f"比赛结束\n🥇{final_res[0].name}\n"
        f"🥈{final_res[1].name}\n"
        f"🥉{final_res[2].name}\n"
        f"余下的参与者:\n" + "\n".join([f"{rank + 4}. {horse.name}" for rank, horse in enumerate(final_res[3:])])
    )

def main():
    race, horses = init_race()
    for index, i in enumerate(do_race(race, horses)):
        if isinstance(i, str):
            print(i)
            print("-"*20)
        elif isinstance(i, bytes):
            with open(f"data/test/{index}.png", "wb") as f:
                f.write(i)
