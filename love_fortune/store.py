"""store.py, 해석 데이터베이스 (SQLite, 표준라이브러리 sqlite3).

db/init.sql 이 원본이다. 처음 부를 때 data/fortune.db 를 만들고, init.sql 의
schema_version 이 바뀌었으면 다시 만든다. 다른 사람이 저장소를 받아도 따로 할 일이 없다.
DBeaver 등에서 data/fortune.db 를 열어 볼 수 있다.

해석 데이터는 작아서 한 번 읽어 메모리에 들고 있는다 (요청마다 DB 를 열지 않는다).
"""
from __future__ import annotations

import os
import re
import sqlite3
import threading
from contextlib import closing
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INIT_SQL = ROOT / "db" / "init.sql"
# Vercel 같은 서버리스는 /tmp 말고는 쓸 수 없다
DB_PATH = Path(os.environ.get("SAJU_DB", (Path("/tmp") if os.environ.get("VERCEL") else ROOT / "data") / "fortune.db"))
_LOCK = threading.Lock()


def _script_version() -> str:
    m = re.search(r"'schema_version',\s*'([^']+)'", INIT_SQL.read_text(encoding="utf-8"))
    return m.group(1) if m else "0"


def _db_version(path: Path) -> str | None:
    try:
        with closing(sqlite3.connect(path)) as con:
            row = con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            return row[0] if row else None
    except sqlite3.Error:
        return None


def build(path: Path = DB_PATH) -> Path:
    """init.sql 로 DB 를 새로 만든다 (있으면 지우고)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()
    # 윈도우에서는 연결을 닫아야 파일을 옮길 수 있다 (with sqlite3.connect 는 닫지 않는다)
    with closing(sqlite3.connect(tmp)) as con:
        con.executescript(INIT_SQL.read_text(encoding="utf-8"))
        con.commit()
    tmp.replace(path)
    return path


def ensure(path: Path = DB_PATH) -> Path:
    """DB 가 없거나 버전이 다르면 만든다."""
    with _LOCK:
        if not path.exists() or _db_version(path) != _script_version():
            build(path)
    return path


@lru_cache(maxsize=None)
def table(name: str) -> tuple[dict, ...]:
    """테이블 전체를 dict 목록으로 (읽기 전용 캐시)."""
    if not re.fullmatch(r"[a-z_]+", name):
        raise ValueError("잘못된 테이블 이름")
    with closing(sqlite3.connect(ensure())) as con:
        con.row_factory = sqlite3.Row
        return tuple(dict(r) for r in con.execute(f"SELECT * FROM {name}"))


def by_key(name: str, key: str = "name") -> dict:
    """테이블을 key 열로 찾는 dict."""
    return {r[key]: r for r in table(name)}
