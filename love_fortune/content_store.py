"""content_store.py, AI 챕터 풀이·저장한 결과 저장소.

두 가지 중 하나에 저장한다.
- SQLite (기본): data/content.db, db/content.sql 로 만든다. 로컬·시험용.
- Supabase: SUPABASE_URL 과 SUPABASE_SECRET_KEY 가 있으면 Supabase 의 REST API 로 저장한다.
  서버가 재시작돼도(Render 무료 등) 공유 링크와 AI 풀이가 남는다. 표는 db/supabase.sql 로 만든다.
  키는 서버 환경변수에만 둔다. 화면(브라우저)으로는 절대 보내지 않는다.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
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


# ---------------- Supabase (REST)

REST_TIMEOUT = 10


def _supabase() -> tuple[str, str] | None:
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = (os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    return (url, key) if url and key else None


def backend() -> str:
    return "supabase" if _supabase() else "sqlite"


def _rest(method: str, table: str, query: str = "", body: dict | None = None) -> list | None:
    url, key = _supabase()
    headers = {"apikey": key, "Content-Type": "application/json", "Accept": "application/json"}
    if key.startswith("eyJ"):                       # 예전 방식 키(JWT)는 Authorization 에도 넣는다
        headers["Authorization"] = "Bearer " + key
    if method == "POST":
        headers["Prefer"] = "resolution=merge-duplicates,return=minimal"     # 같은 key 면 덮어쓴다
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(f"{url}/rest/v1/{table}{query}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=REST_TIMEOUT) as r:
        raw = r.read()
    return json.loads(raw) if raw else None


def _eq(col: str, val: str) -> str:
    return f"{col}=eq.{urllib.parse.quote(val, safe='')}"


def _log(what: str, e: Exception) -> None:
    # 키·내용은 남기지 않고 어떤 일이 어떤 오류로 실패했는지만 남긴다
    code = getattr(e, "code", "")
    print(f"[저장소] Supabase {what} 실패: {type(e).__name__} {code}".rstrip(), file=sys.stderr)


def get_chapter(key: str) -> dict | None:
    if _supabase():
        try:
            rows = _rest("GET", "chapter", "?select=source,body_json&" + _eq("key", key))
        except (urllib.error.URLError, OSError, ValueError) as e:
            _log("챕터 읽기", e)
            return None                             # 못 읽으면 새로 만든다
        if not rows:
            return None
        body = json.loads(rows[0]["body_json"])
        body["source"] = rows[0]["source"]
        return body
    with closing(_con()) as con:
        row = con.execute("SELECT source, body_json FROM chapter WHERE key=?", (key,)).fetchone()
    if not row:
        return None
    body = json.loads(row["body_json"])
    body["source"] = row["source"]
    return body


def put_chapter(key: str, tab: str, chapter: str, source: str, body: dict) -> None:
    if _supabase():
        try:
            _rest("POST", "chapter", body={"key": key, "tab": tab, "chapter": chapter, "source": source,
                                           "body_json": json.dumps(body, ensure_ascii=False), "created": time.time()})
        except (urllib.error.URLError, OSError, ValueError) as e:
            _log("챕터 저장", e)                    # 저장만 못 했을 뿐 풀이는 그대로 보여 준다
        return
    with closing(_con()) as con:
        con.execute("INSERT OR REPLACE INTO chapter VALUES (?,?,?,?,?,?)",
                    (key, tab, chapter, source, json.dumps(body, ensure_ascii=False), time.time()))
        con.commit()


def put_share(share_id: str, facts: dict, summary: str) -> None:
    if _supabase():
        try:
            _rest("POST", "share", body={"id": share_id, "facts_json": json.dumps(facts, ensure_ascii=False),
                                         "summary": summary, "created": time.time()})
        except (urllib.error.URLError, OSError, ValueError) as e:
            _log("공유 저장", e)
            raise ValueError("저장소에 연결하지 못했어. 잠시 뒤에 다시 해 줘.") from None
        return
    with closing(_con()) as con:
        con.execute("INSERT OR REPLACE INTO share VALUES (?,?,?,?)",
                    (share_id, json.dumps(facts, ensure_ascii=False), summary, time.time()))
        con.commit()


def get_share(share_id: str) -> dict | None:
    if _supabase():
        try:
            rows = _rest("GET", "share", "?select=facts_json,summary,created&" + _eq("id", share_id))
        except (urllib.error.URLError, OSError, ValueError) as e:
            _log("공유 읽기", e)
            raise ValueError("저장소에 연결하지 못했어. 잠시 뒤에 다시 해 줘.") from None
        if not rows:
            return None
        r = rows[0]
        return {"facts": json.loads(r["facts_json"]), "summary": r["summary"], "created": r["created"]}
    with closing(_con()) as con:
        row = con.execute("SELECT facts_json, summary, created FROM share WHERE id=?", (share_id,)).fetchone()
    if not row:
        return None
    return {"facts": json.loads(row["facts_json"]), "summary": row["summary"], "created": row["created"]}
