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

    def do_GET(self):
        FakeRest.seen.append(("GET", self.headers.get("apikey"), self.headers.get("Authorization")))
        name, q = self._table()
        col, val = next((k, v[0][3:]) for k, v in q.items() if k != "select")
        rows = [r for r in FakeRest.tables.get(name, {}).values() if str(r[col]) == val]
        cols = q["select"][0].split(",")
        body = json.dumps([{c: r[c] for c in cols} for r in rows]).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        FakeRest.seen.append(("POST", self.headers.get("apikey"), self.headers.get("Prefer")))
        name, _ = self._table()
        row = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        pk = "key" if name == "chapter" else "id"
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
    monkeypatch.setenv("LOVE_FORTUNE_DOTENV", "1")
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
    assert sql.count("enable row level security") == 2
