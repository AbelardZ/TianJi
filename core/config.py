# -*- coding: utf-8 -*-
"""全局配置：项目根目录与数据库位置。"""

import os
from pathlib import Path

# 项目根目录（本文件位于 <root>/core/config.py）
BASE_DIR = Path(__file__).resolve().parent.parent


def _resolve_db_path():
    """解析数据库路径，默认 <项目根>/tianji.sqlite3。

    环境变量 ``TIANJI_DB_PATH`` 优先；为兼容旧版本，仍接受 ``LIUYAO_DB_PATH``。
    """
    for env_name in ("TIANJI_DB_PATH", "LIUYAO_DB_PATH"):
        value = os.environ.get(env_name)
        if value:
            return Path(value).expanduser()
    return BASE_DIR / "tianji.sqlite3"


DB_PATH = _resolve_db_path()

#：旧版数据库文件名，首次运行时会自动复制迁移为 DB_PATH
LEGACY_DB_FILENAME = "liuyao.sqlite3"

#：模板与静态资源目录
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
