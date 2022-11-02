# 大黄狗

Mirai + Nonebot2实现

## 安装

```plain
暂时只支持mac/linux
```

1. 安装nonebot2，`python3 -m pip install nb-cli`
2. 安装mirai，在`./mirai/`下运行`./install.sh`
3. 配置`.env`
  
```env
ENVIRONMENT=dev
VERIFY_KEY= xxxxxxxxx    # mirai-api-http密钥
driver=~fastapi+~websockets

MIRAI_HOST=127.0.0.1    # mirai-api-http地址
MIRAI_PORT=5700    # mirai-api-http端口
MIRAI_QQ=["123456789"]    # 登陆QQ号
SUPERUSERS=["123456789"]    # 管理员QQ号
```

## 原始功能迁移

- [ ] 基础功能
  - [ ] Dice
  - [ ] CmdPipe
  - [ ] Markov
  - [ ] CurrencyExchange
  - [ ] GetHelp
  - [ ] RunPython
  - [ ] Mathematica
  - [ ] HelpMeSelect
  - [ ] Swear
  - [ ] Calculator
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
