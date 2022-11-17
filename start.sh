cd mirai
nohup ./mcl > /dev/null 2>&1  &
sleep 5s
cd ..
nohup venv/bin/python3 -m nb_cli run > ./bot.log 2>&1  &
