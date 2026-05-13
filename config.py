# -*- coding: utf-8 -*-
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("LIUYAO_DB_PATH", BASE_DIR / "liuyao.sqlite3")).expanduser()
