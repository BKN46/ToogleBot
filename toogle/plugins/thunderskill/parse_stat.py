import datetime
import json

import bs4


def parse_player_stat(html: str):
    soup = bs4.BeautifulSoup(html, "html.parser")

    update_date, last_date = [
        datetime.datetime.strptime(x.contents[0], "%b %d, %Y, %I:%M:%S %p")
        for x in soup.find(class_="stat_dt").find_all("strong")
    ]

    ab_stat, rb_stat, sb_stat = soup.find_all(class_="col mycol text-center")

    res = {
        "name": soup.find(class_="nick").contents[1].strip(),
        "squad": soup.find(class_="squad_name").a.contents[0].strip()
        if soup.find(class_="squad_name").a
        else "",
        "update": update_date.strftime("%Y-%m-%d %H:%M:%S"),
        "last_update": last_date.strftime("%Y-%m-%d %H:%M:%S"),
        "rb_eff": rb_stat.find(class_="kpd_value").contents[0],
        "rb_wr": rb_stat.find(string="Win rate")
        .find_parent(class_="list-group-item")
        .find(class_="badge")
        .contents[0],
        "rb_kd": rb_stat.find(string="Kill / Death ratio")
        .find_parent(class_="list-group-item")
        .find(class_="badge")
        .contents[0],
        "rb_battles": rb_stat.find(string="Total No. of battles")
        .find_parent(class_="list-group-item")
        .find(class_="badge")
        .contents[0],
        "rb_level": rb_stat.find(class_="resume").contents[0].strip(),
    }
    return res


def parse_player_vehicle(html: str):
    def get_value(v, x, form=int):
        return form(
            v.find(string=x)
            .find_parent("li")
            .find(class_="param_value")
            .strong.contents[0]
        )

    def get_diff(v, x, form=int):
        if v.find(string=x).find_parent("li").find(class_="diff").contents:
            return form(
                v.find(string=x).find_parent("li").find(class_="diff").span.contents[0]
            )
        return 0

    soup = bs4.BeautifulSoup(html, "html.parser")

    update_date, last_date = [
        datetime.datetime.strptime(x.contents[0], "%b %d, %Y, %I:%M:%S %p")
        for x in soup.find(class_="stat_dt").find_all("strong")
    ]

    vehicles = soup.find_all("td", class_="vehicle")
    res = {}
    for v in vehicles:
        v_name = v.span.contents[0]
        if get_diff(v, "Battles") > 0:
            res[v_name] = {
                "update": update_date.strftime("%Y-%m-%d %H:%M:%S"),
                "last": last_date.strftime("%Y-%m-%d %H:%M:%S"),
                "name": v_name,
                "battles": get_value(v, "Battles"),
                "battles_d": get_diff(v, "Battles"),
                "respawns": get_value(v, "Respawns"),
                "respawns_d": get_diff(v, "Respawns"),
                "victories": get_value(v, "Victories"),
                "victories_d": get_diff(v, "Victories"),
                "deaths": get_value(v, "Deaths"),
                "deaths_d": get_diff(v, "Deaths"),
                "frags": get_value(v, "Overall ground frags"),
                "frags_d": get_diff(v, "Overall ground frags"),
                "afrags": get_value(v, "Overall air frags"),
                "afrags_d": get_diff(v, "Overall air frags"),
            }
            res[v_name].update(
                {
                    "kd": round(res[v_name]["frags"] / (res[v_name]["deaths"] or 1), 2),
                    "kd_d": round(
                        res[v_name]["frags_d"] / (res[v_name]["deaths_d"] or 1), 2
                    ),
                    "akd": round(
                        res[v_name]["afrags"] / (res[v_name]["deaths"] or 1), 2
                    ),
                    "akd_d": round(
                        res[v_name]["afrags_d"] / (res[v_name]["deaths_d"] or 1), 2
                    ),
                    "wr": round(
                        res[v_name]["victories"] / (res[v_name]["battles"] or 1), 2
                    ),
                    "wr_d": round(
                        res[v_name]["victories_d"] / (res[v_name]["battles_d"] or 1), 2
                    ),
                }
            )

    return res


def player_report(player_stat):
    res = (
        f"{player_stat['squad']}{player_stat['name']}\n更新日期 {player_stat['update']}\n统计周期 {player_stat['last_update']}-{player_stat['update']}\n"
        f"历史效率: {player_stat['rb_eff']}，胜率: {player_stat['rb_wr']}，全局K/D: {player_stat['rb_kd']}，战斗数: {player_stat['rb_battles']}\n"
        f"历史等级: {player_stat['rb_level']}\n"
    )
    # print(res)
    return res


def player_vehicle_report(vehicles):
    vehicles = vehicles.values()
    vehicles = sorted(vehicles, key=lambda x: x["respawns_d"], reverse=True)[:10]
    res = "统计周期内最常使用10辆车的战斗数据：\n"
    for v in vehicles:
        res += f"{v['name']}：总共{v['battles']}场战斗，最近{v['battles_d']}次战斗，胜率 {v['wr_d']}，对地K/D {v['kd_d']}，对空K/D {v['akd_d']}\n"
    # print(json.dumps(list(vehicles), indent=4))
    # print(res)
    return res


if __name__ == "__main__":
    player_report(
        parse_player_stat(open("get_stat.html", "r", encoding="utf-8").read())
    )
    player_vehicle_report(
        parse_player_vehicle(open("get_r_stat.html", "r", encoding="utf-8").read())
    )
