import json

from thefuzz import fuzz, process

tech_tree = json.load(open("toogle/plugins/thunderskill/vehicle_tree.json", "r"))
vehicle_price = json.load(open("toogle/plugins/thunderskill/vehicle_price.json", "r"))


def get_vehicle(text):
    if len(text) < 2:
        return ""
    vehicle_filter = [k for k in vehicle_price.keys() if text in k]
    if len(vehicle_filter) == 1:
        return vehicle_filter[0]
    else:
        fuzz_filter = process.extract(text, vehicle_price.keys(), limit=5)
        for v in fuzz_filter:
            if v[1] > 90:
                return v[0]
        fuzz_filter = [v[0] for v in fuzz_filter if v[1] > 70]
        if len(fuzz_filter) == 1:
            return fuzz_filter[0]
        return vehicle_filter + fuzz_filter


def text_post_proc(text):
    return text.replace("_", " ")


def calc_line_cost(vehicle_name, vehicle_name_end):
    from_start = not vehicle_name
    find_line, find_end = from_start, False
    total_rp, total_sl = 0, 0
    for k, v in tech_tree.items():
        for line in v:
            for vehicle in line:
                if type(vehicle) == list:
                    if vehicle_name in vehicle or find_line:
                        find_line = True
                        total_rp += vehicle_price[vehicle[0]]["rp"]
                        total_sl += vehicle_price[vehicle[0]]["sl"]
                    elif vehicle_name_end in vehicle and find_line:
                        find_end = True
                        total_rp += vehicle_price[vehicle[0]]["rp"]
                        total_sl += vehicle_price[vehicle[0]]["sl"]
                        break
                elif vehicle_name == vehicle:
                    find_line = True
                    total_rp += vehicle_price[vehicle]["rp"]
                    total_sl += vehicle_price[vehicle]["sl"]
                elif vehicle_name_end == vehicle and find_line:
                    find_end = True
                    total_rp += vehicle_price[vehicle]["rp"]
                    total_sl += vehicle_price[vehicle]["sl"]
                    break
                elif find_line:
                    total_rp += vehicle_price[vehicle]["rp"]
                    total_sl += vehicle_price[vehicle]["sl"]
            if find_end:
                if type(line[0]) == list:
                    start_v = line[0][0]
                else:
                    start_v = line[0]
                return total_rp, total_sl, start_v
            elif from_start:
                total_rp, total_sl = 0, 0
            elif find_line and not find_end:
                return 0, 0, ""
    return 0, 0, ""


def get_line_cost(v1, v2):
    search = []
    for v in [v1, v2]:
        search_list = get_vehicle(v)
        if type(search_list) == list:
            return f"没有找到{v}，是不是想搜索:\n" + "\n".join(search_list)
        search.append(search_list)
    res = calc_line_cost(*search)
    if res[0] == 0:
        return f"科技树路径不通"
    elif not search[0]:
        search[0] = res[2]
    return f"从{search[0]}研发到{search[1]}需要{res[0]:,}研发点和{res[1]:,}银狮"


def get_golden_eagle_price(ge):
    price_map = {25000: 113.85, 10000: 49.50, 2500: 16.50, 1000: 6.60, 150: 0.99}
    return ge / 25000 * price_map[25000]


if __name__ == "__main__":
    print(get_line_cost("leo2a4", "leo2a6"))
    # print(get_golden_eagle_price(20000))
    # print(get_vehicle('2a6'))
