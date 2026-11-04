# -*- coding: utf-8 -*-
"""SQLite 数据访问层：连接、初始化与各类记录表结构。"""

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from .config import BASE_DIR, DB_PATH, LEGACY_DB_FILENAME


def migrate_legacy_database():
    """旧版 ``liuyao.sqlite3`` 存在而新库缺失时，自动复制一份以保留历史记录。

    返回是否执行了迁移。
    """
    db_file = Path(DB_PATH)
    legacy_file = Path(BASE_DIR) / LEGACY_DB_FILENAME

    if db_file.exists() or not legacy_file.exists():
        return False
    if legacy_file.resolve() == db_file.resolve():
        return False

    db_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(legacy_file, db_file)
    print(f"检测到旧版数据库 {legacy_file.name}，已自动迁移为 {db_file.name}")
    return True


def get_connection():
    """Return a SQLite connection configured for dict-like row access."""
    migrate_legacy_database()

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


def ensure_bazi_table(conn):
    """Ensure the BaZi record table exists (single table, independent of year tables)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bazi_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            时间 TEXT,
            性别 TEXT,
            姓名 TEXT,
            年干 TEXT,
            年支 TEXT,
            月干 TEXT,
            月支 TEXT,
            日干 TEXT,
            日支 TEXT,
            时干 TEXT,
            时支 TEXT,
            备注 TEXT,
            标签 TEXT,
            校正分钟 TEXT,
            时柱未知 TEXT
        )
        """
    )

    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(bazi_records)").fetchall()
    }
    if "标签" not in columns:
        conn.execute("ALTER TABLE bazi_records ADD COLUMN 标签 TEXT")
    if "校正分钟" not in columns:
        conn.execute("ALTER TABLE bazi_records ADD COLUMN 校正分钟 TEXT")
    if "时柱未知" not in columns:
        conn.execute("ALTER TABLE bazi_records ADD COLUMN 时柱未知 TEXT")

    return "bazi_records"


def ensure_qimen_table(conn):
    """Ensure the QiMen record table exists (single table, independent of year tables)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS qimen_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            时间 TEXT,
            方法 TEXT,
            标的 TEXT,
            问事 TEXT,
            地点 TEXT,
            目的 TEXT,
            局数 TEXT,
            备注 TEXT,
            标签 TEXT,
            取法 TEXT
        )
        """
    )

    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(qimen_records)").fetchall()
    }
    for name in ("方法", "标的", "问事", "地点", "目的", "局数", "备注", "标签", "取法"):
        if name not in columns:
            conn.execute(f"ALTER TABLE qimen_records ADD COLUMN {name} TEXT")

    return "qimen_records"


def ensure_ziwei_table(conn):
    """Ensure the ZiWeiDouShu record table exists (single table).

    紫微斗数排盘在浏览器端由 ``iztro`` 完成，因此服务端只保存出生信息与
    少量盘面摘要，「时间」即出生时间，用于重新排盘。
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ziwei_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            时间 TEXT,
            姓名 TEXT,
            性别 TEXT,
            四柱 TEXT,
            五行局 TEXT,
            命主 TEXT,
            身主 TEXT,
            标签 TEXT,
            备注 TEXT,
            闰月调整 TEXT,
            流派 TEXT
        )
        """
    )

    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(ziwei_records)").fetchall()
    }
    for name in (
        "姓名", "性别", "四柱", "五行局", "命主", "身主",
        "标签", "备注", "闰月调整", "流派",
    ):
        if name not in columns:
            conn.execute(f"ALTER TABLE ziwei_records ADD COLUMN {name} TEXT")

    return "ziwei_records"


def ensure_xiaoliuren_table(conn):
    """Ensure the XiaoLiuRen record table exists (single table).

    小六壬盘面由「时间 + 流派 + 起课方式 + 报数」决定，因此只存这几项，
    载入时重算，避免盘面字段与算法版本脱节。数字起课的盘面不依赖农历
    日（江氏）或月日时（道传），必须与「报数」一并回放，否则重算会走
    时间起课而得到另一张盘。
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS xiaoliuren_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            时间 TEXT,
            流派 TEXT,
            起课方式 TEXT,
            报数 TEXT,
            标的 TEXT,
            备注 TEXT,
            标签 TEXT,
            农历 TEXT,
            时辰 TEXT,
            摘要 TEXT
        )
        """
    )

    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(xiaoliuren_records)").fetchall()
    }
    for name in ("流派", "起课方式", "报数", "标的", "备注", "标签", "农历", "时辰", "摘要"):
        if name not in columns:
            conn.execute(f"ALTER TABLE xiaoliuren_records ADD COLUMN {name} TEXT")

    return "xiaoliuren_records"


def ensure_meihua_table(conn):
    """梅花易数记录表。

    盘面完全由「起卦时刻 + 起卦方式 + 起卦参数」决定，因此只保存这些输入，
    载入历史时按保存参数重算，不存整张盘。参数以 JSON 存于 ``参数`` 列
    （报数、手动指定的上下卦与动爻、年支分界）。
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meihua_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            时间 TEXT,
            起卦方式 TEXT,
            参数 TEXT,
            问事 TEXT,
            标的 TEXT,
            备注 TEXT,
            标签 TEXT,
            本卦 TEXT,
            摘要 TEXT
        )
        """
    )

    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(meihua_records)").fetchall()
    }
    for name in ("起卦方式", "参数", "问事", "标的", "备注", "标签", "本卦", "摘要"):
        if name not in columns:
            conn.execute(f"ALTER TABLE meihua_records ADD COLUMN {name} TEXT")

    return "meihua_records"


def ensure_daliuren_table(conn):
    """大六壬记录表。

    课式完全由「起课时刻 + 起课方式 + 手动指定的日干支／月将／占时 +
    流派选项」决定，因此只保存这些输入（``参数`` 以 JSON 存储），
    载入历史时按保存参数重算，不存整张盘。
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS daliuren_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            时间 TEXT,
            起课方式 TEXT,
            参数 TEXT,
            问事 TEXT,
            标的 TEXT,
            备注 TEXT,
            标签 TEXT,
            日干支 TEXT,
            课体 TEXT,
            三传 TEXT,
            摘要 TEXT
        )
        """
    )

    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(daliuren_records)").fetchall()
    }
    for name in ("起课方式", "参数", "问事", "标的", "备注", "标签",
                 "日干支", "课体", "三传", "摘要"):
        if name not in columns:
            conn.execute(f"ALTER TABLE daliuren_records ADD COLUMN {name} TEXT")

    return "daliuren_records"


def ensure_mingli_table(conn):
    """Ensure the unified MingLi (命理) record table exists.

    八字与紫微斗数共享同一套「命理档案」：出生信息（姓名/性别/出生时间）为
    公共字段，八字四柱与紫微盘面摘要分别存于各自字段。八字排盘在服务端完成，
    紫微排盘在浏览器端由 ``iztro`` 完成，「时间」即出生时间，用于重新排盘。
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mingli_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            时间 TEXT,
            姓名 TEXT,
            性别 TEXT,
            标签 TEXT,
            备注 TEXT,
            校正分钟 TEXT,
            时柱未知 TEXT,
            年干 TEXT,
            年支 TEXT,
            月干 TEXT,
            月支 TEXT,
            日干 TEXT,
            日支 TEXT,
            时干 TEXT,
            时支 TEXT,
            四柱 TEXT,
            五行局 TEXT,
            命主 TEXT,
            身主 TEXT,
            闰月调整 TEXT,
            流派 TEXT
        )
        """
    )

    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(mingli_records)").fetchall()
    }
    for name in (
        "姓名", "性别", "标签", "备注", "校正分钟", "时柱未知",
        "年干", "年支", "月干", "月支", "日干", "日支", "时干", "时支",
        "四柱", "五行局", "命主", "身主", "闰月调整", "流派",
    ):
        if name not in columns:
            conn.execute(f"ALTER TABLE mingli_records ADD COLUMN {name} TEXT")

    return "mingli_records"


def migrate_to_mingli_table(conn):
    """把旧的 ``bazi_records`` 与 ``ziwei_records`` 合并进 ``mingli_records``。

    仅当 ``mingli_records`` 为空时执行一次，避免重复导入。八字记录与紫微记录
    若姓名+出生时间相同则视为同一档案合并，否则各自独立成条。
    """
    ensure_mingli_table(conn)
    count = conn.execute("SELECT COUNT(*) AS c FROM mingli_records").fetchone()["c"]
    if count:
        return

    # 先导入八字记录
    try:
        bazi_rows = conn.execute("SELECT * FROM bazi_records").fetchall()
    except Exception:
        bazi_rows = []
    for row in bazi_rows:
        conn.execute(
            """
            INSERT INTO mingli_records
            (时间, 姓名, 性别, 标签, 备注, 校正分钟, 时柱未知,
             年干, 年支, 月干, 月支, 日干, 日支, 时干, 时支)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["时间"], row["姓名"], row["性别"], row["标签"], row["备注"],
                row["校正分钟"], row["时柱未知"],
                row["年干"], row["年支"], row["月干"], row["月支"],
                row["日干"], row["日支"], row["时干"], row["时支"],
            ),
        )

    # 再导入紫微记录，按「姓名 + 出生时间」尝试合并到已有八字档案
    try:
        ziwei_rows = conn.execute("SELECT * FROM ziwei_records").fetchall()
    except Exception:
        ziwei_rows = []
    for row in ziwei_rows:
        existing = conn.execute(
            "SELECT id FROM mingli_records WHERE 姓名 = ? AND 时间 = ?",
            (row["姓名"], row["时间"]),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE mingli_records SET
                    四柱 = ?, 五行局 = ?, 命主 = ?, 身主 = ?,
                    闰月调整 = ?, 流派 = ?
                WHERE id = ?
                """,
                (
                    row["四柱"], row["五行局"], row["命主"], row["身主"],
                    row["闰月调整"], row["流派"], existing["id"],
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO mingli_records
                (时间, 姓名, 性别, 标签, 备注, 四柱, 五行局, 命主, 身主, 闰月调整, 流派)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["时间"], row["姓名"], row["性别"], row["标签"], row["备注"],
                    row["四柱"], row["五行局"], row["命主"], row["身主"],
                    row["闰月调整"], row["流派"],
                ),
            )

    conn.commit()


def initialize_database(year=None):
    """Ensure the local database file and the target year table are ready."""
    target_year = year or datetime.now().year

    with get_connection() as conn:
        table_name = ensure_year_table(conn, target_year)
        ensure_bazi_table(conn)
        ensure_qimen_table(conn)
        ensure_ziwei_table(conn)
        ensure_xiaoliuren_table(conn)
        ensure_meihua_table(conn)
        ensure_daliuren_table(conn)
        ensure_mingli_table(conn)
        migrate_to_mingli_table(conn)
        conn.commit()

    return Path(DB_PATH), table_name
