import random
from typing import List, Optional

original_dice_table = {
    "11": "HOME_RUN",       # 全垒打
    "12": "DOUBLE",         # 二垒安打
    "13": "FLY_OUT",        # 外野接杀
    "14": "WALK",           # 保送
    "15": "POP_OUT",        # 内野接杀
    "16": "SINGLE",         # 一垒安打
    "22": "DOUBLE_PLAY",    # 双杀
    "23": "GROUND_OUT",     # 滚地球出局
    "24": "STRIKE_OUT",     # 三振
    "25": "SINGLE",         # 一垒安打
    "26": "STRIKE_OUT",     # 三振
    "33": "WALK",           # 保送
    "34": "TRIPLE",         # 三垒安打
    "35": "GROUND_OUT",     # 滚地球出局
    "36": "FLY_OUT",        # 外野接杀
    "44": "WALK",           # 保送
    "45": "POP_OUT",        # 内野接杀
    "46": "STRIKE_OUT",     # 三振
    "55": "DOUBLE",         # 二垒安打
    "56": "SACRIFICE_FLY",  # 牺牲高飞球
    "66": "HOME_RUN",       # 全垒打
}

default_dice_table = {
    "HOME_RUN": 20,
    "SINGLE": 20,
    "DOUBLE": 20,
    "TRIPLE": 10,
    "WALK": 30,
    "FLY_OUT": 20,
    "POP_OUT": 20,
    "GROUND_OUT": 20,
    "STRIKE_OUT": 30,
    "DOUBLE_PLAY": 10,
    "SACRIFICE_FLY": 10,
}

position_name = [
    "捕手",
    "一垒手",
    "二垒手",
    "游击手",
    "三垒手",
    "左外野",
    "中外野",
    "右外野",
    "投手",
]

famous_baseball_players = [
    "Mike Trout",
    "Shohei Ohtani",
    "Mookie Betts",
    "Francisco Lindor",
    "Fernando Tatis Jr.",
    "Juan Soto",
    "Ronald Acuña Jr.",
    "Jacob deGrom",
    "Gerrit Cole",
    "Shane Bieber",
    "Yu Darvish",
    "Clayton Kershaw",
    "Max Scherzer",
    "Justin Verlander",
    "Walker Buehler",
    "Trevor Bauer",
    "Stephen Strasburg",
    "Aaron Nola",
    "Suzuki Ichiro",
    "Hideki Matsui",
    "Hideo Nomo",
]

base_to_name = {
    0: "一垒",
    1: "二垒",
    2: "三垒",
}

class Player:
    def __init__(self, name, dice_table=default_dice_table):
        self.name = name
        self.dice_table: dict[str, int] = dice_table
        self.xp = 0
        self.level = 1
        self.statistics = {
            "AT_BAT": 0,
            "HIT": 0,
            "WALK": 0,
            "STRIKE_OUT": 0,
            "DOUBLE": 0,
            "TRIPLE": 0,
            "HOME_RUN": 0,
            "GROUND_OUT": 0,
            "FLY_OUT": 0,
            "POP_OUT": 0,
            "DOUBLE_PLAY": 0,
            "SACRIFICE_FLY": 0,
            
            "PICTH": 0,
            "HIT_BY_PITCH": 0,
            "HR_BY_PITCH": 0,
            "PITCH_WALK": 0,
            "PITCH_STRIKE": 0,
            "ER": 0,
        }

    def rec_stats(self, stats, num):
        self.statistics[stats] += num

    def roll(self):
        r = sorted([d6() for _ in range(2)])
        return f"{r[0]}{r[1]}"

    def original_play(self):
        return original_dice_table[self.roll()]

    def play(self):
        total_score = sum(self.dice_table.values())
        r = random.randint(1, total_score)
        for k, v in self.dice_table.items():
            r -= v
            if r <= 0:
                return k
        return "STRIKE_OUT"

    def get_xp(self, num):
        self.xp = self.xp + num
        level_xp = 10 * self.level
        if self.xp >= level_xp:
            self.xp = self.xp - level_xp
            self.level = self.level + 1

    @staticmethod
    def get_random_player(name):
        player = Player(name)
        for k, v in player.dice_table.items():
            player.dice_table[k] = max(v + random.randint(-int(v * 0.25), int(v * 0.25)), 8)
        return player

    @staticmethod
    def from_json(data):
        player = Player(data["name"])
        player.xp = data["xp"]
        player.level = data["level"]
        player.statistics = data["statistics"]
        return player

    def to_json(self):
        return {
            "name": self.name,
            "xp": self.xp,
            "level": self.level,
            "statistics": self.statistics
        }

    def get_data(self):
        hit = self.statistics["HIT"] + self.statistics["DOUBLE"] + self.statistics["TRIPLE"] + self.statistics["HOME_RUN"]
        hit_point = self.statistics["HIT"] + self.statistics["DOUBLE"] * 2 + self.statistics["TRIPLE"] * 3 + self.statistics["HOME_RUN"] * 4
        self.statistics["PICTH"] = self.statistics["PICTH"] or 1
        self.statistics["AT_BAT"] = self.statistics["AT_BAT"] or 1
        # 打击率
        s_ba = hit / self.statistics["AT_BAT"]
        # 上垒率
        s_obp = (hit + self.statistics["WALK"]) / (self.statistics["AT_BAT"] + self.statistics["WALK"] + self.statistics["SACRIFICE_FLY"])
        # 长打率
        s_slg = hit_point / self.statistics["AT_BAT"]
        # 打击指数
        s_ops = s_obp + s_slg
        # 防御率
        s_era = self.statistics["ER"] / self.statistics["PICTH"] * 9
        # K9
        s_k9 = self.statistics["PITCH_STRIKE"] / self.statistics["PICTH"] * 9
        # 被上垒率
        s_oba = (self.statistics["PITCH_WALK"] + self.statistics["HIT_BY_PITCH"]) / self.statistics["PICTH"]
        return (
            f"{self.name}"
            f"\n打数: {self.statistics['AT_BAT']} 打击率: {s_ba:.3f} 上垒率: {s_obp:.3f} 长打率: {s_slg:.3f} OPS: {s_ops:.3f}"
            f"\n投数: {self.statistics['PICTH']} 防御率: {s_era:.3f} K9: {s_k9:.3f} OBA: {s_oba:.3f}"
        )


class Team:
    def __init__(self, name) -> None:
        self.name = name
        # player size of ten
        self.players: List[Player] = []

    def add_player(self, player: Player):
        self.players.append(player)

    def team_balance(self):
        if len(self.players) < 9:
            for i in range(9 - len(self.players)):
                self.add_player(Player.get_random_player(f"{self.name} 代打{i}"))
        elif len(self.players) > 9:
            random.shuffle(self.players)
            self.players = self.players[:9]
            random.shuffle(self.players)
    
    def show(self):
        res = f"{self.name}\n"
        for i, player in enumerate(self.players):
            if i > 8:
                res += f"[代打{i-9}] {player.name}\n"
            res += f"[{position_name[i]}] {player.name}\n"
        return res

    @staticmethod
    def get_random_team():
        team = Team("全明星")
        names = random.sample(famous_baseball_players, 9)
        for i in range(9):
            team.add_player(Player.get_random_player(names[i]))
        return team


class Game:
    def __init__(self, team1: Team, team2: Team) -> None:
        self.teams = [team1, team2]
        self.atk_t, self.def_t = 0, 1
        self.score = [[0], [0]]
        self.bat_seq = [0, 0]
        self.base: List[Optional[Player]] = [None, None, None]

        self.round = 0
        self.turn_out = 0

        self.logs = []

    def swap_defense(self):
        self.atk_t, self.def_t = (self.atk_t + 1) % 2, (self.def_t + 1) % 2
        self.base = [None, None, None]

    def next_round(self):
        self.round += 1
        self.score[0].append(0)
        self.score[1].append(0)

    def push(self, num, player=None):
        pitcher = self.teams[self.def_t].players[-1]
        if num == 4:
            self.score[self.atk_t][-1] += 1
            for i in self.base:
                if i:
                    self.score[self.atk_t][-1] += 1
                    pitcher.rec_stats("ER", 1)
            self.base = [None, None, None]
            return

        for i in range(2, 2-num, -1):
            if self.base[i]:
                self.log(f"{self.base[i].name} 返回本垒得分") # type: ignore
                self.base[i] = None
                self.score[self.atk_t][-1] += 1
                pitcher.rec_stats("ER", 1)
        for i in [1, 0]:
            if self.base[i]:
                self.base[i+num] = self.base[i]
                self.base[i] = None
        self.base[num-1] = player

    def log(self, *msg):
        self.logs.append(random.choice(msg))

    def game(self):
        for _ in range(9):
            for _ in range(2):
                self.turn_out = 0
                while self.turn_out < 3:
                    batter = self.teams[self.atk_t].players[self.bat_seq[self.atk_t]]
                    pitcher = self.teams[self.def_t].players[-1]
                    self.bat_seq[self.atk_t] = (self.bat_seq[self.atk_t] + 1) % 9
                    self.turn(batter, pitcher)
                    yield 'turn'
                self.swap_defense()
            self.next_round()
            yield 'round'
        if sum(self.score[0]) == sum(self.score[1]):
            while True:
                for _ in range(2):
                    self.turn_out = 0
                    while self.turn_out < 3:
                        batter = self.teams[self.atk_t].players[self.bat_seq[self.atk_t]]
                        pitcher = self.teams[self.def_t].players[-1]
                        self.bat_seq[self.atk_t] = (self.bat_seq[self.atk_t] + 1) % 9
                        self.turn(batter, pitcher)
                        yield 'turn'
                    self.swap_defense()
                if sum(self.score[0]) != sum(self.score[1]):
                    break
                self.next_round()
                yield 'round'
        self.log(f"比赛结束, {self.teams[0].name} {sum(self.score[0])} : {sum(self.score[1])} {self.teams[1].name}")


    def turn(self, batter: Player, pitcher: Player):
        batter.rec_stats("AT_BAT", 1)
        pitcher.rec_stats("PICTH", 1)
        batter.get_xp(1)
        pitcher.get_xp(1)
        play = batter.play()
        if play == "WALK":
            self.push(1, batter)
            self.log(f"{batter.name} 被四坏球保送上垒")
            batter.rec_stats("WALK", 1)
            pitcher.rec_stats("PITCH_WALK", 1)
            batter.get_xp(1)
        elif play == "STRIKE_OUT":
            self.turn_out += 1
            self.log(f"{batter.name} 被三振出局")
            batter.rec_stats("STRIKE_OUT", 1)
            pitcher.rec_stats("PITCH_STRIKE", 1)
            pitcher.get_xp(3)
        elif play == "DOUBLE":
            self.push(2, batter)
            self.log(f"{batter.name} 打出二垒安打")
            batter.rec_stats("DOUBLE", 1)
            pitcher.rec_stats("HIT_BY_PITCH", 1)
            batter.get_xp(2)
        elif play == "TRIPLE":
            self.push(3, batter)
            self.log(f"{batter.name} 打出三垒安打")
            batter.rec_stats("TRIPLE", 1)
            pitcher.rec_stats("HIT_BY_PITCH", 1)
            batter.get_xp(3)
        elif play == "HOME_RUN":
            self.push(4, batter)
            self.log(f"{batter.name} 打出本垒打！！！")
            batter.rec_stats("HOME_RUN", 1)
            pitcher.rec_stats("HIT_BY_PITCH", 1)
            pitcher.rec_stats("HR_BY_PITCH", 1)
            pitcher.rec_stats("ER", 1)
            batter.get_xp(5)
        elif play == "GROUND_OUT":
            self.turn_out += 1
            self.log(f"{batter.name} 打出滚地球被截杀出局")
            batter.rec_stats("GROUND_OUT", 1)
            pitcher.get_xp(1)
        elif play == "FLY_OUT":
            self.turn_out += 1
            self.log(f"{batter.name} 击球被外野接杀出局")
            batter.rec_stats("FLY_OUT", 1)
            pitcher.get_xp(1)
        elif play == "POP_OUT":
            self.turn_out += 1
            self.log(f"{batter.name} 打出高飞球被接杀出局")
            batter.rec_stats("POP_OUT", 1)
            pitcher.get_xp(1)
        elif play == "DOUBLE_PLAY":
            for i in range(2, -1, -1):
                if self.base[i]:
                    self.turn_out += 2
                    self.base[i] = None
                    self.log(f"{batter.name} 击球被内野接住、同时双杀{base_to_name[i]}出局")
                    batter.rec_stats("DOUBLE_PLAY", 1)
                    pitcher.get_xp(5)
                    break
            else:
                self.turn_out += 1
                self.log(f"{batter.name} 击球被内野接杀出局")
                batter.rec_stats("FLY_OUT", 1)
                pitcher.get_xp(1)
        elif play == "SINGLE":
            self.push(1, batter)
            self.log(f"{batter.name} 打出一垒安打")
            batter.rec_stats("HIT", 1)
            pitcher.rec_stats("HIT_BY_PITCH", 1)
            batter.get_xp(1)
        elif play == "SACRIFICE_FLY":
            for i in range(2, -1, -1):
                if self.base[i]:
                    self.turn_out += 1
                    self.log(f"{batter.name} 打出牺牲高飞球")
                    batter.rec_stats("DOUBLE_PLAY", 1)
                    self.push(1, batter)
                    self.base[0] = None
                    batter.get_xp(1)
                    break
            else:
                self.turn_out += 1
                self.log(f"{batter.name} 打出高飞球被接杀出局")
                batter.rec_stats("FLY_OUT", 1)
                pitcher.get_xp(1)
        else:
            self.log(f"{batter.name} 击球无效: {play}")


    def now_turn(self):
        upper = "上半" if self.atk_t == 0 else "下半"
        return f"{self.round+1}局{upper}\n{self.teams[0].name} {sum(self.score[0])} : {sum(self.score[1])} {self.teams[1].name}"

    def show(self):
        upper = "上半" if self.atk_t == 0 else "下半"
        return (
            f"{self.teams[0].name} {sum(self.score[0])} : {sum(self.score[1])} {self.teams[1].name}"
            f"\n{self.round+1}局{upper} - {self.turn_out}出局"
            f"\n    {'■' if self.base[1] else '□'}\n"
            f"   /   \\\n"
            f"{'■' if self.base[2] else '□'}     {'■' if self.base[0] else '□'}"
        )


def d6():
    return random.randint(1, 6)


if __name__ == "__main__":
    # teams = [Team("A"), Team("B")]
    # for i in range(9):
    #     teams[0].add_player(Player(f"A{i}"))
    #     teams[1].add_player(Player(f"B{i}"))
    teams = [Team.get_random_team(), Team.get_random_team()]
    game = Game(
        teams[0],
        teams[1]
    )
    for turn in game.game():
        if turn == 'round':
            print("\nTURN!\n" + game.now_turn())
        elif turn == 'turn':
            print(game.show())
            print('\n'.join(game.logs))
            game.logs.clear()
            print('-=*=-'*10)
    
    # print('\n'.join(game.logs))
    # for i in range(2):
    #     print(f"{teams[i].name} 统计")
    #     for player in teams[i].players:
    #         print(player.get_data())
    #     print('-=*=-'*10)
