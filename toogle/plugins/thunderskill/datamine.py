import os
import io
import json

from thefuzz import fuzz, process
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont

from toogle.configs import config


git_dir = config.get('WT_DATAMINE_GIT', '')

def cutoff_dict(input_dict):
    res ={}
    for k, v in input_dict.items():
        if isinstance(v, dict):
            tmp = cutoff_dict(v)
            if tmp:
                res[k] = tmp
        elif v:
            res[k] = v
    return res


def missile_parse(file_path):
    DATA = json.load(open(file_path, "r"))

    def jdata(path, cal_val=False):
        path = path.split('.')
        res = DATA
        for item in path:
            res = res.get(item)
            if not res:
                if cal_val:
                    return 0
                return None
        return res

    res = {
        "ID": file_path.split('/')[-1].replace('.blkx', ''),
        "弹体ID": jdata("mesh"),
        "参数ID": jdata("rocket.bulletName"),
        "出生点": jdata("preset_cost"),
        "口径": jdata("rocket.caliber") * 1000, # type: ignore
        "质量": jdata("rocket.mass"),
        "动力": {
            "空阻系数": jdata("rocket.CxK"),
            "一级动力段推力": jdata("rocket.force"),
            "一级动力段时间": jdata("rocket.timeFire"),
            "一级动力段平均推重比": jdata("rocket.force", cal_val=True)
            / (jdata("rocket.mass", cal_val=True) + jdata("rocket.massEnd", cal_val=True)) # type: ignore
            * 2,
            "二级动力段推力": jdata("rocket.force1"),
            "二级动力段时间": jdata("rocket.timeFire1"),
            "二级动力段平均推重比": jdata("rocket.force1", cal_val=True)
            / (jdata("rocket.massEnd", cal_val=True) + jdata("rocket.massEnd1", cal_val=True)) # type: ignore
            * 2,
            "最大射程": jdata("rocket.maxDistance"),
            "末端速度": jdata("rocket.endSpeed"),
        },
        "机动": {
            "尾翼最大攻角": f"{jdata('rocket.finsAoaHor', cal_val=True) * 90}° {jdata('rocket.finsAoaVer', cal_val=True) * 90}°",  # type: ignore
            "矢量推力": jdata("rocket.thrustVectoringAngle"),
            "机翼面积因子": jdata("rocket.wingAreaMult"),
            "实际G值限制": jdata("rocket.guidance.guidanceAutopilot.reqAccelMax"),
            "发射G值限制": jdata("rocket.loadFactorMax"),
        },
        "制导": {
            "预热时间": jdata("rocket.guidance.warmUpTime"),
            "发射窗口时间": jdata("rocket.guidance.workTime"),
            "锁定目标后解锁引导头": jdata("rocket.guidance.uncageBeforeLaunch"),
            "发射后进入制导时间": jdata("rocket.guidance.lockTimeOut"),
            "红外制导": {
                "后向锁定距离": jdata("rocket.guidance.irSeeker.rangeBand0"),
                "全向锁定距离": jdata("rocket.guidance.irSeeker.rangeBand1"),
                "热诱弹干扰距离": jdata("rocket.guidance.irSeeker.rangeBand2"),
                "IRCM干扰距离": jdata("rocket.guidance.irSeeker.rangeBand3"),
                "地面IRCM干扰距离": jdata("rocket.guidance.irSeeker.rangeBand4"),
                "DIRCM干扰距离": jdata("rocket.guidance.irSeeker.rangeBand6"),
                "导弹FoV": jdata("rocket.guidance.irSeeker.fov"),
                "锁定FoV": jdata("rocket.guidance.irSeeker.lockAngleMax"),
                "战斗锁定FoV": jdata("rocket.guidance.irSeeker.angleMax"),
                "热源门限角度": jdata("rocket.guidance.irSeeker.gateWidth"),
                "最小对日角": jdata("rocket.guidance.irSeeker.minAngleToSun"),
                "屏蔽红外频段": jdata("rocket.guidance.irSeeker.bandMaskToReject"),
            },
            "惯性制导": {
                "惯性制导偏移速度": jdata("rocket.guidance.inertialGuidance.inertialNavigationDriftSpeed"),
            },
            "雷达制导": {
                "主动雷达": jdata("rocket.guidance.radarSeeker.active"),
                "波段屏蔽": jdata("rocket.guidance.radarSeeker.designationSourceTypeMask"),
                "旁瓣衰减": jdata("rocket.guidance.radarSeeker.sideLobesAttenuation"),
                "锁定FoV": jdata("rocket.guidance.radarSeeker.lockAngleMax"),
                "战斗锁定FoV": jdata("rocket.guidance.radarSeeker.angleMax"),
            },
        },
        "战斗部": {
            "近炸保险时间": jdata("rocket.proximityFuse.timeOut"),
            "保险距离": jdata("rocket.armDistance"),
            "近炸保险距离": jdata("rocket,proximityFuse.armDistance"),
            "近炸半径": jdata("rocket.proximityFuse.radius"),
            "爆炸当量": jdata("rocket.explosiveMass"),
            "弹片爆炸半径": jdata("rocket.shutterDamageRadius"),
        }
    }

    res = cutoff_dict(res)
    def parse(d, depth):
        res_text = ""
        for k, v in d.items():
            if isinstance(v, dict):
                res_text += f"{depth * '    '}{k}:\n"
                res_text += parse(v, depth + 1)
            else:
                res_text += f"{depth * '    '}{k}: {v}\n"
        return res_text

    return parse(res, 0)


def search(query):
    missile_path = "/missile_index/missiles/"
    missiles = os.listdir(git_dir + missile_path)
    query = query.replace("-", "")
    exact_list = [x for x in missiles if query == x.replace('.blkx', '')]
    if len(exact_list) == 1:
        return git_dir + missile_path + exact_list[0]

    query_list = [x for x in missiles if query in x.replace('_', '')]
    if len(query_list) == 1:
        return git_dir + missile_path + query_list[0]
    else:
        fuzz_filter = process.extract(query, missiles, limit=5)
        for v in fuzz_filter:
            if v[1] > 90:
                return v[0]
        fuzz_filter = [v[0] for v in fuzz_filter if v[1] > 70]
        if len(fuzz_filter) == 1:
            return git_dir + missile_path + fuzz_filter[0]
        return list(set([x.replace('.blkx', '') for x in query_list + fuzz_filter]))


def missile_damage_module(file_path):
    DATA = json.load(open(file_path, "r"))
    shatters = DATA["rocket"]["damage"]["shatter"]["segment"]
    size = (200, 200)
    image = PIL.Image.new("RGBA", size, (255, 255, 255))
    draw = PIL.ImageDraw.Draw(image)
    for seg in shatters:
        portion = seg.get("countPortion", 0)
        angles = seg.get("angles", [0, 0])
        radius = seg.get("radiusScale", 0)
        penetration = seg.get("penetrationScale", 0)
        damage = seg.get("damageScale", 0)
        color = (
            int(130 * (damage)),
            100,
            100,
        )
        pieslice_size = (
            (int(size[0] * (1 - radius)), int(size[1] * (1 - radius))),
            (int(size[0] * radius), int(size[1] * radius)),
        )
        if radius > 0:
            draw.pieslice(pieslice_size, angles[0] - 90, angles[1] - 89, color)
    draw.ellipse([0, 0, size[0], size[1]], outline=(50, 50, 50), width=2)
    img_bytes = io.BytesIO()
    image.save(img_bytes, format="PNG")
    return img_bytes.getvalue()


def get_missile_detail(file_path):
    return [
        missile_parse(file_path),
        "弹片散射区域:",
        missile_damage_module(file_path),
    ]


# print(json.dumps(res, indent=2, ensure_ascii=False))
if __name__ == "__main__":
    query = "aim7m"
    query_list = search(query)
    if isinstance(query_list, list):
        print(query_list)
    else:
        res = missile_parse(query_list)
        print(res)
    pass
