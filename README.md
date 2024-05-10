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

- [x] 基础功能
  - [x] Dice 带有期望计算的多功能骰子
  - [ ] Markov 基于马尔可夫的对话机器人
  - [x] CurrencyExchange 货币转换
  - [x] GetHelp 帮助
  - [x] RunPython Python运行时
  - [x] Mathematica 数学画图
  - [x] Wolfram Alpha 高等数学计算
  - [x] HelpMeSelect 解决选择困难症
  - [x] Swear 说藏话
  - [x] Calculator 科学计算器
  - [x] NowTime 世界时间
  - [x] GetRemake 基于世界银行统计数据的科学Remake
  - [x] Lottery 抽奖功能
- [X] AI相关
  - [x] ChatGPT OpenAI GPT接口调用
  - [x] GetAICompose NovelAI AI画图
- [x] DND功能
  - [x] Search5EMagic 快速搜索DND5E魔法
  - [x] Search5ECHM 快速搜索DND5E天麒不全书
  - [x] FastPythagorean 快速计算勾股定理
  - [x] UnitConversion 单位转换
  - [x] FastFallCal 快速计算掉落时间
  - [x] CustomDiceTable 自定义骰表
  - [x] DPRCalculator DND5E每轮伤害期望计算器
- [x] 图片相关
  - [x] GetSetu 获取setu
  - [x] GetQutu 获取趣图
  - [x] GetLuck 获取每日运势
  - [x] GetRandomAnimeFemale 获取随机动漫角色
  - [x] LongTu 获取龙图
  - [x] HistoryTu 记录黑历史
- [x] 定时
  - [x] SetScheduler 定时运行
  - [x] DailyNews 每日新闻推送
  - [x] HealthCare 提肛喝水小助手
- [ ] 工具
  - [x] ThunderSkill 战雷TS快速战绩查询
  - [x] WTVehicleLine 战雷开线需求查询
  - [x] WTWinRate 战雷当前胜率查询
  - [x] WTDatamine 战雷数据挖掘
  - [ ] ChatStatic 聊天统计信息
