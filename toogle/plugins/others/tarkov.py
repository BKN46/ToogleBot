import datetime
import json
import os
import sys
import requests

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from toogle.configs import config

TARKOV_DATA_PATH = "data/tarkov.json"
TARKOV_MARKET_SECRET = config.get("TARKOV_MARKET_SECRET")
proxies = {
    'http': config.get('REQUEST_PROXY_HTTP', ''),
    'https': config.get('REQUEST_PROXY_HTTPS', ''),
}

TRADER_CN_NAMES = {
    "Prapor": "俄商Prapor",
    "Therapist": "大妈Therapist",
    "Skier": "配件商Skier",
    "Peacekeeper": "美商Peacekeeper",
    "Mechanic": "机械师Mechanic",
    "Ragman": "服装商Ragman",
    "Jaeger": "猎人Jaeger",
    "Fence": "黑商Fence",
}

HIDEOUT_CN_NAMES = {
    "Generator": "发电机",
    "Workbench": "工作台",
    "Illumination": "照明",
    "Heating": "供暖",
    "Water Collector": "水收集器",
    "Nutrition Unit": "营养单元",
    "Medstation": "医疗站",
    "Security": "安全",
    "Rest Space": "休息空间",
    "Scav Case": "掠夺者箱",
    "Intelligence Center": "情报中心",
    "Air Filtering": "空气过滤",
    "Vents": "通风口",
    "Water Collector": "水收集器",
    "Booze Generator": "酒精发生器",
    "Bitcoin Farm": "比特币农场",
    "Solar Power": "太阳能",
    "Lavatory": "卫生",
    "Stash": "仓库",
    "Shooting Range": "射击场",
    "Weapon Rack": "武器架",
    "Gym": "健身房",
    "Defective Wall": "破损墙",
    "Library": "图书馆",
    "Hall of Fame": "展示台",
}


def get_sites():
    return f"[交互地图]https://escapefromtarkov.fandom.com/wiki/Map:Customs#"\
    f"\n[快速定位]https://tarkov-market.com/maps/woods"\
    f"\n[跳蚤市场]https://tarkov-market.com/"\
    f"\n[任务跟踪]https://tarkov-market.com/"\
    f"\n[子弹信息]https://www.eft-ammo.com/"\
    f"\n[弹道计算]https://tarkov-ballistics.com/"\
    f"\n[其他数据]https://tarkov.dev/"\


def query_tarkov_dev(query):
    url = "https://api.tarkov.dev/graphql"
    data = {
        # "operationName": operation,
        # "variables": {},
        "query": query,
    }
    return requests.post(url, json=data, proxies=proxies).json()["data"]



def get_tarkov_meta_data():
    res = {
        **query_tarkov_dev("query TarkovDevCrafts {\n            crafts(lang: zh) {\n                station {\n                    id\n                    normalizedName\n                }\n                level\n                duration\n                rewardItems {\n                    item {\n                        id\n                    }\n                    count\n                }\n                requiredItems {\n                    item {\n                        id\n                    }\n                    count\n                    attributes {\n                        type\n                        name\n                        value\n                    }\n                }\n                taskUnlock {\n                    id\n                }\n            }\n        }"),
        **query_tarkov_dev("query TarkovDevBarters {\n            barters(lang: zh) {\n                rewardItems {\n                    item {\n                        id\n                    }\n                    count\n                }\n                requiredItems {\n                    item {\n                        id\n                    }\n                    count\n                    attributes {\n                        name\n                        value\n                    }\n                }\n                trader {\n                    id\n                    name\n                    normalizedName\n                }\n                level\n                taskUnlock {\n                    id\n                    tarkovDataId\n                    name\n                    normalizedName\n                }\n            }\n        }"),
        **query_tarkov_dev("query TarkovDevHideout {\n        hideoutStations(lang: zh) {\n            id\n            name\n            normalizedName\n            imageLink\n            levels {\n                id\n                level\n                itemRequirements {\n                    quantity\n                    item {\n                        name\n                        id\n                        iconLink\n                    }\n                } \n                stationLevelRequirements {\n                    station {\n                        id\n                        normalizedName\n                    }\n                    level\n                }\n                traderRequirements {\n                    trader {\n                        id\n                        normalizedName\n                    }\n                    level\n                }\n            }\n            crafts {\n                id\n            }\n        }\n    }"),
        **query_tarkov_dev("query TarkovDevBosses {\n            bosses(lang: zh) {\n                name\n                normalizedName\n                imagePortraitLink\n                imagePosterLink\n                health {\n                    id\n                    max\n                }\n                equipment {\n                    item {\n                        id\n                        containsItems {\n                            item {\n                                id\n                            }\n                        }\n                    }\n                    attributes {\n                        name\n                        value\n                    }\n                }\n                items {\n                    id\n                }\n            }\n        }"),
        **query_tarkov_dev("query TarkovDevMaps {\n            maps(lang: zh) {\n                id\n                tarkovDataId\n                name\n                normalizedName\n                wiki\n                description\n                enemies\n                raidDuration\n                players\n                bosses {\n                    name\n                    normalizedName\n                    spawnChance\n                    spawnLocations {\n                        spawnKey\n                        name\n                        chance\n                    }\n                    escorts {\n                        name\n                        normalizedName\n                        amount {\n                            count\n                            chance\n                        }\n                    }\n                    spawnTime\n                    spawnTimeRandom\n                    spawnTrigger\n                    switch {\n                        id\n                    }\n                }\n                spawns {\n                    zoneName\n                    position {\n                        x\n                        y\n                        z\n                    }\n                    sides\n                    categories\n                }\n                extracts {\n                    id\n                    name\n                    faction\n                    position {\n                        x\n                        y\n                        z\n                    }\n                    outline {\n                        x\n                        y\n                        z\n                    }\n                    top\n                    bottom\n                    switches {\n                        id\n                        name\n                    }\n                }\n                locks {\n                    lockType\n                    key {\n                        id\n                    }\n                    needsPower\n                    position {\n                        x\n                        y\n                        z\n                    }\n                    outline {\n                        x\n                        y\n                        z\n                    }\n                    top\n                    bottom\n                }\n                hazards {\n                    hazardType\n                    name\n                    position {\n                        x\n                        y\n                        z\n                    }\n                    outline {\n                        x\n                        y\n                        z\n                    }\n                    top\n                    bottom\n                }\n                lootContainers {\n                    lootContainer {\n                        id\n                        name\n                        normalizedName\n                    }\n                    position {\n                        x\n                        y\n                        z\n                    }\n                }\n                switches {\n                    id\n                    name\n                    switchType\n                    activatedBy {\n                        id\n                        name\n                    }\n                    activates {\n                        operation\n                        target {\n                            __typename\n                            ...on MapSwitch {\n                                id\n                                name\n                            }\n                            ...on MapExtract {\n                                id\n                                name\n                                faction\n                            }\n                        }\n                    }\n                    position {\n                        x\n                        y\n                        z\n                    }\n                }\n                stationaryWeapons {\n                    stationaryWeapon {\n                        name\n                        shortName\n                    }\n                    position {\n                        x\n                        y\n                        z\n                    }\n                }\n            }\n        }"),
        **query_tarkov_dev("query TarkovDevTraders {\n        traders(lang: zh) {\n            id\n            name\n            description\n            normalizedName\n            imageLink\n            currency {\n                id\n                name\n                normalizedName\n            }\n            resetTime\n            discount\n            levels {\n                id\n                level\n                requiredPlayerLevel\n                requiredReputation\n                requiredCommerce\n                payRate\n                insuranceRate\n                repairCostMultiplier\n            }\n            barters {\n                id\n            }\n        }\n    }"),
        **query_tarkov_dev("query TarkovDevTasks {\n            tasks(lang: zh) {\n                id\n                tarkovDataId\n                name\n                normalizedName\n                trader {\n                    id\n                    name\n                    normalizedName\n                }\n                map {\n                    id\n                    name\n                    normalizedName\n                }\n                experience\n                wikiLink\n                minPlayerLevel\n                taskRequirements {\n                    task {\n                        id\n                    }\n                    status\n                }\n                traderRequirements {\n                    trader {\n                        id\n                        name\n                    }\n                    requirementType\n                    compareMethod\n                    value\n                }\n                restartable\n                objectives {\n                    ...TaskObjectiveInfo\n                }\n                failConditions {\n                    ...TaskObjectiveInfo\n                }\n                startRewards {\n                    ...taskRewardFragment\n                }\n                finishRewards {\n                    ...taskRewardFragment\n                }\n                failureOutcome {\n                    ...taskRewardFragment\n                }\n                factionName\n                neededKeys {\n                    keys {\n                        id\n                    }\n                    map {\n                        id\n                    }\n                }\n                kappaRequired\n                lightkeeperRequired\n            }\n        }\n        fragment TaskObjectiveInfo on TaskObjective {\n            __typename\n            id\n            type\n            description\n            maps {\n                id\n                name\n            }\n            optional\n            ...on TaskObjectiveBasic {\n                zones {\n                    id\n                    map {\n                        id\n                    }\n                    position {\n                        x\n                        y\n                        z\n                    }\n                    outline {\n                        x\n                        y\n                        z\n                    }\n                    top\n                    bottom\n                }\n            }\n            ...on TaskObjectiveBuildItem {\n                item {\n                    id\n                }\n                containsAll {\n                    id\n                }\n                containsCategory {\n                    id\n                    name\n                    normalizedName\n                }\n                attributes {\n                    name\n                    requirement {\n                        compareMethod\n                        value\n                    }\n                }\n            }\n            ...on TaskObjectiveExperience {\n                healthEffect {\n                    bodyParts\n                    effects\n                    time {\n                        compareMethod\n                        value\n                    }\n                }\n            }\n            ...on TaskObjectiveExtract {\n                exitStatus\n                exitName\n                count\n            }\n            ...on TaskObjectiveItem {\n                items {\n                    id\n                }\n                count\n                foundInRaid\n                dogTagLevel\n                maxDurability\n                minDurability\n                zones {\n                    id\n                    map {\n                        id\n                    }\n                    position {\n                        x\n                        y\n                        z\n                    }\n                    outline {\n                        x\n                        y\n                        z\n                    }\n                    top\n                    bottom\n                }\n            }\n            ...on TaskObjectiveMark {\n                markerItem {\n                    id\n                }\n                zones {\n                    id\n                    map {\n                        id\n                    }\n                    position {\n                        x\n                        y\n                        z\n                    }\n                    outline {\n                        x\n                        y\n                        z\n                    }\n                    top\n                    bottom\n                }\n            }\n            ...on TaskObjectivePlayerLevel {\n                playerLevel\n            }\n            ...on TaskObjectiveQuestItem {\n                questItem {\n                    id\n                    name\n                    shortName\n                    width\n                    height\n                    iconLink\n                    gridImageLink\n                    image512pxLink\n                    baseImageLink\n                    image8xLink\n                }\n                possibleLocations {\n                    map {\n                        id\n                    }\n                    positions {\n                        x\n                        y\n                        z\n                    }\n                }\n                zones {\n                    id\n                    map {\n                        id\n                    }\n                    position {\n                        x\n                        y\n                        z\n                    }\n                    outline {\n                        x\n                        y\n                        z\n                    }\n                    top\n                    bottom\n                }\n                count\n            }\n            ...on TaskObjectiveShoot {\n                targetNames\n                count\n                shotType\n                zoneNames\n                bodyParts\n                timeFromHour\n                timeUntilHour\n                usingWeapon {\n                    id\n                }\n                usingWeaponMods {\n                    id\n                }\n                wearing {\n                    id\n                }\n                notWearing {\n                    id\n                }\n                distance {\n                    compareMethod\n                    value\n                }\n                playerHealthEffect {\n                    bodyParts\n                    effects\n                    time {\n                        compareMethod\n                        value\n                    }\n                }\n                enemyHealthEffect {\n                    bodyParts\n                    effects\n                    time {\n                        compareMethod\n                        value\n                    }\n                }\n                zones {\n                    id\n                    map {\n                        id\n                    }\n                    position {\n                        x\n                        y\n                        z\n                    }\n                    outline {\n                        x\n                        y\n                        z\n                    }\n                    top\n                    bottom\n                }\n            }\n            ...on TaskObjectiveSkill {\n                skillLevel {\n                    name\n                    level\n                }\n            }\n            ...on TaskObjectiveTaskStatus {\n                task {\n                    id\n                }\n                status\n            }\n            ...on TaskObjectiveTraderLevel {\n                trader {\n                    id\n                }\n                level\n            }\n            ...on TaskObjectiveTraderStanding {\n                trader {\n                    id\n                }\n                compareMethod\n                value\n            }\n            ...on TaskObjectiveUseItem {\n                useAny {\n                    id\n                }\n                compareMethod\n                count\n                zoneNames\n                zones {\n                    id\n                    map {\n                        id\n                    }\n                    position {\n                        x\n                        y\n                        z\n                    }\n                    outline {\n                        x\n                        y\n                        z\n                    }\n                    top\n                    bottom\n                }\n            }\n        }\n        fragment taskRewardFragment on TaskRewards {\n            traderStanding {\n                trader {\n                    id\n                }\n                standing\n            }\n            items {\n                item {\n                    id\n                    containsItems {\n                        item {\n                            id\n                        }\n                        count\n                    }\n                }\n                count\n                attributes {\n                    name\n                    value\n                }\n            }\n            offerUnlock {\n                trader {\n                    id\n                }\n                level\n                item {\n                    id\n                }\n            }\n            craftUnlock {\n                id\n                station {\n                    id\n                }\n                level\n                rewardItems {\n                    item {\n                        id\n                    }\n                    count\n                }\n            }\n            skillLevelReward {\n                name\n                level\n            }\n            traderUnlock {\n                id\n            }\n        }"),
        **query_tarkov_dev('''query TarkovDevItems {\n                items(lang: zh, limit: 10000, offset: 0) {\n                    id\n                    bsgCategoryId\n                    categories {\n                        id\n                        name\n                        normalizedName\n                    }\n                    name\n                    shortName\n                    basePrice\n                    normalizedName\n                    backgroundColor\n                    types\n                    width\n                    height\n                    weight\n                    avg24hPrice\n                    wikiLink\n                    changeLast48h\n                    changeLast48hPercent\n                    low24hPrice\n                    high24hPrice\n                    lastLowPrice\n                    gridImageLink\n                    iconLink\n                    baseImageLink\n                    image512pxLink\n                    image8xLink\n                    updated\n                    sellFor {\n                        ...ItemPriceFragment\n                    }\n                    buyFor {\n                        ...ItemPriceFragment\n                    }\n                    containsItems {\n                        count\n                        item {\n                            id\n                        }\n                    }\n                    properties {\n                        __typename\n                        ...on ItemPropertiesAmmo {\n                            caliber\n                            damage\n                            projectileCount\n                            penetrationPower\n                            armorDamage\n                            fragmentationChance\n                            ammoType\n                        }\n                        ...on ItemPropertiesArmor {\n                            class\n                            material {\n                                id\n                                name\n                            }\n                            zones\n                            durability\n                            ergoPenalty\n                            speedPenalty\n                            turnPenalty\n                        }\n                        ...on ItemPropertiesArmorAttachment {\n                            class\n                            material {\n                                id\n                                name\n                            }\n                            headZones\n                            durability\n                            ergoPenalty\n                            speedPenalty\n                            turnPenalty\n                        }\n                        ...on ItemPropertiesBackpack {\n                            capacity\n                            grids {\n                                ...GridFragment\n                            }\n                            speedPenalty\n                            turnPenalty\n                            ergoPenalty\n                        }\n                        ...on ItemPropertiesBarrel {\n                            ergonomics\n                            recoilModifier\n                            slots {\n                                ...SlotFragment\n                            }\n                        }\n                        ...on ItemPropertiesChestRig {\n                            capacity\n                            class\n                            material {\n                                id\n                                name\n                            }\n                            zones\n                            durability\n                            ergoPenalty\n                            speedPenalty\n                            turnPenalty\n                            grids {\n                                ...GridFragment\n                            }\n                        }\n                        ...on ItemPropertiesContainer {\n                            capacity\n                            grids {\n                                ...GridFragment\n                            }\n                        }\n                        ...on ItemPropertiesFoodDrink {\n                            energy\n                            hydration\n                            units\n                            stimEffects {\n                                ...StimEffectFragment\n                            }\n                        }\n                        ...on ItemPropertiesGlasses {\n                            class\n                            durability\n                            blindnessProtection\n                            material {\n                                id\n                                name\n                            }\n                        }\n                        ...on ItemPropertiesGrenade {\n                            type\n                            fuse\n                            maxExplosionDistance\n                            fragments\n                        }\n                        ...on ItemPropertiesHeadphone {\n                            ambientVolume\n                            distortion\n                            distanceModifier\n                        }\n                        ...on ItemPropertiesHelmet {\n                            class\n                            material {\n                                id\n                                name\n                            }\n                            headZones\n                            durability\n                            ergoPenalty\n                            speedPenalty\n                            turnPenalty\n                            deafening\n                            blocksHeadset\n                            ricochetY\n                            slots {\n                                ...SlotFragment\n                            }\n                        }\n                        ...on ItemPropertiesKey {\n                            uses\n                        }\n                        ...on ItemPropertiesMagazine {\n                            capacity\n                            malfunctionChance\n                            ergonomics\n                            recoilModifier\n                            capacity\n                            loadModifier\n                            ammoCheckModifier\n                        }\n                        ...on ItemPropertiesMedicalItem {\n                            uses\n                            useTime\n                            cures\n                        }\n                        ...on ItemPropertiesMedKit {\n                            hitpoints\n                            useTime\n                            maxHealPerUse\n                            cures\n                            hpCostLightBleeding\n                            hpCostHeavyBleeding\n                        }\n                        ...on ItemPropertiesPainkiller {\n                            uses\n                            useTime\n                            cures\n                            painkillerDuration\n                            energyImpact\n                            hydrationImpact\n                        }\n                        ...on ItemPropertiesPreset {\n                            baseItem {\n                                id\n                                name\n                                normalizedName\n                                properties {\n                                    ...on ItemPropertiesWeapon {\n                                        defaultPreset {\n                                            id\n                                        }\n                                    }\n                                }\n                            }\n                            ergonomics\n                            recoilVertical\n                            recoilHorizontal\n                        }\n                        ...on ItemPropertiesResource {\n                            units\n                        }\n                        ...on ItemPropertiesScope {\n                            ergonomics\n                            recoilModifier\n                            zoomLevels\n                        }\n                        ...on ItemPropertiesStim {\n                            cures\n                            useTime\n                            stimEffects {\n                                ...StimEffectFragment\n                            }\n                        }\n                        ...on ItemPropertiesSurgicalKit {\n                            uses\n                            useTime\n                            cures\n                            minLimbHealth\n                            maxLimbHealth\n                        }\n                        ...on ItemPropertiesWeapon {\n                            caliber\n                            effectiveDistance\n                            ergonomics\n                            fireModes\n                            fireRate\n                            recoilVertical\n                            recoilHorizontal\n                            sightingRange\n                            recoilAngle\n                            recoilDispersion\n                            convergence\n                            cameraRecoil\n                            slots {\n                                ...SlotFragment\n                            }\n                            defaultPreset {\n                                id\n                            }\n                            presets {\n                                id\n                            }\n                        }\n                        ...on ItemPropertiesWeaponMod {\n                            ergonomics\n                            recoilModifier\n                            slots {\n                                ...SlotFragment\n                            }\n                        }\n                    }\n                }\n            }\n            fragment GridFragment on ItemStorageGrid {\n                width\n                height\n                filters {\n                    allowedCategories {\n                        id\n                    }\n                    allowedItems {\n                        id\n                    }\n                    excludedCategories {\n                        id\n                    }\n                    excludedItems {\n                        id\n                    }\n                }\n            }\n            fragment SlotFragment on ItemSlot {\n                filters {\n                    allowedCategories {\n                        id\n                    }\n                    allowedItems {\n                        id\n                    }\n                    excludedCategories {\n                        id\n                    }\n                    excludedItems {\n                        id\n                    }\n                }\n            }\n            fragment ItemPriceFragment on ItemPrice {\n                vendor {\n                    name\n                    normalizedName\n                    __typename\n                    ...on TraderOffer {\n                        trader {\n                            id\n                        }\n                        minTraderLevel\n                        taskUnlock {\n                            id\n                            tarkovDataId\n                            name\n                        }\n                    }\n                }\n                price\n                currency\n                priceRUB\n                requirements {\n                    type\n                    value\n                }\n            }\n            fragment StimEffectFragment on StimEffect {\n                type\n                chance\n                delay\n                duration\n                value\n                percent\n                skillName\n            }'''),
    }
    return res


if os.path.exists(TARKOV_DATA_PATH):
    with open(TARKOV_DATA_PATH, "r") as f:
        TARKOV_DATA = json.load(f)
else:
    TARKOV_DATA = get_tarkov_meta_data()
    with open(TARKOV_DATA_PATH, "w") as f:
        json.dump(TARKOV_DATA, f, ensure_ascii=False, indent=2)


class Item:
    def __init__(self, item_data):
        self.uid = item_data["uid"]
        self.name = item_data["name"]
        self.banned_on_flea = item_data["bannedOnFlea"]
        self.have_market_data = item_data["haveMarketData"]
        self.short_name = item_data["shortName"]
        self.price = item_data["price"]
        self.avg24h_price = item_data["avg24hPrice"]
        self.avg7d_price = item_data["avg7daysPrice"]
        self.trader_name = item_data["traderName"]
        self.trader_price = item_data["traderPrice"]
        self.trader_price_cur = item_data["traderPriceCur"]
        self.trader_price_rub = item_data["traderPriceRub"]
        self.updated = datetime.datetime.fromisoformat(item_data["updated"][:-1])
        self.slots = item_data["slots"]
        self.diff24h = item_data["diff24h"]
        self.diff7days = item_data["diff7days"]
        self.icon = item_data["icon"]
        self.link = item_data["link"]
        self.wiki_link = item_data["wikiLink"]
        self.img_url = item_data["img"]
        self.img_big_url = item_data["imgBig"]
        self.bsg_id = item_data["bsgId"]
        self.is_functional = item_data["isFunctional"]
        self.reference = item_data["reference"]


def get_market_item(item_name, pve=False):
    '''
    params:
        item_name: str
    return:
        res: list[item]
    '''
    url = f"https://api.tarkov-market.app/api/v1{'/pve' if pve else ''}/item"
    data = {
        "q": item_name,
        "lang": "cn",
    }
    headers = {
        "x-api-key": TARKOV_MARKET_SECRET,
    }
    res = requests.post(url, json=data, headers=headers, proxies=proxies)
    try:
        res = res.json()
    except Exception as e:
        raise Exception(f"Failed to get market item: {res.text}")

    items = [Item(x) for x in res]
    for item in items:
        if item.name == item_name:
            return [item]

    return items


def search_item_quest_use(item_bsg_id):
    
    res = []
    for task in TARKOV_DATA['tasks']:
        for obj in task.get('objectives', []):
            if obj.get('type') != "giveItem":
                continue
            if obj.get('items', [{}])[0].get('id') == item_bsg_id:
                tmp_name = TRADER_CN_NAMES.get(task['trader']['name'], task['trader']['name'])
                tmp_str = f"[{tmp_name}][Lv.{task['minPlayerLevel']}][{task['name']}] {obj['description']} x{obj['count']}"
                res.append(tmp_str)
    return "\n".join(res)


def search_item_hideout_use(item_bsg_id):
    res = []
    for station in TARKOV_DATA['hideoutStations']:
        for level in station['levels']:
            for item in level['itemRequirements']:
                if item['item']['id'] == item_bsg_id:
                    tmp_name = HIDEOUT_CN_NAMES.get(station['name'], station['name'])
                    tmp_str = f"[{tmp_name}][Lv.{level['level']}] {item['item']['name']} x{item['quantity']}"
                    res.append(tmp_str)
    return "\n".join(res)


def search_item(item_name_cn, pve=False):
    items = get_market_item(item_name_cn, pve=pve)
    if len(items) == 0:
        return "未找到该物品"
    elif len(items) > 1:
        res = []
        for item in items:
            if item.banned_on_flea:
                tmp_str = f"[不可跳蚤交易]{item.name}"
            elif not item.have_market_data:
                tmp_str = f"[无市场数据]{item.name}"
            else:
                tmp_str = f"{item.name} - {item.price} RUB ({item.diff24h}% in 24h / {item.diff7days}% in 7d)"
            res.append(tmp_str)
        return "\n".join(res)
    else:
        item = items[0]
        res = f"{item.name} - {item.price} RUB ({item.diff24h}% in 24h / {item.diff7days}% in 7d)"
        if item.banned_on_flea:
            res += f"\n[不可跳蚤交易]"
        elif not item.have_market_data:
            res += f"\n[无市场数据]"
        else:
            res += f"\n市场24H均价: {item.avg24h_price} RUB | 市场7日均价: {item.avg7d_price} RUB"
        trader_name = TRADER_CN_NAMES.get(item.trader_name, item.trader_name)
        res += f"\n{trader_name}收购价: {item.trader_price}{item.trader_price_cur}"
        res += f"\n更新时间: {item.updated}"
        res += f"\nWiki: {item.wiki_link}"

        quest_data = search_item_quest_use(item.bsg_id)
        if quest_data:
            res += f"\n\n任务使用:\n{quest_data}"
        hideout_data = search_item_hideout_use(item.bsg_id)
        if hideout_data:
            res += f"\n\n藏身处使用:\n{hideout_data}"
        craft_data = search_craft(item.bsg_id)
        if craft_data:
            res += f"\n\n合成配方:\n{craft_data}"
        return res


def search_item_json(item_name):
    res = []
    for item in TARKOV_DATA['items']:
        if item_name in item['name']:
            res.append(item)
    return res


def get_quest(quest_id):
    for task in TARKOV_DATA['tasks']:
        if task['id'] == quest_id:
            return task
    return {'name': '[未找到]'}


def get_item(item_id):
    for item in TARKOV_DATA['items']:
        if item['id'] == item_id:
            return item
    return {'name': '[未找到]'}


def get_station(station_id):
    for station in TARKOV_DATA['hideoutStations']:
        if station['id'] == station_id:
            return station
    return {'name': '[未找到]'}


def search_quest(quest_name):
    quests = []
    for task in TARKOV_DATA['tasks']:
        if quest_name == task['name']:
            quests = [task]
            break
        elif quest_name in task['name']:
            quests.append(task)

    if len(quests) > 1:
        res = []
        for quest in quests:
            tmp_str = f"[{TRADER_CN_NAMES.get(quest['trader']['name'], quest['trader']['name'])}][Lv.{quest['minPlayerLevel']}] {quest['name']}"
            res.append(tmp_str)
        return '\n'.join(res)
    else:
        quest = quests[0]
        res = f"{quest['name']} - Lv.{quest['minPlayerLevel']} - {TRADER_CN_NAMES.get(quest['trader']['name'], quest['trader']['name'])}"
        res += f"\n地图: {quest['map']['name'] if quest.get('map') else '任意地图'}"
        res += f"\n经验: {quest['experience']}"
        res += f"\nWiki: {quest.get('wikiLink', 'None')}"
        res += f"\n前置任务"
        for obj in quest['taskRequirements']:
            obj_q = get_quest(obj['task']['id'])
            res += f"\n    - {obj_q['name']} [{TRADER_CN_NAMES.get(obj_q['trader']['name'], obj_q['trader']['name'])}][Lv.{obj_q['minPlayerLevel']}]]" # type: ignore
        res += f"\n任务内容:"
        for obj in quest['objectives']:
            res += f"\n    - {obj['description']}" + (f" x{obj['count']}" if obj.get('count') else "")
        res += f"\n任务奖励:"
        for obj in quest['finishRewards']['items']:
            res += f"\n    - {get_item(obj['item']['id'])['name']} x{obj['count']}"
    return res


def search_craft(item_bsg_id):
    res = []
    for craft in TARKOV_DATA['crafts']:
        for item in craft['requiredItems']:
            if item['item']['id'] == item_bsg_id:
                tmp_str = f"[{get_station(craft['station']['id'])['name']}][Lv.{craft['level']}]"
                for reward_item in craft['rewardItems']:
                    tmp_str += f" x{item['count']} -> {get_item(reward_item['item']['id'])['name']} x{reward_item['count']}"
                res.append(tmp_str)
                break
    return "\n".join(res)


if __name__ == "__main__":
    print(search_item("热成像", pve=False))
    # print(search_item_json("5.56")[0]['id'])
    # print(search_craft(get_market_item('火药')[0].bsg_id))
    # print(search_quest("奢靡人生"))
