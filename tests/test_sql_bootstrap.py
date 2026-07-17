import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import toogle.sql as sql
from toogle.economy import get_balance


class SqlBootstrapTest(unittest.TestCase):
    def test_empty_database_bootstraps_required_tables(self):
        with tempfile.TemporaryDirectory() as tempdir:
            database = Path(tempdir) / "toogle.db"
            with patch.object(sql, "DB_PATH", database), patch.object(
                sql, "_SCHEMA_READY", False
            ):
                self.assertEqual(get_balance(10001), 0)
                with sqlite3.connect(database) as connection:
                    tables = {
                        row[0]
                        for row in connection.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        )
                    }
                    user = connection.execute(
                        "SELECT id, credit FROM qq_user WHERE id = ?", (10001,)
                    ).fetchone()

        self.assertTrue({"qq_user", "qq_waifu", "remake_data"} <= tables)
        self.assertEqual(user, ("10001", 0))


if __name__ == "__main__":
    unittest.main()
