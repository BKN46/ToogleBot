# 大黄狗

Mirai + Nonebot2实现
并且为任何可能的框架迁移做好准备

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

> currencyExchange.CurrencyExchange:  货币转换
> novelai.GetAICompose:  AI画图
> dice.Dice:  骰子
> remaking.GetRemake:  科学remake
> runPython.RunPython:  Python解释器
> waifu.GetRandomAnimeFemale:  随机ACG老婆
> economy.Balance:  余额
> tools.AStock:  A股详情查询
> tools.BaiduIndex:  百度指数
> tools.GetRainfallWeatherGraph:  全国降水天气预告图
> tools.HealthCalculator:  健康计算器
> other.CSGOBuff:  CSGO Buff饰品查询
> other.CSGORandomCase:  CSGO开箱
> other.Diablo4Tracker:  D4 event tracker
> other.JokingHazard:  Joking Hazard
> other.MagnetParse:  磁链内容解析
> other.NFSWorNot:  判断色图
> other.RaceHorse:  模拟赛马
> other.RandomAlbum:  随机专辑
> pic.HistoryTu:  黑历史
> pic.LongTu:  随机龙图
> wt.WTDatamine:  战雷拆包数据查询
> wt.WTVehicleLine:  战雷开线资源查询
> wt.WTWinRate:  战雷历史模式国家胜率查询
> setu.GetLuck:  每日运势
> debug.WitsAndWagers:  猜来猜趣简化版
> trpg.CustomDiceTable:  创建自定义骰表
> trpg.DPRCalculator:  DND5E DPR计算器
> trpg.Search5ECHM:  DND5E 天麟不全书查询
> trpg.Search5EMagic:  DND5E 魔法查询
> schedule.CreateSchedule:  创建定时
> math.Calculator:  计算器
> math.FastFallCal:  快速坠落时间计算
> math.FastPythagorean:  快速勾股计算
> math.Mathematica:  数学绘图
> math.UnitConversion:  单位转换
> math.WolframAlpha:  Wolfram Alpha
> basic.HelpMeSelect:  随机选择
> basic.Lottery:  抽奖
> basic.NowTime:  世界时间
> basic.SeeRecall:  反撤回
> basic.UpdatePersonalInfo:  更新群聊个人信息
