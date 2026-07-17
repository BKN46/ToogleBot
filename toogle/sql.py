import datetime
import json
import threading
from functools import wraps
from pathlib import Path
from typing import Dict

import sqlite3

from toogle.utils import filter_emoji


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "toogle.db"
SCHEMA_PATH = PROJECT_ROOT / "sqlite.sql"
_SCHEMA_LOCK = threading.Lock()
_SCHEMA_READY = False


def ensure_schema() -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    with _SCHEMA_LOCK:
        if _SCHEMA_READY:
            return
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        with sqlite3.connect(DB_PATH) as db:
            db.executescript(schema)
        _SCHEMA_READY = True


class DatetimeUtils:
    @staticmethod
    def get_now_time():
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def date_parse(date_str):
        return datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")

    @staticmethod
    def is_today(date):
        return datetime.datetime.today().date() == datetime.datetime.fromisoformat(date).date()


def db_connect(func):
    @wraps(func)
    def a_func(*args, **kwargs):
        ensure_schema()
        with sqlite3.connect(DB_PATH) as db:
            cursor = db.cursor()
            return func(*args, db=db, cursor=cursor, **kwargs)

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
    def get_top_remake(db=None, cursor=None):
        sql_cmd = f"SELECT * FROM remake_data ORDER BY score DESC LIMIT 5"
        cursor.execute(sql_cmd) # type: ignore
        return cursor.fetchall() # type: ignore

    @staticmethod
    @db_connect
    def get_low_remake(db=None, cursor=None):
        sql_cmd = f"SELECT * FROM remake_data ORDER BY score ASC LIMIT 5"
        cursor.execute(sql_cmd) # type: ignore
        return cursor.fetchall() # type: ignore
        
    @staticmethod
    def get_user_data(id):
        user = SQLConnection.search("qq_user", {"id": id})
        if user:
            if user[0][7].strip() and user[0][7] != "null":
                data = json.loads(user[0][7]) 
                return data
            return {}
        else:
            SQLConnection.insert_user(id)
            return {}
        
    @staticmethod
    def update_user_data(id, data):
        original_data = SQLConnection.get_user_data(id)
        original_data.update(data)
        SQLConnection.update("qq_user", {"data": json.dumps(original_data)}, {"id": id})


if __name__ == "__main__":
    pass
