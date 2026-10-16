"""content_store.py, AI 챕터 풀이·저장한 결과 저장소.

두 가지 중 하나에 저장한다.
- SQLite (기본): data/content.db, db/content.sql 로 만든다. 로컬·시험용.
- Supabase: SUPABASE_URL 과 SUPABASE_SECRET_KEY 가 있고 운영 서버(VERCEL, 또는 HOST 가 로컬 주소가 아님)면
  Supabase 의 REST API 로 저장한다. 로컬은 키가 있어도 SQLite (SAJU_STORE=supabase|sqlite 로 직접 정할 수 있다).
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
# Vercel 같은 서버리스는 /tmp 말고는 쓸 수 없다
_TMP_DEFAULT = Path("/tmp") if os.environ.get("VERCEL") else ROOT / "data"
DB = Path(os.environ.get("SAJU_CONTENT_DB", _TMP_DEFAULT / "content.db"))
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


LOCAL_HOSTS = ("", "127.0.0.1", "localhost", "::1")


def _server() -> bool:
    """운영 서버에서 도는지. 로컬(이 컴퓨터)에서 연 결과가 운영 DB 에 섞이지 않게 (2026-10-16)."""
    store = os.environ.get("SAJU_STORE", "auto").strip().lower()
    if store in ("supabase", "sqlite"):
        return store == "supabase"
    return bool(os.environ.get("VERCEL")) or os.environ.get("HOST", "").strip() not in LOCAL_HOSTS


def _supabase() -> tuple[str, str] | None:
    if not _server():
        return None
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = (os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    return (url, key) if url and key else None


def backend() -> str:
    return "supabase" if _supabase() else "sqlite"


def _rest(method: str, table: str, query: str = "", body: dict | list | None = None, count: bool = False,
          keep: bool = False):
    url, key = _supabase()
    headers = {"apikey": key, "Content-Type": "application/json", "Accept": "application/json"}
    if count:
        headers["Prefer"] = "count=exact"
    if key.startswith("eyJ"):                       # 예전 방식 키(JWT)는 Authorization 에도 넣는다
        headers["Authorization"] = "Bearer " + key
    if method == "POST":
        # 같은 key 면 덮어쓴다 (keep 이면 처음 값을 둔다)
        headers["Prefer"] = ("resolution=ignore-duplicates" if keep else "resolution=merge-duplicates") + ",return=minimal"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(f"{url}/rest/v1/{table}{query}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=REST_TIMEOUT) as r:
        raw = r.read()
        if count:                                   # Content-Range: 0-0/12 또는 */12
            return int((r.headers.get("Content-Range") or "*/0").rsplit("/", 1)[1] or 0)
    return json.loads(raw) if raw else None


# ---------------- 결과 토큰 (서버리스에서 요청마다 다른 기계가 받아도 이어지게)

def put_ctx(token: str, summary: str, target: str, facts: dict | None) -> None:
    if not _supabase():
        return
    try:
        _rest("POST", "ctx", body={"token": token, "summary": summary, "target": target,
                                   "facts_json": json.dumps(facts, ensure_ascii=False) if facts else "",
                                   "created": time.time()})
        if time.time() % 50 < 1:                    # 가끔 6시간 넘은 것을 치운다
            _rest("DELETE", "ctx", f"?created=lt.{time.time() - 6 * 3600}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        _log("결과 저장", e)


def get_ctx(token: str) -> dict | None:
    if not _supabase() or not token:
        return None
    try:
        rows = _rest("GET", "ctx", "?select=summary,target,facts_json,created&" + _eq("token", token))
    except (urllib.error.URLError, OSError, ValueError) as e:
        _log("결과 읽기", e)
        return None
    if not rows:
        return None
    r = rows[0]
    return {"md": "", "summary": r["summary"], "target": r["target"], "created": r["created"],
            "facts": json.loads(r["facts_json"]) if r["facts_json"] else None}


# ---------------- 상담 횟수 (서버가 여러 대여도 한 사람 하루 횟수를 함께 센다)

def chat_take(keys: list[str], per_day: int, global_per_day: int) -> int | None | bool:
    """한 번 쓴다. 남은 횟수(int), 다 썼으면 None, Supabase 가 없거나 안 되면 False (부르는 쪽이 메모리로 센다).
    keys 는 이미 해시된 값이라 IP·쿠키 원래 값은 저장되지 않는다."""
    if not _supabase() or not keys:
        return False
    now = time.time()
    since = now - 24 * 3600
    try:
        if _rest("HEAD", "chat_use", f"?select=k&ts=gt.{since}&k=eq.all", count=True) >= global_per_day:
            return None
        inlist = ",".join(urllib.parse.quote(k, safe="") for k in keys)
        rows = _rest("GET", "chat_use", f"?select=k&ts=gt.{since}&k=in.({inlist})") or []
        used = max((sum(1 for r in rows if r["k"] == k) for k in keys), default=0)
        if used >= per_day:
            return None
        _rest("POST", "chat_use", body=[{"k": k, "ts": now} for k in keys + ["all"]])
        if now % 100 < 1:
            _rest("DELETE", "chat_use", f"?ts=lt.{since}")
        return per_day - used - 1
    except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError) as e:
        _log("상담 횟수", e)
        return False


# ---------------- AI 사용량 (서버가 여러 대여도 시간당 총량을 함께 센다)

def ai_budget_take(per_hour: int) -> bool | None:
    """한 번 쓴다. 남았으면 True, 다 찼으면 False. Supabase 가 없거나 안 되면 None (부르는 쪽이 메모리로 센다)."""
    if not _supabase():
        return None
    now = time.time()
    try:
        used = _rest("HEAD", "ai_call", f"?select=ts&ts=gt.{now - 3600}", count=True)
        if used >= per_hour:
            return False
        _rest("POST", "ai_call", body={"ts": now})
        if now % 100 < 1:
            _rest("DELETE", "ai_call", f"?ts=lt.{now - 86400}")
        return True
    except (urllib.error.URLError, OSError, ValueError) as e:
        _log("AI 사용량", e)
        return None


# ---------------- 방문자 수 (하루·누적, 포트폴리오·운영 확인용)

def visit_add(day: str, day_key: str, person_key: str) -> bool:
    """결과를 연 IP 하나. 키는 이미 해시된 값이다 (IP 원래 값은 저장하지 않는다).
    day_key 는 날짜를 섞은 해시라 하루 표만으로는 같은 사람이 언제 또 왔는지 이어 볼 수 없다.
    visitor 는 처음 온 날만 남긴다 (누적 방문자·그날 새로 온 사람). 저장했으면 True."""
    if _supabase():
        try:
            _rest("POST", "visit_day", body={"day": day, "k": day_key}, keep=True)
            _rest("POST", "visitor", body={"k": person_key, "first_day": day}, keep=True)
        except (urllib.error.URLError, OSError, ValueError) as e:
            _log("방문 기록", e)
            return False
        return True
    with closing(_con()) as con:
        con.execute("INSERT OR IGNORE INTO visit_day VALUES (?,?)", (day, day_key))
        con.execute("INSERT OR IGNORE INTO visitor VALUES (?,?)", (person_key, day))
        con.commit()
    return True


def visit_stats(since: str = "") -> dict:
    """{"total": 누적 방문자, "days": [{"day", "visitors", "new"}, ...]} (since 날짜부터, 오래된 날이 위)."""
    if _supabase():
        total = _rest("HEAD", "visitor", "?select=k", count=True)
        days = _rest_all("visit_day", "day", f"&day=gte.{since}" if since else "")
        firsts = _rest_all("visitor", "first_day", f"&first_day=gte.{since}" if since else "")
        day_rows, new_rows = [r["day"] for r in days], [r["first_day"] for r in firsts]
    else:
        with closing(_con()) as con:
            total = con.execute("SELECT COUNT(*) FROM visitor").fetchone()[0]
            day_rows = [r[0] for r in con.execute("SELECT day FROM visit_day WHERE day >= ?", (since,))]
            new_rows = [r[0] for r in con.execute("SELECT first_day FROM visitor WHERE first_day >= ?", (since,))]
    out = [{"day": d, "visitors": day_rows.count(d), "new": new_rows.count(d)} for d in sorted(set(day_rows))]
    return {"total": total, "days": out}


# ---------------- 익명 쪽지 (불편한 점·의견, 2026-10-16 사용자 요청)
# 이름·로그인 없이 받는다. 욕설·도배를 막으려고 IP 를 같이 둔다 (화면에 그렇게 알린다).
# k 는 IP 해시 (차단·하루 횟수용), 차단은 feedback_block 에 k 로.

def feedback_add(ip: str, k: str, body: str) -> None:
    row = {"ts": time.time(), "ip": ip, "k": k, "body": body}
    if _supabase():
        try:
            _rest("POST", "feedback", body=row)
        except (urllib.error.URLError, OSError, ValueError) as e:
            _log("쪽지 저장", e)
            raise ValueError("쪽지를 저장하지 못했어. 잠시 뒤에 다시 해 줘.") from None
        return
    with closing(_con()) as con:
        con.execute("INSERT INTO feedback (ts, ip, k, body) VALUES (?,?,?,?)", (row["ts"], ip, k, body))
        con.commit()


def feedback_state(k: str) -> tuple[bool, int]:
    """(차단됐나, 최근 24시간에 보낸 수). 못 읽으면 (False, 0) 으로 받아 준다."""
    since = time.time() - 24 * 3600
    if _supabase():
        try:
            blocked = bool(_rest("GET", "feedback_block", "?select=k&" + _eq("k", k)))
            used = _rest("HEAD", "feedback", f"?select=id&ts=gt.{since}&" + _eq("k", k), count=True)
            return blocked, used
        except (urllib.error.URLError, OSError, ValueError) as e:
            _log("쪽지 확인", e)
            return False, 0
    with closing(_con()) as con:
        blocked = con.execute("SELECT 1 FROM feedback_block WHERE k=?", (k,)).fetchone() is not None
        used = con.execute("SELECT COUNT(*) FROM feedback WHERE k=? AND ts>?", (k, since)).fetchone()[0]
    return blocked, used


def feedback_list(limit: int = 50) -> list[dict]:
    """최근 쪽지부터. 차단된 IP 의 쪽지는 blocked=True."""
    if _supabase():
        rows = _rest("GET", "feedback", f"?select=id,ts,ip,k,body&order=id.desc&limit={int(limit)}") or []
        ks = ",".join(sorted({urllib.parse.quote(r["k"], safe="") for r in rows}))
        bl = {r["k"] for r in (_rest("GET", "feedback_block", f"?select=k&k=in.({ks})") or [])} if rows else set()
    else:
        with closing(_con()) as con:
            rows = [dict(r) for r in con.execute("SELECT id, ts, ip, k, body FROM feedback ORDER BY id DESC LIMIT ?",
                                                 (limit,))]
            bl = {r[0] for r in con.execute("SELECT k FROM feedback_block")}
    return [{**r, "blocked": r["k"] in bl} for r in rows]


def feedback_block(k: str, ip: str, note: str = "", on: bool = True) -> None:
    if _supabase():
        if on:
            _rest("POST", "feedback_block", body={"k": k, "ip": ip, "note": note, "ts": time.time()})
        else:
            _rest("DELETE", "feedback_block", "?" + _eq("k", k))
        return
    with closing(_con()) as con:
        if on:
            con.execute("INSERT OR REPLACE INTO feedback_block VALUES (?,?,?,?)", (k, ip, note, time.time()))
        else:
            con.execute("DELETE FROM feedback_block WHERE k=?", (k,))
        con.commit()


def _rest_all(table: str, col: str, extra: str, page: int = 1000) -> list[dict]:
    rows, off = [], 0
    while True:
        got = _rest("GET", table, f"?select={col}{extra}&order={col}.asc&limit={page}&offset={off}") or []
        rows += got
        if len(got) < page:
            return rows
        off += page


def _eq(col: str, val: str) -> str:
    return f"{col}=eq.{urllib.parse.quote(val, safe='')}"


def _log(what: str, e: Exception) -> None:
    # 키·내용은 남기지 않고 어떤 일이 어떤 오류로 실패했는지만 남긴다
    code = getattr(e, "code", "")
    hint = {404: " (표가 없어. Supabase SQL Editor 에서 db/supabase.sql 을 실행해 줘)",
            401: " (키가 틀렸어. SUPABASE_SECRET_KEY 를 확인해 줘)",
            403: " (권한이 없어. 공개 키가 아니라 서버 전용 키인지 확인해 줘)"}.get(code, "")
    print(f"[저장소] Supabase {what} 실패: {type(e).__name__} {code}".rstrip() + hint, file=sys.stderr)


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
