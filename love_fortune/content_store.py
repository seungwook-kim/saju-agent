"""content_store.py, AI 챕터 풀이·저장한 결과 저장소 (data/content.db, db/content.sql 로 생성)."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL = ROOT / "db" / "content.sql"
DB = Path(os.environ.get("LOVE_FORTUNE_CONTENT_DB", ROOT / "data" / "content.db"))
_LOCK = threading.Lock()
_READY = False


def _con() -> sqlite3.Connection:
    global _READY
    if not _READY:
        with _LOCK:
            DB.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(DB)) as con:
                con.executescript(SQL.read_text(encoding="utf-8"))
                con.commit()
            _READY = True
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def get_chapter(key: str) -> dict | None:
    with closing(_con()) as con:
        row = con.execute("SELECT source, body_json FROM chapter WHERE key=?", (key,)).fetchone()
    if not row:
        return None
    body = json.loads(row["body_json"])
    body["source"] = row["source"]
    return body


def put_chapter(key: str, tab: str, chapter: str, source: str, body: dict) -> None:
    with closing(_con()) as con:
        con.execute("INSERT OR REPLACE INTO chapter VALUES (?,?,?,?,?,?)",
                    (key, tab, chapter, source, json.dumps(body, ensure_ascii=False), time.time()))
        con.commit()


def put_share(share_id: str, facts: dict, summary: str) -> None:
    with closing(_con()) as con:
        con.execute("INSERT OR REPLACE INTO share VALUES (?,?,?,?)",
                    (share_id, json.dumps(facts, ensure_ascii=False), summary, time.time()))
        con.commit()


def get_share(share_id: str) -> dict | None:
    with closing(_con()) as con:
        row = con.execute("SELECT facts_json, summary, created FROM share WHERE id=?", (share_id,)).fetchone()
    if not row:
        return None
    return {"facts": json.loads(row["facts_json"]), "summary": row["summary"], "created": row["created"]}
