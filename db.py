# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime
from pathlib import Path

from config import DB_PATH


def get_connection():
    """Return a SQLite connection configured for dict-like row access."""
    db_file = Path(DB_PATH)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    return conn


def quote_identifier(identifier):
    """Safely quote a SQLite identifier such as a year table name."""
    return '"' + identifier.replace('"', '""') + '"'


def ensure_year_table(conn, year):
    table_name = f"{year}年"
    quoted_table = quote_identifier(table_name)

    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {quoted_table} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            起卦方式 TEXT,
            时间 TEXT,
            月干 TEXT,
            月支 TEXT,
            日干 TEXT,
            日支 TEXT,
            初爻 TEXT,
            二爻 TEXT,
            三爻 TEXT,
            四爻 TEXT,
            五爻 TEXT,
            上爻 TEXT,
            标的 TEXT,
            用户 TEXT,
            备注 TEXT
        )
        """
    )

    columns = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({quoted_table})").fetchall()
    }
    if "备注" not in columns:
        conn.execute(f"ALTER TABLE {quoted_table} ADD COLUMN 备注 TEXT")

    return table_name


def initialize_database(year=None):
    """Ensure the local database file and the target year table are ready."""
    target_year = year or datetime.now().year

    with get_connection() as conn:
        table_name = ensure_year_table(conn, target_year)
        conn.commit()

    return Path(DB_PATH), table_name
