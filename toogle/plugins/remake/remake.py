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
    "高收入国家": 5,
    "中高等收入国家": 3,
    "中低等收入国家": 1.5,
    "低收入国家": 0.3,
    "未分类国家": 1,
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
    IS_DEAD_EARLY = False
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
        res = [f"你remake在了{nation_line['国家']}"]
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
            IS_DEAD_EARLY = True
    if nation_line.get("美元人均国民收入") and not IS_POOR:
        gini_coeff = 0.44  # 世界平均基尼系数
        if nation_line.get("基尼系数"):
            gini_coeff = float(nation_line.get("基尼系数")) / 100 # type: ignore
        
        avg_income = float(nation_line.get("美元人均国民收入"))  # type: ignore
        # 使用对数正态分布，通过基尼系数计算标准差σ
        # 对数正态分布的基尼系数公式: Gini = 2*Φ(σ/√2) - 1
        # 其中Φ是标准正态分布的累积分布函数
        # 反推：Φ(σ/√2) = (Gini + 1) / 2
        # 因此：σ = √2 * Φ^(-1)((Gini + 1) / 2)
        
        # 使用Abramowitz和Stegun的近似公式计算标准正态分布的逆累积分布函数
        def norm_ppf(p):
            """标准正态分布的逆累积分布函数（百分位点函数）"""
            if p <= 0 or p >= 1:
                raise ValueError("p must be in (0, 1)")
            
            # 使用有理函数近似（Abramowitz and Stegun approximation）
            if p < 0.5:
                # 使用对称性: ppf(p) = -ppf(1-p)
                return -norm_ppf(1 - p)
            
            # 对于p >= 0.5，使用近似公式
            t = math.sqrt(-2 * math.log(1 - p))
            c0, c1, c2 = 2.515517, 0.802853, 0.010328
            d1, d2, d3 = 1.432788, 0.189269, 0.001308
            
            numerator = c0 + c1 * t + c2 * t**2
            denominator = 1 + d1 * t + d2 * t**2 + d3 * t**3
            
            return t - numerator / denominator
        
        # 计算σ
        p = (gini_coeff + 1) / 2
        sigma = float(math.sqrt(2) * norm_ppf(p))
        
        # 对数正态分布参数
        # E[X] = exp(μ + σ²/2) = avg_income
        # 因此 μ = ln(avg_income) - σ²/2
        mu = float(math.log(avg_income) - sigma**2 / 2)
        
        income = random.lognormvariate(mu, sigma)

        def _lognorm_cdf(x: float, mu: float, sigma: float) -> float:
            if x <= 0:
                return 0.0
            z = (math.log(x) - mu) / sigma
            return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

        mixture_cdf = _lognorm_cdf(income, mu, sigma)
        income_rank = max(0.0, min(1.0, mixture_cdf))

        # 更新得分（保持原逻辑：以均方根比率调整）
        score *= pow(max(income, 0.0) / avg_income, 1/4)
        rae(f"你父母人均年收入大约为{income:.2f}$ (国内前{(1-income_rank)*100:.2f}%)")
        if nation_line.get("PPP人均国民收入"):
            ppp_income = float(nation_line.get("PPP人均国民收入"))  # type: ignore
            pt_income = income * ppp_income / avg_income / 17090 * 10550
            rae(f"PPP后约等价月薪{pt_income*7/12:.2f}¥")
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
        if IS_DEAD_EARLY:
            life_time = random.uniform(0, 5)
        else:
            # Weibull distribution for adult lifespan
            # Shape parameter beta=5 gives a reasonable left-skewed distribution for aging
            alpha = avg_lt / 0.91817
            life_time = random.weibullvariate(alpha, 5)
            if life_time < 5:
                life_time = 5 + random.random() * 5

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
