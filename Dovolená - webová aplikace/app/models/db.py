# app/models/db.py

import sqlite3
from contextlib import contextmanager
from typing import Iterator

#
# KONFIGURACE DATABÁZE
#
DB_PATH = "app/data/vacation.db"


#
# KONTEXTOVÝ MANAŽER PRO DATABÁZOVÉ PŘIPOJENÍ
#
@contextmanager
def open_conn() -> Iterator[sqlite3.Connection]:
    conn = None
    try:
        conn = sqlite3.connect(
            DB_PATH,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON") 
        yield conn
        conn.commit()
        
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise e 
        
    finally:
        if conn:
            conn.close()