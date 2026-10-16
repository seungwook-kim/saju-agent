"""법률 검토(2026-10-16)로 고친 서버 쪽 문제: 구독 CLI 막기, 상담 안전 규칙·위기 대응, 쿠키 Secure,
속궁합 나이 막기, Langfuse 개인 표시 끊기, 보관 기간 파기, 공유 링크 지우기, AI 없이 보기, /licenses.txt."""
import json
import threading
import types
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from love_fortune import ai, chapters, facts
from love_fortune import content_store as CS
from love_fortune import web
from test_supabase_store import FakeRest, fake  # noqa: F401  (fake 는 pytest 고정물)

ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))
PERSON = {"birth": "1990-05-05", "birth_time": "14:30", "sex": "female", "city": "서울"}


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(CS, "DB", tmp_path / "c.db")
    monkeypatch.setattr(CS, "_READY", False)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _req(base, path, obj=None):
    req = urllib.request.Request(base + path, data=json.dumps(obj).encode("utf-8") if obj is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers


def _post(base, path, obj):
    code, raw, hd = _req(base, path, obj)
    return code, json.loads(raw.decode("utf-8")), hd


# ---------------------------------------------------------------- 1. 구독 CLI 막기

def test_public_server_detection(monkeypatch):
    for k in ("VERCEL", "HOST", "SAJU_TRUST_PROXY"):
        monkeypatch.delenv(k, raising=False)
    assert not ai._public_server()                           # 이 컴퓨터에서 직접
    for host in ("127.0.0.1", "localhost", "::1", ""):
        monkeypatch.setenv("HOST", host)
        assert not ai._public_server()
    monkeypatch.setenv("HOST", "0.0.0.0")
    assert ai._public_server()
    monkeypatch.delenv("HOST")
    monkeypatch.setenv("VERCEL", "1")
    assert ai._public_server()
    monkeypatch.delenv("VERCEL")
    for v, want in (("1", True), ("true", True), ("yes", True), ("on", True), ("0", False), ("", False)):
        monkeypatch.setenv("SAJU_TRUST_PROXY", v)
        assert ai._public_server() is want


def test_subscription_cli_blocked_on_public_server(monkeypatch):
    monkeypatch.setattr(ai, "BACKEND", "cli")
    monkeypatch.setattr(ai.shutil, "which", lambda name: "/usr/bin/claude")
    monkeypatch.setattr(ai, "PER_HOUR", 0)
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("SAJU_TRUST_PROXY", raising=False)
    monkeypatch.setenv("HOST", "127.0.0.1")
    assert ai.available() is True                            # 이 컴퓨터에서는 그대로
    monkeypatch.setenv("VERCEL", "1")
    assert ai.available() is False
    with pytest.raises(RuntimeError, match="공개 서버"):
        ai._run_backend("s", "p", 5, 10, False)
    with pytest.raises(RuntimeError):
        ai.run("s", "p")
    # API 방식은 공개 서버에서도 그대로
    monkeypatch.setattr(ai, "BACKEND", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    assert ai.available() is True


def test_dockerfile_uses_api_backend():
    assert "SAJU_AI_BACKEND=anthropic" in (ROOT / "Dockerfile").read_text(encoding="utf-8")


# ---------------------------------------------------------------- 2. 상담 규칙·위기 대응

def test_system_prompt_rules():
    p = web.SYSTEM_PROMPT
    assert "정통 공식" not in p
    assert "재미·참고용 풀이" in p and "AI 라는 걸 숨기지 않는다" in p
    assert "12) 건강·의료, 법률, 투자·돈 거래, 진학·취업" in p and "전문가와 상의하라고 한다" in p
    assert "13) 성적인 질문에는 노골적인 묘사 없이 짧게" in p
    assert "—" not in p


def test_crisis_reply_and_local_agent():
    for msg in ("죽고 싶어", "자 살 할래", "죽 어버리고 싶다", "자해했어", "죽을래"):
        r = web.crisis_reply(msg)
        assert r and "109" in r and "1388" in r
    assert web.crisis_reply("올해 연애운 어때") is None and web.crisis_reply("헤어져야 할까?") is None
    assert web.local_agent_reply("죽고싶어", "대상일 2026-10-16") == web.CRISIS_REPLY
    assert "1388" not in web.local_agent_reply("헤어져야 할까?", "대상일 2026-10-16")


def test_grounding_keeps_crisis_numbers():
    reply = "많이 힘들구나. 자살예방상담전화 109에 전화해 줘. 청소년이면 1388 도 있어. 정신건강상담 1577-0199 도 있어."
    kept = chapters.ground_reply(reply, "대상일 2026-10-16 / 점수 70점")
    for n in ("109", "1388", "1577-0199"):
        assert n in kept
    assert "4321" not in chapters.ground_reply("행운의 숫자는 4321 이야.", "점수 70점")      # 다른 숫자는 여전히 뺀다


def test_chat_crisis_comes_first_even_without_result(server, monkeypatch):
    called = []
    monkeypatch.setattr(ai, "run", lambda *a, **k: called.append(a) or "AI 답")
    monkeypatch.setattr(web, "_chat_on", lambda ip: True)
    code, j, _ = _post(server, "/api/chat", {"token": "만료됨", "message": "그냥 죽고싶어"})      # 결과가 없어도 먼저 받는다
    assert code == 200 and j["mode"] == "rule" and "109" in j["reply"] and "1388" in j["reply"] and j["sig"]
    code, _j, _ = _post(server, "/api/chat", {"token": "만료됨", "message": "올해 연애운 어때"})
    assert code == 400
    assert called == []                                      # AI 를 부르지 않는다


# ---------------------------------------------------------------- 3. 쿠키 Secure

def test_cid_cookie_secure_on_vercel(server, monkeypatch):
    monkeypatch.delenv("SAJU_TRUST_PROXY", raising=False)
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setattr(web, "_chat_on", lambda ip: True)
    monkeypatch.setattr(web, "_ai_on", lambda: False)
    _, rep, _ = _post(server, "/api/v2/report", PERSON)

    def cookie():
        _, _, hd = _post_raw_chat(server, rep["token"])
        return hd.get("Set-Cookie") or ""
    c = cookie()
    assert c.startswith("cid=") and "HttpOnly" in c and "Secure" not in c      # 로컬 http 에서는 붙이지 않는다
    monkeypatch.setenv("VERCEL", "1")
    assert "; Secure" in cookie()
    monkeypatch.delenv("VERCEL")
    monkeypatch.setenv("SAJU_TRUST_PROXY", "1")
    assert "; Secure" in cookie()


def _post_raw_chat(base, token):
    return _req(base, "/api/chat", {"token": token, "message": "올해 연애운 어때"})


# ---------------------------------------------------------------- 4. 속궁합 나이

def test_sok_hidden_for_under_19():
    adult = facts.build(date(1990, 5, 5), 14, 30, "female", "서울", date(2026, 10, 16))
    teen = facts.build(date(2008, 10, 17), 14, 30, "female", "서울", date(2026, 10, 16))      # 만 17세
    edge = facts.build(date(2007, 10, 16), 14, 30, "female", "서울", date(2026, 10, 16))      # 오늘 만 19세
    assert adult["sok"] and edge["sok"] and teen["sok"] is None
    assert facts.build(date(2007, 10, 17), 14, 30, "male", "서울", date(2026, 10, 16))["sok"] is None   # 내일 만 19세


def test_match_sok_none_if_either_is_under_19(server):
    today = date.today()
    adult = {"birth": "1990-05-05", "birth_time": "14:30", "sex": "female", "city": "서울"}

    def pair(b2):
        return {**adult, "birth2": b2, "birth2_time": "09:00", "sex2": "male", "city2": "부산"}
    code, j, _ = _post(server, "/api/match", pair("1992-03-03"))
    assert code == 200 and len(j["data"]["sok"]["rows"]) == 2
    teen = today.replace(year=today.year - 18) - timedelta(days=1) + timedelta(days=2)       # 만 18세 (생일 이틀 전)
    code, j, _ = _post(server, "/api/match", pair(teen.isoformat()))
    assert code == 200 and j["data"]["sok"] is None
    code, j, _ = _post(server, "/api/match", {**pair("1992-03-03"), "birth": teen.isoformat()})      # 첫째 사람이어도
    assert code == 200 and j["data"]["sok"] is None
    assert web.age_on(date(2007, 10, 16), date(2026, 10, 15)) == 18 and web.age_on(date(2007, 10, 16), date(2026, 10, 16)) == 19


# ---------------------------------------------------------------- 6. 보관 기간과 파기

T0 = datetime(2026, 10, 16, 12, 0, tzinfo=KST).timestamp()
DAY = 86400


def _at(monkeypatch, t):
    monkeypatch.setattr(CS, "time", types.SimpleNamespace(time=lambda: t))


def _seed_visits():
    for day, k, v in (("2026-10-12", "d12a", "A"), ("2026-10-12", "d12b", "B"),
                      ("2026-10-13", "d13a", "A"), ("2026-10-13", "d13b", "C"), ("2026-10-13", "d13c", "D"),
                      ("2026-10-15", "d15a", "E"),
                      ("2026-10-16", "d16a", "A"), ("2026-10-16", "d16b", "F")):
        assert CS.visit_add(day, k, v)


EXPECT = {"total": 6, "days": [{"day": "2026-10-12", "visitors": 2, "new": 2},
                               {"day": "2026-10-13", "visitors": 3, "new": 2},
                               {"day": "2026-10-15", "visitors": 1, "new": 1},
                               {"day": "2026-10-16", "visitors": 2, "new": 1}]}


def _visit_checks():
    assert CS.visit_stats("2026-10-01") == EXPECT
    assert CS.visit_stats("2026-10-15")["days"] == EXPECT["days"][2:]
    CS.purge(T0)                                             # 어제(10-15)보다 오래된 날만 숫자로 합친다
    assert CS.visit_stats("2026-10-01") == EXPECT
    assert CS.visit_stats("2026-10-15")["days"] == EXPECT["days"][2:]
    CS.purge(T0)                                             # 두 번 해도 같다
    assert CS.visit_stats("2026-10-01") == EXPECT


def test_purge_visits_supabase(fake):
    _seed_visits()
    _visit_checks()
    assert sorted(d for d, _k in FakeRest.tables["visit_day"]) == ["2026-10-15", "2026-10-16", "2026-10-16"]
    assert FakeRest.tables["visit_count"] == {"2026-10-12": {"day": "2026-10-12", "visitors": 2, "new": 2},
                                              "2026-10-13": {"day": "2026-10-13", "visitors": 3, "new": 2}}
    CS.purge(T0 + 3 * DAY)                                   # 며칠 뒤에는 15·16일도 합쳐진다. 누적은 그대로
    assert CS.visit_stats()["total"] == 6 and not FakeRest.tables["visit_day"]
    assert CS.visit_stats()["days"][-1] == {"day": "2026-10-16", "visitors": 2, "new": 1}
    CS.visit_add("2026-10-20", "d20", "A")                   # 이미 센 사람이 또 와도 누적은 그대로
    CS.visit_add("2026-10-20", "d20b", "G")
    assert CS.visit_stats()["total"] == 7
    CS.purge(T0 + 400 * DAY)                                 # 365일 넘은 visitor 는 지워도 누적은 그대로
    assert not FakeRest.tables["visitor"] and CS.visit_stats()["total"] == 7


def test_purge_visits_sqlite(tmp_path, monkeypatch):
    monkeypatch.setattr(CS, "DB", tmp_path / "c.db")
    monkeypatch.setattr(CS, "_READY", False)
    _seed_visits()
    _visit_checks()
    from contextlib import closing
    with closing(CS._con()) as con:
        assert [r[0] for r in con.execute("SELECT day FROM visit_day ORDER BY day")] == ["2026-10-15", "2026-10-16", "2026-10-16"]
        assert con.execute("SELECT COUNT(*) FROM visit_count").fetchone()[0] == 2
    CS.purge(T0 + 400 * DAY)
    assert CS.visit_stats()["total"] == 6
    with closing(CS._con()) as con:
        assert con.execute("SELECT COUNT(*) FROM visitor").fetchone()[0] == 0


def test_purge_ctx_chat_ai_call(fake, monkeypatch):
    _at(monkeypatch, T0 - 7 * 3600)
    CS.put_ctx("old", "요약", "2026-10-16", None)
    CS.chat_take(["k1"], 10, 300)
    CS.ai_budget_take(600)
    _at(monkeypatch, T0 - 3600)
    CS.put_ctx("new", "요약", "2026-10-16", None)
    _at(monkeypatch, T0 - 25 * 3600)
    CS.chat_take(["k2"], 10, 300)
    CS.ai_budget_take(600)
    _at(monkeypatch, T0 - 3600)
    CS.chat_take(["k3"], 10, 300)
    CS.ai_budget_take(600)
    CS.purge(T0)
    assert list(FakeRest.tables["ctx"]) == ["new"]
    assert {r["k"] for r in FakeRest.tables["chat_use"].values()} == {"k1", "k3", "all"}     # 24시간 안의 것만 남는다
    assert len(FakeRest.tables["chat_use"]) == 4 and len(FakeRest.tables["ai_call"]) == 2


def _feedback_and_share(monkeypatch):
    for days, body, k in ((400, "아주 옛날", "k400"), (100, "석 달 넘음", "k100"), (10, "얼마 전", "k10")):
        _at(monkeypatch, T0 - days * DAY)
        CS.feedback_add("203.0.113.7", k, body)
        CS.put_share(f"share{days}", {"meta": {"target": "2026-10-16"}}, "요약")
    _at(monkeypatch, T0)


def _check_feedback_and_share():
    got = {r["body"]: r["ip"] for r in CS.feedback_list()}
    assert got == {"석 달 넘음": "", "얼마 전": "203.0.113.7"}            # 90일 넘으면 IP 비움, 365일 넘으면 줄을 지움
    assert CS.get_share("share400") is None and CS.get_share("share100") and CS.get_share("share10")


def test_purge_feedback_and_share_supabase(fake, monkeypatch):
    _feedback_and_share(monkeypatch)
    assert CS.get_share("share400") is None                  # 지우기 전에도 365일 넘으면 열리지 않는다
    assert "share400" in FakeRest.tables["share"]
    CS.purge(T0)
    assert "share400" not in FakeRest.tables["share"]
    _check_feedback_and_share()
    assert ("PATCH", "sb_secret_test", "return=minimal") in FakeRest.seen


def test_purge_feedback_and_share_sqlite(tmp_path, monkeypatch):
    monkeypatch.setattr(CS, "DB", tmp_path / "c.db")
    monkeypatch.setattr(CS, "_READY", False)
    _feedback_and_share(monkeypatch)
    assert CS.get_share("share400") is None
    CS.purge(T0)
    _check_feedback_and_share()


def test_feedback_block_keeps_no_ip(tmp_path, monkeypatch):
    monkeypatch.setattr(CS, "DB", tmp_path / "c.db")
    monkeypatch.setattr(CS, "_READY", False)
    CS.feedback_add("203.0.113.7", "kA", "욕설")
    CS.feedback_block("kA", "203.0.113.7", "욕설")
    from contextlib import closing
    with closing(CS._con()) as con:
        assert con.execute("SELECT ip FROM feedback_block WHERE k='kA'").fetchone()[0] == ""
    assert CS.feedback_state("kA")[0] is True                # 해시만으로 막힌다


def test_feedback_tool_shows_purged_ip(tmp_path, monkeypatch, capsys):
    import importlib.util
    monkeypatch.setattr(CS, "DB", tmp_path / "c.db")
    monkeypatch.setattr(CS, "_READY", False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    _at(monkeypatch, T0 - 100 * DAY)
    CS.feedback_add("203.0.113.7", "kA", "옛 쪽지")
    _at(monkeypatch, T0)
    CS.purge(T0)
    spec = importlib.util.spec_from_file_location("fb_tool", ROOT / "tools" / "feedback.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main([]) == 0
    assert "(90일 지나 지움)" in capsys.readouterr().out
    assert mod.main(["block", "1", "욕설"]) == 0              # IP 가 지워져도 해시로 막는다
    assert CS.feedback_state("kA")[0] is True


def test_purge_failure_does_not_break(monkeypatch, capsys):
    monkeypatch.setattr(CS, "purge", lambda now=None: 1 / 0)
    monkeypatch.setenv("SAJU_PURGE", "1")
    monkeypatch.setitem(web._PURGE, "t", 0.0)
    web.maybe_purge()                                        # 오류가 밖으로 나오지 않는다
    assert "[파기] 실패" in capsys.readouterr().err


def test_maybe_purge_once_per_ten_minutes(monkeypatch):
    calls = []
    monkeypatch.setattr(CS, "purge", lambda now=None: calls.append(now))
    monkeypatch.setenv("SAJU_PURGE", "1")
    monkeypatch.setitem(web._PURGE, "t", 0.0)
    web.maybe_purge()
    web.maybe_purge()
    assert len(calls) == 1
    web._PURGE["t"] -= web.PURGE_EVERY + 1
    web.maybe_purge()
    assert len(calls) == 2
    monkeypatch.setenv("SAJU_PURGE", "0")
    web._PURGE["t"] = 0.0
    web.maybe_purge()
    assert len(calls) == 2


def test_post_and_visits_trigger_purge(server, monkeypatch):
    calls = []
    monkeypatch.setattr(CS, "purge", lambda now=None: calls.append(now))
    monkeypatch.setenv("SAJU_PURGE", "1")
    monkeypatch.setitem(web._PURGE, "t", 0.0)
    code, _j, _ = _post(server, "/api/v2/report", PERSON)
    assert code == 200 and len(calls) == 1
    monkeypatch.setitem(web._PURGE, "t", 0.0)
    assert _req(server, "/api/visits")[0] == 200 and len(calls) == 2


def test_supabase_sql_has_visit_count_and_lock():
    sql = (ROOT / "db" / "supabase.sql").read_text(encoding="utf-8")
    assert "create table if not exists public.visit_count" in sql
    assert "alter table public.visit_count enable row level security" in sql
    assert "revoke all on public.visit_count from anon, authenticated" in sql
    assert sql.count("enable row level security") == sql.count("create table")
    assert "visit_count" in (ROOT / "db" / "content.sql").read_text(encoding="utf-8")
    assert "visit_count" in (ROOT / "tools" / "sync_supabase.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------- 7. 공유 링크 지우기

def test_share_delete_needs_key(server):
    _, rep, _ = _post(server, "/api/v2/report", PERSON)
    code, sh, _ = _post(server, "/api/v2/share", {"token": rep["token"]})
    assert code == 200 and sh["del"] and sh["del"] != sh["id"]
    assert _post(server, "/api/v2/shared", {"id": sh["id"]})[0] == 200
    code, j, _ = _post(server, "/api/v2/share_delete", {"id": sh["id"], "key": "틀린 열쇠"})
    assert code == 403 and j["error"] == "지울 권한이 없어."
    assert _post(server, "/api/v2/share_delete", {"id": sh["id"]})[0] == 403
    assert _post(server, "/api/v2/share_delete", {"id": "x!", "key": sh["del"]})[0] == 400       # 형식이 틀린 이름
    assert _post(server, "/api/v2/shared", {"id": sh["id"]})[0] == 200                           # 아직 안 지워졌다
    code, j, _ = _post(server, "/api/v2/share_delete", {"id": sh["id"], "key": sh["del"]})
    assert code == 200 and j == {"ok": True}
    code, j, _ = _post(server, "/api/v2/shared", {"id": sh["id"]})
    assert code == 400 and "없는 링크" in j["error"]
    _, sh2, _ = _post(server, "/api/v2/share", {"token": rep["token"]})
    assert _post(server, "/api/v2/share_delete", {"id": sh2["id"], "key": sh["del"]})[0] == 403   # 다른 링크의 열쇠로는 못 지운다


def test_share_delete_supabase(fake):
    CS.put_share("abcdefgh1", {"meta": {"target": "2026-10-16"}}, "요약")
    CS.delete_share("abcdefgh1")
    assert CS.get_share("abcdefgh1") is None and "abcdefgh1" not in FakeRest.tables["share"]
    CS.delete_share("없는링크")                                # 없어도 오류가 아니다


# ---------------------------------------------------------------- 8. AI 없이 보기

def test_noai_skips_prefetch_ai_and_chat(server, monkeypatch):
    submitted = []
    monkeypatch.setattr(web, "_ai_on", lambda: True)
    monkeypatch.setattr(web, "_chat_on", lambda ip: True)
    from love_fortune import prefetch
    monkeypatch.setattr(prefetch, "submit_all", lambda f: submitted.append(1))
    code, j, _ = _post(server, "/api/v2/report", PERSON)
    assert code == 200 and j["ai"] is True and j["chat"] is True and submitted == [1]
    code, j, _ = _post(server, "/api/v2/report", {**PERSON, "noai": True})
    assert code == 200 and j["ai"] is False and j["chat"] is False and submitted == [1]
    code, j, _ = _post(server, "/api/v2/report", {**PERSON, "noai": "0"})
    assert j["ai"] is True and submitted == [1, 1]
    token = _post(server, "/api/v2/report", {**PERSON, "noai": 1})[1]["token"]
    sh = _post(server, "/api/v2/share", {"token": token})[1]
    code, j, _ = _post(server, "/api/v2/shared", {"id": sh["id"], "noai": True})
    assert code == 200 and j["ai"] is False and j["chat"] is False and j["shared"] is True
    assert _post(server, "/api/v2/shared", {"id": sh["id"]})[1]["ai"] is True


def test_noai_chapter_is_rule_only(server, monkeypatch):
    monkeypatch.setattr(web, "_ai_on", lambda: True)
    from love_fortune import prefetch
    monkeypatch.setattr(prefetch, "submit_all", lambda f: None)
    monkeypatch.setattr(prefetch, "wait", lambda *a: {"headline": "AI 풀이", "source": "ai"})
    monkeypatch.setattr(web, "SERVERLESS", False)
    rep = _post(server, "/api/v2/report", PERSON)[1]
    tab = next(iter(chapters.TABS))
    ch = chapters.TABS[tab]["chapters"][0]["id"]
    j = _post(server, "/api/v2/chapter", {"token": rep["token"], "tab": tab, "chapter": ch})[1]
    assert j["headline"] == "AI 풀이"
    j = _post(server, "/api/v2/chapter", {"token": rep["token"], "tab": tab, "chapter": ch, "noai": True})[1]
    assert j["headline"] != "AI 풀이" and j.get("source") != "ai"
    monkeypatch.setattr(web, "SERVERLESS", True)
    monkeypatch.setattr(chapters, "generate", lambda *a, **k: {"headline": "서버리스 AI", "source": "ai"})
    j = _post(server, "/api/v2/chapter", {"token": rep["token"], "tab": tab, "chapter": ch, "noai": True})[1]
    assert j["headline"] != "서버리스 AI"


# ---------------------------------------------------------------- 9. /licenses.txt

def test_licenses_txt(server):
    code, raw, hd = _req(server, "/licenses.txt")
    assert code == 200 and hd["Content-Type"] == "text/plain; charset=utf-8"
    assert raw == (ROOT / "THIRD_PARTY_NOTICES.md").read_bytes()


def test_licenses_txt_behind_bot_block(server, monkeypatch):
    monkeypatch.setenv("SAJU_BOT_BLOCK", "1")
    req = urllib.request.Request(server + "/licenses.txt", headers={"User-Agent": "GPTBot/1.0"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 403


def test_vercelignore_keeps_notices():
    vi = (ROOT / ".vercelignore").read_text(encoding="utf-8").splitlines()
    assert "THIRD_PARTY_NOTICES.md" not in vi and "*.md" not in vi          # 배포에 들어간다


def test_cli_blocked_when_served_on_lan(monkeypatch):
    # --host 0.0.0.0 처럼 바깥에 연 서버는 HOST 환경변수가 없어도 공개 서버로 본다 (구독 CLI 막기)
    from love_fortune import ai
    for k in ("VERCEL", "HOST", "SAJU_TRUST_PROXY", "SAJU_PUBLIC"):
        monkeypatch.delenv(k, raising=False)
    assert ai._public_server() is False
    monkeypatch.setenv("SAJU_PUBLIC", "1")
    assert ai._public_server() is True


def test_purge_drops_year_old_chapters(tmp_path, monkeypatch):
    # AI 풀이(chapter)도 처리방침대로 1년 뒤 지운다
    import time
    from love_fortune import content_store as CS
    monkeypatch.setattr(CS, "DB", tmp_path / "c.db")
    monkeypatch.setattr(CS, "_READY", False)
    CS.put_chapter("old", "love", "flow", "ai", {"blocks": []})
    CS.put_chapter("new", "love", "flow", "ai", {"blocks": []})
    from contextlib import closing
    with closing(CS._con()) as con:
        con.execute("UPDATE chapter SET created=? WHERE key='old'", (time.time() - 400 * 86400,))
        con.commit()
    CS.purge()
    assert CS.get_chapter("old") is None and CS.get_chapter("new") is not None
