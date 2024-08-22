import datetime
import json
import time
from toogle.configs import config
from toogle.economy import get_balance, give_balance
from toogle.message import MessageChain, Plain, At
from toogle.message_handler import MESSAGE_HISTORY
from toogle.nonebot2_adapter import bot_send_message
from toogle.utils import modify_json_file


TRADE_PLANS = {
    "大黄狗小会员": 1,
    "大黄狗大会员": 2,
}


def get_membership_level(qq: int):
    with modify_json_file('afdian') as d:
        if str(qq) in d:
            time_due = datetime.datetime.strptime(d[str(qq)]["time_due"], "%Y-%m-%d %H:%M:%S")
            if time_due < datetime.datetime.now():
                return 0
            else:
                return TRADE_PLANS.get(d[str(qq)]["trade_plan"], 0)
        else:
            return 0


def recv_afdian_msg(msg_json: dict):
    try:
        trade_data = msg_json["data"]["order"]
        trade_no = trade_data["out_trade_no"]
        trade_time = trade_data["create_time"]
        trade_user_id = trade_data["user_id"]
        trade_plan = trade_data["plan_title"]
        trade_qq = trade_data["remark"]
        trade_month = trade_data["month"]
        trade_price = trade_data["total_amount"]
        trade_status = trade_data["status"]
    except Exception as e:
        bot_send_message(
            int(config.get("ADMIN_LIST", [0])[0]),
            MessageChain.plain(f"afdian webhook error: {repr(e)}\n{json.dumps(msg_json, ensure_ascii=False)}"),
            friend=True,
        )
        return
    
    if trade_status != 2:
        return
    
    with modify_json_file('afdian') as d:
        if trade_qq in d:
            time_due = datetime.datetime.strptime(d[trade_qq]["time_due"], "%Y-%m-%d %H:%M:%S")
            time_due += datetime.timedelta(days=30) * int(trade_month)
        else:
            time_due = datetime.datetime.now() + datetime.timedelta(days=30) * int(trade_month)
        d[trade_qq] = {
            "trade_no": trade_no,
            "trade_time": trade_time,
            "trade_user_id": trade_user_id,
            "time_due": time_due.strftime("%Y-%m-%d %H:%M:%S"),
            "trade_price": trade_price,
            "trade_plan": trade_plan,
            "trade_status": trade_status,
        }
    
    try:
        balance_left = get_balance(int(trade_qq))
        target_balance = 3000 if trade_plan == "大黄狗大会员" else 500
        if balance_left < target_balance:
            give_balance(int(trade_qq), target_balance - balance_left)
    except Exception as e:
        bot_send_message(
            int(config.get("ADMIN_LIST", [0])[0]),
            MessageChain.plain(f"membership balance error: {e}\nqq: {trade_qq}"),
            friend=True,
        )

    member_msg_record = MESSAGE_HISTORY.find_qq_last_message(int(trade_qq))
    if member_msg_record:
        member_group = member_msg_record.group.id
        bot_send_message(
            member_group,
            MessageChain.create([
                Plain(f"感谢 "),
                At(int(trade_qq)),
                Plain(f" 赞助大黄狗\n获得 {trade_plan} {trade_month} 个月"),
            ]),
        )

    bot_send_message(
        int(config.get("ADMIN_LIST", [0])[0]),
        MessageChain.plain(f"{trade_qq} 成功购买 {trade_plan} {trade_month} 个月"),
        friend=True,
    )


def set_membership(qq: int, trade_plan: int, time_due: str):
    with modify_json_file('afdian') as d:
        d[str(qq)] = {
            "trade_no": "manual",
            "trade_time": int(time.time()),
            "trade_user_id": "manual",
            "time_due": time_due,
            "trade_price": 0,
            "trade_plan": trade_plan,
            "trade_status": 2,
        }
