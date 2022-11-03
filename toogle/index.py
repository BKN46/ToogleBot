from toogle.nonebot2_adapter import PluginWrapper
from toogle.plugins import (
    dice,
    currencyExchange
)

export_plugins = [ PluginWrapper(plugin) for plugin in [
    dice.Dice,
    currencyExchange.CurrencyExchange
]]
