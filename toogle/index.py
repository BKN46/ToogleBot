from toogle.nonebot2_adapter import PluginWrapper
from toogle.plugins import (basic, currencyExchange, dice, math, novelai, pic,
                            remaking, runPython, setu, trpg, waifu, wt)

export_plugins = [
    PluginWrapper(plugin)
    for plugin in [
        dice.Dice,
        currencyExchange.CurrencyExchange,
        runPython.RunPython,
        math.Mathematica,
        math.Calculator,
        math.FastFallCal,
        math.FastPythagorean,
        math.UnitConversion,
        basic.HelpMeSelect,
        basic.NowTime,
        basic.Swear,
        setu.GetLuck,
        setu.GetSetu,
        wt.ThunderSkill,
        wt.WTVehicleLine,
        trpg.CustomDiceTable,
        trpg.Search5ECHM,
        trpg.Search5EMagic,
        pic.GetQutu,
        pic.LongTu,
        pic.HistoryTu,
        novelai.GetAICompose,
        waifu.GetRandomAnimeFemale,
        remaking.GetRemake,
    ]
]
