"""sync_supabase.py, Supabase 데이터를 로컬 SQLite(data/content.db)로 복사한다 (DBeaver 로 보려고).

실행: uv run --no-project python tools/sync_supabase.py
- 한 방향 복사: Supabase → 로컬. 로컬에만 있는 줄은 지우지 않고, 같은 줄은 Supabase 값으로 덮어쓴다.
- 앱이 쓰는 표(chapter, share)에 더해 ctx(결과 6시간), ai_call(AI 호출 시각), chat_use(상담 횟수 해시)도
  같은 이름의 표로 만들어 넣는다. 개인정보(생년월일·이름·도시)는 원래 Supabase 에도 없다.
- 복사 전에 data/content.db 를 data/content.db.bak 으로 한 번 떠 둔다.
- 필요할 때마다 다시 돌리면 된다 (서버를 켜지 않아도 된다).
"""
from __future__ import annotations

import shutil
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from love_fortune import content_store as CS  # noqa: E402  (.env 도 이때 읽는다)

DB = ROOT / "data" / "content.db"
PAGE = 500
TABLES = {
    "chapter": ("key", "key TEXT PRIMARY KEY, tab TEXT NOT NULL, chapter TEXT NOT NULL, source TEXT NOT NULL, "
                "body_json TEXT NOT NULL, created REAL NOT NULL"),
    "share": ("id", "id TEXT PRIMARY KEY, facts_json TEXT NOT NULL, summary TEXT NOT NULL, created REAL NOT NULL"),
    "ctx": ("token", "token TEXT PRIMARY KEY, summary TEXT NOT NULL, target TEXT NOT NULL, facts_json TEXT NOT NULL, "
            "created REAL NOT NULL"),
    "ai_call": ("id", "id INTEGER PRIMARY KEY, ts REAL NOT NULL"),
    "chat_use": ("id", "id INTEGER PRIMARY KEY, k TEXT NOT NULL, ts REAL NOT NULL"),
}


def fetch_all(table: str, pk: str) -> list[dict]:
    rows, off = [], 0
    while True:
        page = CS._rest("GET", table, f"?select=*&order={pk}.asc&limit={PAGE}&offset={off}") or []
        rows += page
        if len(page) < PAGE:
            return rows
        off += PAGE


def main() -> int:
    if CS.backend() != "supabase":
        print("Supabase 설정(SUPABASE_URL·SUPABASE_SECRET_KEY)이 없어. .env 를 확인해 줘.")
        return 1
    DB.parent.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        shutil.copy2(DB, DB.with_suffix(".db.bak"))
    CS._con().close()                                   # 앱 표(chapter·share·meta)가 없으면 앱 방식대로 먼저 만든다
    with closing(sqlite3.connect(DB)) as con:
        for table, (pk, cols) in TABLES.items():
            con.execute(f"CREATE TABLE IF NOT EXISTS {table} ({cols})")
            rows = fetch_all(table, pk)
            if rows:
                names = list(rows[0].keys())
                con.executemany(f"INSERT OR REPLACE INTO {table} ({','.join(names)}) VALUES ({','.join('?' * len(names))})",
                                [tuple(r[n] for n in names) for r in rows])
            total = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table}: Supabase {len(rows)}줄 복사 → 로컬 {total}줄")
        con.commit()
    print(f"완료: {DB} (DBeaver 에서 이 파일을 SQLite 로 열면 돼, 백업은 {DB.name}.bak)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
