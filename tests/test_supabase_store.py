"""Supabase 저장소: 가짜 Supabase(REST) 서버로 챕터·공유 저장과 키 헤더, 실패 처리를 본다. .env 읽기도 본다."""
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from love_fortune import content_store as CS
from love_fortune import dotenv

ROOT = Path(__file__).resolve().parent.parent


class FakeRest(BaseHTTPRequestHandler):
    tables: dict = {}
    seen: list = []

    def log_message(self, *a):
        pass

    def _table(self):
        u = urllib.parse.urlsplit(self.path)
        assert u.path.startswith("/rest/v1/")
        return u.path[len("/rest/v1/"):], urllib.parse.parse_qs(u.query)

    def _match(self, name, q):
        rows = list(FakeRest.tables.get(name, {}).values())
        for k, v in q.items():
            if k in ("select", "limit"):
                continue
            op, val = v[0].split(".", 1)
            test = {"eq": lambda a, b: str(a) == b, "gt": lambda a, b: float(a) > float(b),
                    "lt": lambda a, b: float(a) < float(b)}[op]
            rows = [r for r in rows if test(r[k], val)]
        return rows

    def do_GET(self):
        FakeRest.seen.append(("GET", self.headers.get("apikey"), self.headers.get("Authorization")))
        name, q = self._table()
        rows = self._match(name, q)
        cols = q["select"][0].split(",")
        body = json.dumps([{c: r[c] for c in cols} for r in rows]).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        name, q = self._table()
        n = len(self._match(name, q))
        self.send_response(200)
        self.send_header("Content-Range", f"*/{n}")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_DELETE(self):
        name, q = self._table()
        for r in self._match(name, q):
            pk = next(k for k in ("key", "id", "token", "ts") if k in r)
            FakeRest.tables[name] = {k: v for k, v in FakeRest.tables[name].items() if v is not r}
            del pk
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        FakeRest.seen.append(("POST", self.headers.get("apikey"), self.headers.get("Prefer")))
        name, _ = self._table()
        row = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        pk = {"chapter": "key", "ctx": "token"}.get(name, "id")
        if name == "ai_call":
            row["id"] = len(FakeRest.tables.get(name, {})) + 1
        FakeRest.tables.setdefault(name, {})[row[pk]] = row
        self.send_response(201)
        self.send_header("Content-Length", "0")
        self.end_headers()


@pytest.fixture
def fake(monkeypatch):
    FakeRest.tables, FakeRest.seen = {}, []
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeRest)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("SUPABASE_URL", f"http://127.0.0.1:{srv.server_address[1]}/")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_test")
    yield FakeRest
    srv.shutdown()


def test_backend_switch(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    assert CS.backend() == "sqlite"
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_x")
    assert CS.backend() == "supabase"


def test_chapter_and_share_roundtrip(fake):
    assert CS.get_chapter("k1") is None
    CS.put_chapter("k1", "love", "flow", "ai", {"blocks": [{"t": "안녕"}]})
    CS.put_chapter("k1", "love", "flow", "ai", {"blocks": [{"t": "바뀐 풀이"}]})     # 같은 key 는 덮어쓴다
    got = CS.get_chapter("k1")
    assert got == {"blocks": [{"t": "바뀐 풀이"}], "source": "ai"}
    CS.put_share("abc_-1", {"meta": {"target": "2026-09-27"}}, "요약")
    s = CS.get_share("abc_-1")
    assert s["facts"]["meta"]["target"] == "2026-09-27" and s["summary"] == "요약"
    assert CS.get_share("없음") is None
    # 새 방식 키(sb_secret)는 apikey 헤더로만, 덮어쓰기는 merge-duplicates
    assert all(k == "sb_secret_test" for _, k, _ in fake.seen)
    assert all(extra is None for m, _, extra in fake.seen if m == "GET")
    assert all("merge-duplicates" in extra for m, _, extra in fake.seen if m == "POST")


def test_legacy_jwt_key_also_sent_as_bearer(fake, monkeypatch):
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "eyJhbGciOi.test")
    CS.get_chapter("x")
    assert fake.seen[-1][2] == "Bearer eyJhbGciOi.test"


def test_supabase_down(monkeypatch, capsys):
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:9")       # 아무도 안 받는 포트
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_zzz")
    assert CS.get_chapter("k") is None                               # 챕터는 새로 만들면 된다
    CS.put_chapter("k", "love", "flow", "ai", {"blocks": []})        # 저장 실패는 조용히 넘어간다
    with pytest.raises(ValueError, match="다시"):
        CS.put_share("abc", {}, "")                                  # 공유는 실패를 알린다
    err = capsys.readouterr().err
    assert "sb_secret_zzz" not in err and "Supabase" in err          # 키는 로그에 안 남는다


def test_dotenv_load(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text("# 주석\nLF_T_A=1\nLF_T_B=\"따옴표\"\nLF_T_EMPTY=\nLF_T_KEEP=새값\n", encoding="utf-8")
    monkeypatch.setenv("SAJU_DOTENV", "1")
    monkeypatch.setenv("LF_T_KEEP", "원래값")
    for k in ("LF_T_A", "LF_T_B", "LF_T_EMPTY"):
        monkeypatch.delenv(k, raising=False)
    assert dotenv.load(f) == 2
    import os
    assert os.environ["LF_T_A"] == "1" and os.environ["LF_T_B"] == "따옴표"
    assert "LF_T_EMPTY" not in os.environ and os.environ["LF_T_KEEP"] == "원래값"   # 서버 설정이 우선
    for k in ("LF_T_A", "LF_T_B"):
        monkeypatch.delenv(k)


def test_secrets_stay_out_of_git_and_docker():
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    di = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in gi and "!.env.example" in gi and ".env" in di
    ex = (ROOT / ".env.example").read_text(encoding="utf-8")
    for line in ex.splitlines():
        if "=" in line and not line.startswith("#"):
            assert line.split("=", 1)[1] == "", line                 # 예시에는 값이 없다
    sql = (ROOT / "db" / "supabase.sql").read_text(encoding="utf-8")
    assert sql.count("enable row level security") == 4


def test_ctx_roundtrip_and_web_context_fallback(fake):
    # 서버리스: 다른 기계 메모리에 없는 토큰도 Supabase 에서 찾아 이어진다
    from love_fortune import web
    tok = web._remember("", "요약", "2026-09-27", facts={"natal": {"a": 1}, "meta": {"target": "2026-09-27"}})
    assert tok in FakeRest.tables["ctx"]
    with web._CONTEXTS_LOCK:
        web._CONTEXTS.pop(tok)                              # 다른 기계라고 치고 메모리를 비운다
    ctx = web._context(tok)
    assert ctx and ctx["summary"] == "요약" and ctx["facts"]["natal"] == {"a": 1}
    assert web._context("zz") is None and web._context("0" * 16) is None


def test_ai_budget_shared_across_servers(fake):
    assert [CS.ai_budget_take(3) for _ in range(4)] == [True, True, True, False]
    from love_fortune import ai
    import pytest as _pt
    old = ai.PER_HOUR
    try:
        ai.PER_HOUR = 3
        with _pt.raises(RuntimeError):
            ai._take_budget()
    finally:
        ai.PER_HOUR = old


def test_ai_budget_falls_back_without_supabase(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    assert CS.ai_budget_take(3) is None


def test_vercel_entry_and_config():
    import importlib.util
    spec = importlib.util.spec_from_file_location("vercel_entry", ROOT / "api" / "index.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from love_fortune.web import Handler
    assert mod.handler is Handler
    cfg = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert cfg["rewrites"][0]["destination"] == "/api/index"
    assert "love_fortune/**" in cfg["functions"]["api/index.py"]["includeFiles"]
    vi = (ROOT / ".vercelignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in vi and "tests" in vi
    sql = (ROOT / "db" / "supabase.sql").read_text(encoding="utf-8")
    assert sql.count("enable row level security") == 4


def test_serverless_chapter_generates_in_request(monkeypatch):
    from datetime import date
    from love_fortune import chapters, facts, web
    f = facts.build(date(1990, 5, 5), 14, 30, "female", "서울", date(2026, 9, 27))
    tok = web._remember("", "s", "2026-09-27", facts=f)
    called = []
    monkeypatch.setattr(web, "SERVERLESS", True)
    monkeypatch.setattr(web, "_ai_on", lambda: True)
    monkeypatch.setattr(chapters, "generate", lambda tab, ch, fx, use_ai=True: called.append((tab, ch)) or
                        {"headline": "h", "lead": "", "blocks": [], "closing": "", "source": "ai"})

    class H(web.Handler):
        def __init__(self):
            self.out = None

        def _json(self, obj):
            self.out = obj

    h = H()
    h._v2_chapter({"token": tok, "tab": "love", "chapter": chapters.TABS["love"]["chapters"][0]["id"]})
    assert called and h.out["headline"] == "h"
