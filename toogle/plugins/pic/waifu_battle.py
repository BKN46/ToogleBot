import math
import pickle
import random
import re
import uuid
from typing import Iterable, List, Tuple, Union


class Dice:
    @staticmethod
    def rd(maxium: int) -> int:
        res = random.randint(1, maxium)
        # print(f'd{maxium} = {res}')
        return res

    @staticmethod
    def psd(dice_str):
        if type(dice_str) == re.Match:
            dice_str = dice_str.group()
        num, sides = dice_str.split("d")
        if dice_str.endswith("kh") or dice_str.endswith("kl"):
            kh = True if sides.endswith("kh") else False
            sides = int(sides[:-2])
            if sides >= 10000:
                raise Exception("Exceed maximum dice sides")
            if num == "" or num == "1":
                num = 2
            elif int(num) > 10000:
                raise Exception("Exceed maximum dice num")
            if kh:
                return str(
                    max(
                        [
                            Dice.rd(int(sides))
                            for _ in range(int(num))
                        ]
                    )
                )
            else:
                return str(
                    min(
                        [
                            Dice.rd(int(sides))
                            for _ in range(int(num))
                        ]
                    )
                )
        else:
            if num == "":
                num = 1
            elif int(num) > 10000:
                raise Exception("Exceed maximum dice num")
            if int(sides) > 10000:
                raise Exception("Exceed maximum dice sides")
            return str(
                sum([Dice.rd(int(sides)) for _ in range(int(num))])
            )

    @staticmethod
    def roll_str(dice_str: str) -> int:
        while re.match(r"\d*d\d+", dice_str):
            dice_str = re.sub(r"(\d*)d(\d+)(kh|kl|)", Dice.psd, dice_str)
        return int(eval(dice_str))

    @staticmethod
    def roll(dice: Union[int, str], t=1):
        if type(dice) == int:
            return sum([random.randint(1, dice) for _ in range(t)])
        else:
            return sum([Dice.roll_str(dice) for _ in range(t)])


class CombatResource:
    def __init__(self, name: str, value=0) -> None:
        self.name = name
        self.value = value

    def __add__(self, other):
        return CombatResource(self.name, self.value + other.value)

    def __sub__(self, other):
        return CombatResource(self.name, self.value - other.value)


class CombatResourceGroup:
    def __init__(self, group=[]) -> None:
        self.group = group

    def __add__(self, other: Union[CombatResource, "CombatResourceGroup", None]):
        tmp = CombatResourceGroup(self.group)
        if other == None:
            return tmp
        elif type(other) == CombatResource:
            other = CombatResourceGroup([other])
        for resource in other:
            tmp[resource.name] = tmp[resource.name].value + resource.value
        return tmp

    def __sub__(self, other: Union[CombatResource, "CombatResourceGroup", None]):
        tmp = CombatResourceGroup(self.group)
        if other == None:
            return tmp
        elif type(other) == CombatResource:
            other = CombatResourceGroup([other])
        for resource in other:
            tmp[resource.name] = tmp[resource.name].value - resource.value
        return tmp

    def __contains__(self, item: Union[CombatResource, "CombatResourceGroup", None]):
        if item == None:
            return True
        elif type(item) == CombatResource:
            for resource in self.group:
                if resource.name == item.name and resource.value >= item.value:
                    return True
            return False
        else:
            for target in item.group:
                for resource in self.group:
                    if resource.name == target.name and resource.value >= target.value:
                        break
                else:
                    return False
            return True

    def __iter__(self) -> Iterable[CombatResource]:
        return iter(self.group)

    def __len__(self) -> int:
        return len(self.group)

    def __bool__(self) -> bool:
        return len(self.group) != 0

    def __getitem__(self, key: str) -> CombatResource:
        for resource in self.group:
            if resource.name == key:
                return resource
        return CombatResource(key, 0)

    def __setitem__(self, key: str, value: int) -> None:
        for resource in self.group:
            if resource.name == key:
                resource.value = value
                return
        self.group.append(CombatResource(key, value))

    def __str__(self) -> str:
        return ", ".join([f"{x.name}: {x.value}" for x in self])


class CombatDoing:
    name = ""

    def on_call(self):
        pass


class AttackMethod(CombatDoing):
    def __init__(
        self,
        name: str,
        main_chara: str,
        value: int,
        damage: str,
        saving: str,
        desc: str,
        using: Union[None, CombatResourceGroup, CombatResource],
        range=5,
        type="damage",
    ) -> None:
        self.name = name
        self.chara = main_chara
        self.value = value
        self.damage = damage
        self.saving = saving
        self.using = using
        self.range = range
        self.type = type
        self.desc = desc

weapon_list = [
    AttackMethod("赤手空拳", "STR", 0, "d4", "AC", "使用拳头击打", None),
    AttackMethod("火焰箭", "STR", 0, "d6", "DEX", "手中迸发出火焰形成箭矢，射出击中", None),
    AttackMethod("火球术", "STR", 0, "8d6", "DEX", "投射出一个巨大火团，烈焰包围", CombatResourceGroup(
        [
            CombatResource("三环", 1),
        ]
    )),
]

class DefendMethod(CombatDoing):
    def __init__(
        self, name: str, value: int, chara: str, saving: str, using: CombatResourceGroup
    ) -> None:
        self.name = name
        self.value = value
        self.chara = chara
        self.saving = saving
        self.using = using


class CombatCharacter:
    def __init__(
        self,
        name,
        hp,
        chara,
        resource=CombatResourceGroup(),
        attack_methods=[],
        defend_methods=[],
    ):
        self.name = name
        self.HP = hp
        self.STR, self.DEX, self.INT, self.CON, self.CHA, self.PER = chara
        self.resource = resource
        self.attack_methods = attack_methods
        self.defend_methods = defend_methods
        self.alive = hp > 0
        self.ai = CombatCharacter.AI(self)

    def attack(self, attack_method: AttackMethod):
        chara = self.__getattribute__(attack_method.chara)
        attack_dice = Dice.roll(20)
        attack_roll = (
            attack_dice + attack_method.value + CombatCharacter.get_modifier(chara)
        )
        damage_roll = Dice.roll(attack_method.damage) + max(0, CombatCharacter.get_modifier(
            chara
        ))
        if attack_dice == 20:
            attack_roll = 9999
            damage_roll += Dice.roll(attack_method.damage)
        self.resource -= attack_method.using
        return attack_roll, damage_roll

    def defend(self, saving: str):
        auto_defend_method = sorted(
            [
                x
                for x in self.defend_methods
                if x.saving == saving and x.using in self.resource
            ],
            key=lambda x: x.value,
            reverse=True,
        )
        if auto_defend_method:
            auto_defend_method = auto_defend_method[0]
            self.resource -= auto_defend_method.using
            if saving == "AC":
                return auto_defend_method.value
            else:
                return (
                    Dice.roll(20)
                    + CombatCharacter.get_modifier(self.__getattribute__(saving))
                    + auto_defend_method.value
                )
        elif saving == "AC":
            return 10 + CombatCharacter.get_modifier(self.DEX)
        else:
            return Dice.roll(20) + CombatCharacter.get_modifier(
                self.__getattribute__(saving)
            )

    def health_loss(self, value: int):
        if self.HP > value:
            self.HP -= value
        else:
            self.HP = 0
            self.death()
        return self.HP

    def get_initial(self) -> int:
        self.ai = CombatCharacter.AI(self)
        return Dice.roll(20) + CombatCharacter.get_modifier(self.DEX)

    def death(self):
        self.alive = False

    @staticmethod
    def get_random(
        name="",
        dice_num=3,
    ):
        if not name:
            name = str(uuid.uuid4())[:4]
        character = CombatCharacter(
            name,
            Dice.roll(6, t=4),
            [Dice.roll(6, t=dice_num) for _ in range(6)],
            attack_methods = weapon_list
        )
        character.HP = Dice.roll(f"d6+{CombatCharacter.get_modifier(character.CON)}", t=dice_num + 1)
        return character

    @staticmethod
    def get_modifier(chara):
        return int((chara - 10) / 2)

    def to_hex(self) -> str:
        return pickle.dumps(self).hex()

    @staticmethod
    def load_hex(hex):
        return pickle.loads(bytes.fromhex(hex))

    class AI:
        def __init__(self, character: "CombatCharacter", ai_type=None) -> None:
            self.character = character
            self.ai_type = ai_type

        def auto_select_attack(self, distance: int) -> Union[AttackMethod, None]:
            auto_attack_method = sorted(
                [
                    x
                    for x in self.character.attack_methods
                    if x.using in self.character.resource and distance < x.range
                ],
                key=lambda x: Dice.roll(x.damage)
                * (
                    10.5
                    + x.value
                    + CombatCharacter.get_modifier(
                        self.character.__getattribute__(x.chara)
                    )
                ),
                reverse=True,
            )
            if not auto_attack_method:
                return None
            if not self.ai_type:
                return random.choice(
                    [x for i, x in enumerate(auto_attack_method) if i < 3]
                )
            else:
                method_list = {
                    i: 2 if x.chara == self.ai_type else 1
                    for i, x in enumerate(auto_attack_method)
                }
                return auto_attack_method[CombatCharacter.AI.weight_random(method_list)]

        def auto_movement(
            self, turn_roll: List[Tuple[int, int, int, "CombatCharacter"]]
        ) -> int:
            return 0

        def select_target(
            self, turn_roll: List[Tuple[int, int, int, "CombatCharacter"]]
        ) -> Tuple[int, int, int, "CombatCharacter"]:
            tmp = random.randint(0, len(turn_roll) - 1)
            return turn_roll[tmp]

        @staticmethod
        def weight_random(random_list: dict):
            total = 0
            for k, v in random_list.items():
                total += float(v)
            res = random.random() * total
            for k, v in random_list.items():
                v = float(v)
                if res <= v:
                    return k
                else:
                    res -= v
            return random_list.keys()[0]


class Combat:
    def __init__(self, teams: List[List[CombatCharacter]]) -> None:
        self.teams = []
        self.logs = []
        self.turn_roll: List[Tuple[int, int, int, CombatCharacter]] = []
        position = random.randint(1, 30)
        for team_index, team in enumerate(teams):
            for character in team:
                initial = character.get_initial()
                self.turn_roll.append(
                    (initial, team_index, position, character)
                )
                self.log(f"{character.name} 的先攻：{initial}")
        self.turn_roll = sorted(self.turn_roll, key=lambda x: x[0], reverse=True)

    def log(self, msg: str):
        print(msg)
        self.logs.append(msg)

    def run(self, roll_limit=-1):
        while len(self.teams_remain()) > 1 and roll_limit != 0:
            roll_limit -= 1
            for index, data in enumerate(self.turn_roll):
                initial, team, position, character = data
                if not character.alive:
                    continue
                enemy_list = [ x for x in self.turn_roll if x[1] != team]

                # Move/Select target/Attack
                move = character.ai.auto_movement(enemy_list)
                if move > 0:
                    self.turn_roll[index] = (
                        self.turn_roll[index][0],
                        self.turn_roll[index][1],
                        self.turn_roll[index][2] + move,
                        self.turn_roll[index][3],
                    )
                target = character.ai.select_target(enemy_list)
                attack_method = character.ai.auto_select_attack(abs(target[2] - position))
                # Attack result
                if attack_method:
                    attack_throw, attack_damage = character.attack(attack_method)
                    defend_throw = target[3].defend(attack_method.saving)
                    self.log(f"{character.name} {attack_method.desc} {target[3].name}")
                    if attack_throw > defend_throw:
                        target[3].health_loss(attack_damage)
                        self.log(f"对 {target[3].name} 造成 {attack_damage} 点伤害")
                        if not target[3].alive:
                            self.log(f"{target[3].name} 失去意识")
                    else:
                        self.log(f"{character.name} 失手了")


    def teams_remain(self):
        alive_list = [x[1] for x in self.turn_roll if x[3].alive]
        return list(set(alive_list))


if __name__ == "__main__":
    tmp = CombatResourceGroup(
        [
            CombatResource("A", 1),
            CombatResource("B", 2),
        ]
    )
    tmp2 = CombatResourceGroup(
        [
            CombatResource("A", 2),
            CombatResource("B", 2),
        ]
    )
    # print(tmp2 in tmp)
    combat = Combat([
        [CombatCharacter.get_random(name="蒼崎 青子")],
        [CombatCharacter.get_random(name="蒼崎 橙子")]
    ])
    # tmp = pickle.dumps(combat).hex()
    # combat = pickle.loads(bytes.fromhex(tmp))
    combat.run()
