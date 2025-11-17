import json
import math
import random
import uuid
from typing import Any

# print(wbdata.get_country())
raw_csv = open("toogle/plugins/remake/remake_data.csv", "r").readlines()
header = raw_csv[0].replace("\n", "").split(",")
data = [
    {header[i]: v for i, v in enumerate(x.replace("\n", "").split(","))}
    for x in raw_csv[1:]
    if not x.split(",")[1]
]
continent_data = json.loads(
    open("toogle/plugins/remake/continent_skin.json", "r").read()
)

# overall_data
world_new_population = 0
for line in data:
    if all(
        [
            line.get("人口"),
            line.get("千人生育率"),
        ]
    ):
        world_new_population += int(float(line["人口"]) * float(line["千人生育率"]))


nation_rank = {
    "高收入国家": 4,
    "中高等收入国家": 3,
    "中低等收入国家": 2,
    "低收入国家": 1,
    "未分类国家": 2,
}


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


def get_random():
    rand_nation = random.randint(0, world_new_population - 1)

    for line in data:
        if all(
            [
                line.get("人口"),
                line.get("千人生育率"),
            ]
        ):
            remake_poss = int(float(line["人口"]) * float(line["千人生育率"]))
            if rand_nation <= remake_poss:
                return line, remake_poss / world_new_population
            else:
                rand_nation -= remake_poss
    return {}, 0


def nation_parse(name, out_seed):
    IS_POOR = False
    p_res = {
        "name": name,
    }
    game_data = {}
    score = 100
    if out_seed:
        seed = out_seed
    else:
        seed = str(uuid.uuid4())
    random.seed(seed)
    nation_line, p_res["possibility"] = get_random()
    p_res["nation"] = nation_line["国家"]
    game_data["nation"] = nation_line["国家代码"]
    if out_seed:
        res = [f"#{seed}的结果是\nremake在了{nation_line['国家']}"]
    else:
        res = [f"{name}, 你remake在了{nation_line['国家']}"]
    ras = lambda s: res.append("," + s)
    rae = lambda s: res.append("\n" + s)
    if nation_line.get("国家收入等级"):
        income_lvl = nation_line.get("国家收入等级")
        rank = nation_rank[nation_line["国家收入等级"]]
        p_res["rank"] = rank
        game_data["rank"] = rank
        score *= rank
        res = [f"【{income_lvl}】\n"] + res
    if nation_line.get("所在洲"):
        continent = continent_data[nation_line.get("所在洲")]
        skin_color = random.randint(0, 100)
        for k, v in continent.items():
            if skin_color <= v:
                ras(f"你是{k}")
                p_res["race"] = k
                break
            else:
                skin_color -= v
        if p_res["race"] == "白人":
            game_data["race"] = 0
        elif p_res["race"] == "黑人":
            game_data["race"] = 1
        elif p_res["race"] == "混血裔":
            game_data["race"] = 3
        else:
            game_data["race"] = 2
    if nation_line.get("女性人口"):
        tmp = random.randint(0, int(nation_line.get("人口")))  # type: ignore
        if tmp <= int(nation_line.get("女性人口")):  # type: ignore
            ras(f"女性")
            p_res["sexual"] = "女性"
            game_data["sexual"] = 0
        else:
            ras(f"男性")
            p_res["sexual"] = "男性"
            game_data["sexual"] = 1
    if nation_line.get("城镇人口比例"):
        tmp = random.random() * 100
        if tmp <= float(nation_line.get("城镇人口比例")):  # type: ignore
            ras(f"你出生在城市")
            score *= 1.3
        else:
            ras(f"你出生在农村")
    if nation_line.get("贫困人口比例"):
        tmp = random.random() * 100
        if tmp <= float(nation_line.get("贫困人口比例")):  # type: ignore
            rae(f"你出生在贫困户")
            score *= 0.5
            IS_POOR = True
    if nation_line.get("通电率"):
        tmp = random.random() * 100
        if tmp > float(nation_line.get("通电率")):  # type: ignore
            score *= 0.7
            rae(f"你家没有通电")
    if nation_line.get("识字率"):
        tmp = random.random() * 100
        if tmp > float(nation_line.get("识字率")):  # type: ignore
            score *= 0.8
            rae(f"你是文盲")
    if nation_line.get("艾滋病感染率"):
        tmp = random.random() * 100
        if tmp <= float(nation_line.get("艾滋病感染率")):  # type: ignore
            score *= 0.5
            rae(f"你会感染艾滋病")
    if nation_line.get("五岁以下死亡人数"):
        die_early_rate = int(nation_line.get("五岁以下死亡人数")) / int(nation_line.get("人口"))  # type: ignore
        if random.random() < die_early_rate:
            score *= 0.1
            rae(f"你将在5岁以下死亡")
    if nation_line.get("美元人均国民收入") and not IS_POOR:
        avg_income = float(nation_line.get("美元人均国民收入"))  # type: ignore
        # 使用二八定律的混合模型：20%的人口掌握约80%收入
        fraction_high = 0.2
        share_high = 0.8
        # 由总体均值分配出高低两组的均值（保证总体均值为avg_income）
        mean_high = (share_high / fraction_high) * avg_income  # 通常为4*avg_income
        mean_low = ((1 - share_high) / (1 - fraction_high)) * avg_income  # 通常为0.25*avg_income

        # 用对数正态分布模拟组内差异，sigma可以调节不平等程度
        sigma_low = 0.6
        sigma_high = 0.9
        mu_low = math.log(max(mean_low, 1e-6)) - sigma_low**2 / 2
        mu_high = math.log(max(mean_high, 1e-6)) - sigma_high**2 / 2

        # 按比例抽样，20%概率采样高收入组
        if random.random() < fraction_high:
            income = random.lognormvariate(mu_high, sigma_high)
        else:
            income = random.lognormvariate(mu_low, sigma_low)
        
        # 计算混合对数正态分布在样本处的累积分布函数（考虑之后的缩放）
        expected_mean_local = (
            fraction_high * math.exp(mu_high + sigma_high ** 2 / 2)
            + (1 - fraction_high) * math.exp(mu_low + sigma_low ** 2 / 2)
        )
        scale = avg_income / expected_mean_local if expected_mean_local > 0 else 1.0
        scaled_income = income * scale

        def _lognorm_cdf(x: float, mu: float, sigma: float) -> float:
            if x <= 0:
                return 0.0
            z = (math.log(x) - mu) / sigma
            return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

        mixture_cdf = (
            fraction_high * _lognorm_cdf(scaled_income, mu_high, sigma_high)
            + (1 - fraction_high) * _lognorm_cdf(scaled_income, mu_low, sigma_low)
        )
        income_rank = max(0.0, min(1.0, mixture_cdf))

        # p_res["income_rank"] = income_rank
        # game_data["income_rank"] = income_rank

        # 由于样本与理论期望有偏差，按理论期望做一次缩放以确保总体均值约为avg_income
        expected_mean = (
            fraction_high * math.exp(mu_high + sigma_high**2 / 2)
            + (1 - fraction_high) * math.exp(mu_low + sigma_low**2 / 2)
        )
        if expected_mean > 0:
            income = income * (avg_income / expected_mean)

        # 更新得分（保持原逻辑：以均方根比率调整）
        score *= math.sqrt(max(income, 0.0) / avg_income)
        rae(f"你们家人均年收入大约为{income:.2f}$ (国内前{(1-income_rank)*100:.2f}%)")
        if nation_line.get("PPP人均国民收入"):
            ppp_income = float(nation_line.get("PPP人均国民收入"))  # type: ignore
            pt_income = income * ppp_income / avg_income / 17090 * 10550
            rae(f"PPP后约等价为中国2021年月薪{pt_income*7/12:.2f}¥")
    if nation_line.get("失业率"):
        tmp = random.random() * 100
        if tmp <= float(nation_line.get("失业率")):  # type: ignore
            score *= 0.85
            rae(f"你将会失业")
        else:
            if all(
                [
                    nation_line.get("服务业就业比例"),
                    nation_line.get("农业就业比例"),
                    nation_line.get("工业就业比例"),
                ]
            ):
                work_res = weight_random(
                    {
                        "农业": float(nation_line.get("农业就业比例")),  # type: ignore
                        "工业": float(nation_line.get("工业就业比例")),  # type: ignore
                        "服务业": float(nation_line.get("服务业就业比例")),  # type: ignore
                    }
                )
                rae(f"你更可能会从事{work_res}工作")
    if nation_line.get("出生预期寿命"):
        avg_lt = float(nation_line.get("出生预期寿命"))  # type: ignore
        life_time = random.gauss(avg_lt, avg_lt / 10)
        score *= math.sqrt(life_time / avg_lt)
        rae(f"你的预期寿命为{life_time:.1f}年")
    rae(f"# 投胎得分: {score:.2f}")
    # rae(f"本次投胎种子: #{seed}")
    p_res["score"] = score
    p_res["seed"] = seed
    return "".join(res), p_res, game_data


def get_remake(name, seed=""):
    return nation_parse(name, seed)


# print(nation_parse("BKN", ""))
