# 大黄狗

Mirai + Nonebot2实现
并且为任何可能的框架迁移做好准备

## 安装

```plain
安装教程只包含mac/linux
windows请自己研究配置
```

1. 升级pip，`python3 -m pip install -U pip setuptools`
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

## 运行

1. 进入mirai目录，启动mirai服务，`./mcl`
2. 启动nonebot服务，`python3 -m nb_cli run`

## Docker使用

TODO

## 原始功能迁移

- [ ] 基础功能
  - [x] Dice
  - [ ] CmdPipe
  - [x] Markov
  - [x] CurrencyExchange
  - [x] GetHelp
  - [x] RunPython
  - [x] Mathematica
  - [x] HelpMeSelect
  - [x] Swear
  - [x] Calculator
  - [x] NowTime
  - [x] GetRemake
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
  - [ ] ChatStatic
