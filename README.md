# 大黄狗

Mirai + Nonebot2实现
并且为任何可能的框架迁移做好准备

## 安装

```plain
安装教程只包含mac/linux
windows请自己研究配置
```

1. 升级pip，`pip3 install -U pip setuptools`
2. 安装python依赖，`python3 -m pip install -r requirements.txt`
3. 安装mirai，在`./mirai/`下运行`./install.sh`
4. 如下配置`.env`

```ini
ENVIRONMENT=dev
VERIFY_KEY= xxxxxxxxx         # mirai-api-http密钥
driver=~fastapi+~websockets

MIRAI_HOST=127.0.0.1          # mirai-api-http地址
MIRAI_PORT=5700               # mirai-api-http端口
MIRAI_QQ=["123456789"]        # 登陆QQ号
SUPERUSERS=["123456789"]      # 管理员QQ号
```

## Docker使用

TODO

## 原始功能迁移

- [ ] 基础功能
  - [x] Dice
  - [ ] CmdPipe
  - [ ] Markov
  - [x] CurrencyExchange
  - [ ] GetHelp
  - [x] RunPython
  - [x] Mathematica
  - [ ] HelpMeSelect
  - [ ] Swear
  - [x] Calculator
  - [ ] NowTime
  - [ ] DBPedia
- [ ] DND功能
  - [ ] Search5EMagic
  - [ ] Search5ECHM
  - [ ] Hangman5EMagic
  - [ ] FastPythagorean
  - [ ] UnitConversion
  - [ ] FastFallCal
  - [ ] CustomDiceTable
- [ ] 图片相关
  - [ ] GetSetu
  - [ ] GetLastSetuJson
  - [ ] GetQutu
  - [ ] GetLuck
  - [ ] GetNews
  - [ ] GetRandomAnimeFemale
  - [ ] LongTu
  - [ ] GetAICompose
  - [ ] HistoryTu
- [ ] 其他
  - [ ] Sleep
- [ ] 定时
  - [ ] SetScheduler
- [ ] 工具
  - [ ] SWTranslation
  - [ ] SWSpeed
  - [ ] PromoteAuth
  - [ ] ThunderSkill
  - [ ] WTVehicleLine
  - [ ] ChatStatic
- [ ] BKNW
  - [ ] BKNWRegist
  - [ ] GetRemake
