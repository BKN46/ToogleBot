import os
import re
import time

import requests
from thefuzz import fuzz, process

DATA_DIR = "data/pcbench"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)


BRAND_NAME = {
    "华硕": "Asus",
    "技嘉": "Gigabyte",
    "微星": "MSI",
    "华擎": "ASRock",
    "七彩虹": "Colorful",
    "影驰": "Galax",
    "映泰": "Biostar",
    "迪兰": "PowerColor",
    "索泰": "Zotac",
    "铭瑄": "Maxsun",
    "昂达": "Gainward",
    "映众": "Yeston",
    "丽台": "Leadtek",
    "矽力": "Silicon Power",
    "铭盛": "Manli",
    "铭创": "Gainward",
    "映众": "Yeston",
    "必恩威": "PNY",
    "英特尔": "Intel",
    "英伟达": "Nvidia",
}


def reverse_find_brand(brand_eng):
    for brand in BRAND_NAME:
        if BRAND_NAME[brand] == brand_eng:
            return brand
    return brand_eng


class Hardware:
    def __init__(self, json_dict):
        self.type = json_dict["Type"]
        self.brand = json_dict["Brand"]
        self.serial = json_dict["Part Number"]
        self.model = json_dict["Model"]
        self.rank = json_dict["Rank"]
        self.samples = json_dict["Samples"]
        self.score = float(json_dict["Benchmark"])
        self.url = json_dict["URL"]


    def __str__(self):
        # return f"[{self.score}]{self.model}({self.serial})"
        return f"[{self.score}][{reverse_find_brand(self.brand)}]{self.serial}" if self.serial else f"[{self.score}][{reverse_find_brand(self.brand)}]{self.model}"
        # return f"[{self.score}]{self.model} - {self.brand} ({self.serial})"


def read_csv(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        header = f.readline().strip().split(",")
        data = [
            Hardware(dict(zip(header, x.strip().split(","))))
            for x in f.readlines()
        ]
    return data


def get_userbenchmark_data(data_name):
    now_time = int(time.time())
    data_file = [x for x in os.listdir(DATA_DIR) if x.startswith(data_name)]
    if not data_file or now_time - int(data_file[0].split(".")[0].split("_")[-1]) > 7 * 24 * 3600:
        url = f"https://www.userbenchmark.com/resources/download/csv/{data_name}.csv"
        res = requests.get(url)
        file_path = os.path.join(DATA_DIR, f"{data_name}_{now_time}.csv")
        with open(file_path, "wb") as f:
            f.write(res.content)
        return read_csv(file_path)
    else:
        return read_csv(os.path.join(DATA_DIR, data_file[0]))


def manual_update_data():
    global ALL_DATA
    ALL_DATA = [
        *get_userbenchmark_data("CPU_UserBenchmarks"),
        *get_userbenchmark_data("GPU_UserBenchmarks"),
    ]


def find_designated_hardware(text, output_limit=100):
    hardware_brand = ""
    for brand in BRAND_NAME:
        if brand in text:
            text = text.replace(brand, "").strip()
            hardware_brand = BRAND_NAME[brand]
            break
    
    res = []

    for hardware in ALL_DATA:
        if hardware_brand and hardware_brand != hardware.brand:
            continue
        if text.lower().replace(" ", "") in hardware.model.lower().replace(" ", ""):
            res.append(hardware)
        # elif fuzz.ratio(text, hardware.model) > 60:
        #     res.append(hardware)

    return res[:output_limit]


def rank_hardware_list(hardwares):
    str_list, hardware_list = [], []
    for hardware in hardwares:
        if hardware.model not in str_list:
            str_list.append(hardware.model)
            hardware_list.append(hardware)
    hardware_list.sort(key=lambda x: x.score, reverse=True)
    res, max_score = "", hardware_list[0].score
    for comp in hardware_list:
        res += f"[{-(max_score - comp.score) / max_score * 100 : >5.1f}%]{comp}\n"
    return res
    


def get_compairison(text):
    manual_update_data()

    re_str = r"\.it (.*?)(vs|$)(.*?)$"
    res = re.match(re_str, text)
    comp1, is_comp, comp2 = res.group(1).strip(), res.group(2), res.group(3).strip() # type: ignore
    hw1, hw2 = find_designated_hardware(comp1), find_designated_hardware(comp2) if is_comp else []
    if not hw1:
        return "没有找到对应硬件: " + comp1
    if not hw2 and is_comp:
        return "没有找到对应硬件: " + comp2
    
    all_comp = hw1 + hw2
    return rank_hardware_list(all_comp)


if __name__ == "__main__":
    # res = get_userbenchmark_data("CPU_UserBenchmarks")
    # print(get_compairison(".it 七彩虹4070"))
    # print(get_compairison(".it 12700K"))
    print(get_compairison(".it 4070 ti vs 4070"))
    # print('\n'.join([str(x) for x in find_designated_hardware("华硕4070")]))
