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
  - ws
debug: false
enableVerify: true
verifyKey: xxxxxxxx # mirai密码
singleMode: false
cacheSize: 4096
persistenceFactory: 'built-in'
adapterSettings:
  ws:
    host: localhost
    port: 5700
```

7. 如下配置`.env`

```ini
ENVIRONMENT=dev
VERIFY_KEY= xxxxxxxxx         # mirai-api-http密钥
driver=~fastapi+~websockets

CONCURRENCY=false             # 是否matcher并行模式（同一消息多个触发）
MIRAI_HOST=127.0.0.1          # mirai-api-http地址
MIRAI_PORT=5700               # mirai-api-http端口
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

- [ ] 基础功能
  - [x] Dice
  - [x] Markov
  - [x] CurrencyExchange
  - [x] GetHelp
  - [x] RunPython
  - [x] Mathematica
  - [x] Wolfram Alpha
  - [x] HelpMeSelect
  - [x] Swear
  - [x] Calculator
  - [x] NowTime
  - [x] GetRemake
  - [x] Lottery
- [x] DND功能
  - [x] Search5EMagic
  - [x] Search5ECHM
  - [x] FastPythagorean
  - [x] UnitConversion
  - [x] FastFallCal
  - [x] CustomDiceTable
- [x] 图片相关
  - [x] GetSetu
  - [x] GetQutu
  - [x] GetLuck
  - [x] GetRandomAnimeFemale
  - [x] LongTu
  - [x] GetAICompose
  - [x] HistoryTu
- [ ] 定时
  - [ ] SetScheduler
- [ ] 工具
  - [x] ThunderSkill
  - [x] WTVehicleLine
  - [x] WTWinRate
  - [x] WTDatamine
  - [ ] ChatStatic
