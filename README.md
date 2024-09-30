# 大黄狗

Mirai + Nonebot2实现
并且为任何可能的框架迁移做好准备

[![在爱发电支持我](https://afdian.moeci.com/1/badge.svg)](https://afdian.com/a/ToogleBot)

## 安装

```plain
安装教程只包含mac/linux
windows请自己研究配置
```

1. 确保安装python-devel
2. 升级pip，`python3 -m pip install -U pip setuptools`
3. 安装python依赖，`python3 -m pip install -r requirements.txt`
4. 安装mirai，在`./mirai/`下运行`./install.sh`
5. 如下配置mirai账号登陆信息，在`./mirai/config/Console/AutoLogin.yml`中

``` yml
accounts: 
  - # 账号, 现只支持 QQ 数字账号
    account: 123456789
    password: 
      # 密码种类, 可选 PLAIN 或 MD5
      kind: PLAIN
      # 密码内容, PLAIN 时为密码文本, MD5 时为 16 进制
      value: xxxxxxx
    # 账号配置. 可用配置列表 (注意大小写):
    # "protocol": "ANDROID_PHONE" / "ANDROID_PAD" / "ANDROID_WATCH" / "MACOS" / "IPAD"
    configuration: 
      protocol: ANDROID_PAD # 安卓PAD协议较为稳定
```

6. 如下配置mirai-api-http，在`./mirai/config/net.mamoe.mirai-api-http/setting.yml`中，注意使用websocket

``` yml
adapters: 
  - http
  - ws
debug: false
enableVerify: true
verifyKey: xxxxxxxx # mirai密码
singleMode: true
cacheSize: 4096
persistenceFactory: 'built-in'
adapterSettings:
  http:
    host: localhost
    port: 5701
    cors: [*]

  ws:
    host: localhost
    port: 5700
```

7. 如下配置`.env`

```ini
ENVIRONMENT=dev
VERIFY_KEY= xxxxxxxxx         # mirai-api-http密钥
driver=~fastapi+~websockets

CONCURRENCY=true              # 是否matcher并行模式（同一消息多个触发）
MIRAI_HOST=127.0.0.1          # mirai-api-http地址
MIRAI_HTTP_PORT=5700          # mirai-api-http http端口
MIRAI_PORT=5700               # mirai-api-http ws端口
MIRAI_QQ=["123456789"]        # 登陆QQ号
SUPERUSERS=["123456789"]      # 管理员QQ号

# 其他单独插件配置，加载时显示提示
```

## 运行

### 脚本启动

`./start.sh`

### 手动启动（便于debug）

1. 进入mirai目录，启动mirai服务，`./mcl`
2. 启动nonebot服务，`python3 -m nb_cli run`

## Docker使用

TODO

## 功能

```python
<class 'toogle.plugins.currencyExchange.CurrencyExchange'>: 货币转换
<class 'toogle.plugins.dice.Dice'>: 骰子
<class 'toogle.plugins.remaking.GetRemake'>: 科学remake
<class 'toogle.plugins.runPython.RunPython'>: Python解释器
<class 'toogle.plugins.online_ai.GetAICompose'>: AI画图
<class 'toogle.plugins.online_ai.GetMidjourney'>: Midjourney生成图片
<class 'toogle.plugins.waifu.GetRandomAnimeFemale'>: 随机ACG老婆
<class 'toogle.plugins.economy.Balance'>: 余额
<class 'toogle.plugins.economy.Membership'>: 大黄狗赞助
<class 'toogle.plugins.tools.AStock'>: A股详情查询
<class 'toogle.plugins.tools.AnimeDownloadSearch'>: 动漫下载搜索
<class 'toogle.plugins.tools.AnimeSchedule'>: 当季新番
<class 'toogle.plugins.tools.BaiduIndex'>: 百度指数
<class 'toogle.plugins.tools.DateCalculator'>: 日期计算器
<class 'toogle.plugins.tools.FilmDownloadSearch'>: 影视下载搜索
<class 'toogle.plugins.tools.GetRainfallWeatherGraph'>: 全国降水天气预告图
<class 'toogle.plugins.tools.HealthCalculator'>: 健康计算器
<class 'toogle.plugins.tools.PCBenchCompare'>: PC硬件对比
<class 'toogle.plugins.admin.Mute'>: 禁用成员
<class 'toogle.plugins.other.BaseballGame'>: 模拟棒球比赛
<class 'toogle.plugins.other.CSGOBuff'>: CSGO Buff饰品查询
<class 'toogle.plugins.other.CSGORandomCase'>: CSGO开箱
<class 'toogle.plugins.other.Diablo4Tracker'>: D4 event tracker
<class 'toogle.plugins.other.JokingHazard'>: Joking Hazard
<class 'toogle.plugins.other.MagnetParse'>: 磁链内容解析
<class 'toogle.plugins.other.MarvelSnapZone'>: 漫威终极逆转Snap工具
<class 'toogle.plugins.other.MinecraftRCON'>: Minecraft服务器RCON
<class 'toogle.plugins.other.NFSWorNot'>: 判断色图
<class 'toogle.plugins.other.RaceHorse'>: 模拟赛马
<class 'toogle.plugins.other.RandomAlbum'>: 随机专辑
<class 'toogle.plugins.other.TarkovSearch'>: 塔科夫查询
<class 'toogle.plugins.other.ToogleCSServer'>: CS服务器相关
<class 'toogle.plugins.gpt.GetOpenAIConversation'>: OpenAI对话
<class 'toogle.plugins.pic.GetQutu'>: 趣图
<class 'toogle.plugins.pic.HistoryTu'>: 黑历史
<class 'toogle.plugins.pic.LongTu'>: 随机龙图
<class 'toogle.plugins.pic.ReverseGIF'>: 反转GIF
<class 'toogle.plugins.pic.Tarrot'>: 塔罗牌
<class 'toogle.plugins.wt.WTDatamine'>: 战雷拆包数据查询
<class 'toogle.plugins.wt.WTVehicleLine'>: 战雷开线资源查询
<class 'toogle.plugins.wt.WTWinRate'>: 战雷历史模式国家胜率查询
<class 'toogle.plugins.gpt.WhatIs'>: 大黄狗有问必答
<class 'toogle.plugins.setu.GetLuck'>: 每日运势
<class 'toogle.plugins.debug.AsyncDebug'>: 异步测试
<class 'toogle.plugins.debug.CounterPlugin'>: 调试计数器
<class 'toogle.plugins.debug.DarkstarServerPing'>: Stormworks暗星服务器状态查询
<class 'toogle.plugins.debug.DebugPlugin'>: 调试用插件
<class 'toogle.plugins.debug.PoliticsOrNot'>: 调试用插件
<class 'toogle.plugins.debug.RecallDebugPlugin'>: 撤回debug
<class 'toogle.plugins.debug.ToogleWorldDebug'>: 异步测试
<class 'toogle.plugins.debug.WitsAndWagers'>: 猜来猜趣简化版
<class 'toogle.plugins.trpg.CustomDiceTable'>: 创建自定义骰表
<class 'toogle.plugins.trpg.DPRCalculator'>: DND5E DPR计算器
<class 'toogle.plugins.trpg.Search5ECHM'>: DND5E 天麟不全书查询
<class 'toogle.plugins.trpg.Search5EMagic'>: DND5E 魔法查询
<class 'toogle.plugins.schedule.CreateSchedule'>: 创建定时
<class 'toogle.plugins.schedule.DailySetuRanking'>: 每日色图排行
<class 'toogle.plugins.math.Calculator'>: 计算器
<class 'toogle.plugins.math.FastFallCal'>: 快速坠落时间计算
<class 'toogle.plugins.math.FastPythagorean'>: 快速勾股计算
<class 'toogle.plugins.math.Mathematica'>: 数学绘图
<class 'toogle.plugins.math.UnitConversion'>: 单位转换
<class 'toogle.plugins.math.WolframAlpha'>: Wolfram Alpha
<class 'toogle.plugins.basic.EatWhat'>: 吃什么
<class 'toogle.plugins.basic.HelpMeSelect'>: 随机选择
<class 'toogle.plugins.basic.Lottery'>: 抽奖
<class 'toogle.plugins.basic.NowTime'>: 世界时间
<class 'toogle.plugins.basic.SeeRecall'>: 反撤回
<class 'toogle.plugins.basic.UpdatePersonalInfo'>: 更新群聊个人信息
<class 'toogle.plugins.basic.Vote'>: 投票
```
