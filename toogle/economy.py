from contextlib import contextmanager

from toogle.sql import SQLConnection


def get_balance(user_id):
    res = SQLConnection.get_user(user_id)
    if res:
        return res[3]
    else:
        return 0


def give_balance(user_id, amount):
    res = SQLConnection.get_user(user_id)
    SQLConnection.update_user(user_id, f"credit=credit+{amount}")


def take_balance(user_id, amount):
    left = get_balance(user_id)
    if left >= amount:
        SQLConnection.update_user(user_id, f"credit=credit-{amount}")
        return True
    else:
        SQLConnection.update_user(user_id, f"credit=0")
    return False


def has_balance(user_id, amount):
    return get_balance(user_id) >= amount


@contextmanager
def use_balance(user_id, amount):
    try:
        res = has_balance(user_id, amount)
        yield res
        if res:
            SQLConnection.update_user(user_id, f"credit=credit-{amount}")
    except Exception as e:
        pass


def chat_earn(user_id, message: str):
    if len(message) >= 10 and get_balance(user_id) < 15:
        give_balance(user_id, 1)
