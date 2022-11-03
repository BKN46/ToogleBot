from toogle.nonebot2_adapter import PluginWrapper
from toogle.plugins import (
    dice,
    currencyExchange,
    runPython,
    math,
    basic,
    setu,
    wt,
    dnd,
    pic,
)

export_plugins = [ PluginWrapper(plugin) for plugin in [
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
    dnd.CustomDiceTable,
    dnd.Search5ECHM,
    dnd.Search5EMagic,
    pic.GetQutu,
    pic.LongTu,
]]
