import datetime
from typing import Dict

import MySQLdb

from toogle.configs import config
from toogle.utils import filter_emoji


class DatetimeUtils:
    @staticmethod
    def get_now_time():
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def date_parse(date_str):
        return datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")

    @staticmethod
    def is_today(date):
        return datetime.datetime.today().date() == date.date()


def db_connect(func):
    def a_func(*args, **kwargs):
        db = MySQLdb.connect(
            config['DBHost'], config['DBUser'], config['DBPassword'], config['DBTable'], charset="utf8"
        )
        cursor = db.cursor()
        res = func(*args, db=db, cursor=cursor, **kwargs)
        db.close()
        return res

    return a_func


def data_str_proc(data_str):
    for k, v in data_str.items():
        if isinstance(v, str):
            data_str[k] = f"'{deqoute(filter_emoji(v))}'"
    return data_str


def deqoute(data_str):
    return data_str.replace("'", "")


class SQLConnection:
    @staticmethod
    @db_connect
    def search(table: str, data: Dict, order="", limit=None, db=None, cursor=None):
        if len(data) > 0:
            sql_cmd = f"SELECT * FROM {table} WHERE {' AND '.join(f'{k} = {v}' for k, v in data.items())}"
        else:
            sql_cmd = f"SELECT * FROM {table}"
        if order:
            sql_cmd += f" ORDER BY {order}"
        if limit:
            sql_cmd += f" LIMIT {limit}"
        cursor.execute(sql_cmd) # type: ignore
        return cursor.fetchall() # type: ignore

    @staticmethod
    @db_connect
    def insert(table, data: Dict, db=None, cursor=None):
        sql_keys, sql_values = [], []
        for k, v in data.items():
            sql_keys.append(f"`{k}`")
            if type(v) == str:
                sql_values.append(f"'{deqoute(filter_emoji(v))}'")
            else:
                sql_values.append(f"{v}")
        sql_cmd = f"INSERT INTO {table} ({', '.join(sql_keys)}) VALUES ({', '.join(sql_values)});"
        try:
            cursor.execute(sql_cmd) # type: ignore
            db.commit() # type: ignore
            return True
        except:
            db.rollback() # type: ignore
            return False

    @staticmethod
    @db_connect
    def update(table: str, data: Dict, search: Dict, db=None, cursor=None):
        data = data_str_proc(data)
        search = data_str_proc(search)
        sql_cmd = (
            f"UPDATE {table} "
            f"SET {' , '.join(f'{(k)} = {(v)}' for k, v in data.items())} "
            f"WHERE {' AND '.join(f'{(k)} = {(v)}' for k, v in search.items())}"
        )
        try:
            cursor.execute(sql_cmd) # type: ignore
            db.commit() # type: ignore
            return True
        except:
            db.rollback() # type: ignore
            return False

    @staticmethod
    @db_connect
    def delete(table: str, data: Dict, db=None, cursor=None):
        sql_cmd = f"DELETE FROM {table} WHERE {' AND '.join(f'{k} = {v}' for k, v in data.items())}"
        try:
            cursor.execute(sql_cmd) # type: ignore
            db.commit() # type: ignore
            return True
        except:
            db.rollback() # type: ignore
            return False

    @staticmethod
    @db_connect
    def get_user(id, db=None, cursor=None):
        sql_cmd = f"SELECT * FROM qq_user WHERE id={id}"
        cursor.execute(sql_cmd) # type: ignore
        res = cursor.fetchall() # type: ignore
        if res:
            return res[0]
        else:
            SQLConnection.insert_user(id)
            return None

    @staticmethod
    @db_connect
    def insert_user(id, db=None, cursor=None):
        sql_cmd = f"INSERT INTO qq_user (id, auth, last_luck, credit) VALUES ('{id}', 1, '{DatetimeUtils.get_now_time()}', 0);"
        try:
            cursor.execute(sql_cmd) # type: ignore
            # 提交到数据库执行
            db.commit() # type: ignore
            return True
        except:
            db.rollback() # type: ignore
            return False

    @staticmethod
    @db_connect
    def update_user(id, content, db=None, cursor=None):
        sql_cmd = f"UPDATE qq_user SET {content} WHERE id={id};"
        try:
            cursor.execute(sql_cmd) # type: ignore
            # 提交到数据库执行
            db.commit() # type: ignore
            return True
        except:
            db.rollback() # type: ignore
            return False

    @staticmethod
    @db_connect
    def insert_crond(
        content,
        creator_id,
        group_id,
        year=-1,
        month=-1,
        day=-1,
        week=-1,
        day_of_week=-1,
        hour=-1,
        minute=-1,
        second=-1,
        db=None,
        cursor=None,
    ):
        sql_cmd = (
            f"INSERT INTO `scheduler` "
            f"(`content`, `year`, `month`, `day`, `week`, `day_of_week`, `hour`, `minute`, `second`, `creator`, `group`) "
            f"VALUES "
            f"('{content}', {year}, {month}, {day}, {week}, {day_of_week}, {hour}, {minute}, {second}, '{creator_id}', '{group_id}');"
        )
        try:
            cursor.execute(sql_cmd) # type: ignore
            # 提交到数据库执行
            db.commit() # type: ignore
            return True
        except Exception as e:
            db.rollback() # type: ignore
            return False

    @staticmethod
    @db_connect
    def get_crond(id=None, db=None, cursor=None):
        sql_cmd = f"SELECT * FROM scheduler"
        if id:
            sql_cmd += f" WHERE creator={id};"
        cursor.execute(sql_cmd) # type: ignore
        res = cursor.fetchall() # type: ignore
        if res:
            return res
        else:
            return

    @staticmethod
    @db_connect
    def del_crond(id, creator, db=None, cursor=None):
        sql_cmd = f"DELETE FROM scheduler WHERE id={id} AND creator={creator};"
        try:
            cursor.execute(sql_cmd) # type: ignore
            db.commit() # type: ignore
            return True
        except:
            db.rollback() # type: ignore
            return False

    @staticmethod
    @db_connect
    def get_top_remake(db=None, cursor=None):
        sql_cmd = f"SELECT * FROM remake_data ORDER BY score DESC LIMIT 5"
        cursor.execute(sql_cmd) # type: ignore
        res = cursor.fetchall() # type: ignore
        if res:
            return res
        else:
            SQLConnection.insert_user(id)
            return None

    @staticmethod
    @db_connect
    def get_low_remake(db=None, cursor=None):
        sql_cmd = f"SELECT * FROM remake_data ORDER BY score ASC LIMIT 5"
        cursor.execute(sql_cmd) # type: ignore
        res = cursor.fetchall() # type: ignore
        if res:
            return res
        else:
            SQLConnection.insert_user(id)
            return None


if __name__ == "__main__":
    # print(datetime.datetime.now())
    # print(SQLConnection.insert_user("752941266"))
    # user_info = SQLConnection.get_user("1149887546")
    # print(DatetimeUtils.is_today(user_info[2]))
    # print(
    #     SQLConnection.update_user(
    #         1149887546, f"last_luck='{DatetimeUtils.get_now_time()}'"
    #     )
    # )
    timer_info = {"year": 2022, "month": 2, "day": 19, "hour": 20, "minute": 0}
    print(SQLConnection.insert_crond("11111", 1149887546, 325353479, **timer_info))
