"""새 화면(탭·챕터)용 사실표·챕터·API 검사. AI 없이 돈다."""
import json
import threading
import urllib.request
from datetime import date
from http.server import ThreadingHTTPServer

import pytest

from love_fortune import chapters, content_store, facts

BIRTH = date(1990, 5, 5)
TARGET = date(2026, 9, 24)


@pytest.fixture(scope="module")
def sheet():
    return facts.build(BIRTH, 14, 30, "female", "서울", TARGET)


@pytest.fixture(autouse=True)
def temp_content_db(tmp_path, monkeypatch):
    monkeypatch.setattr(content_store, "DB", tmp_path / "content.db")
    monkeypatch.setattr(content_store, "_READY", False)


def test_facts_have_no_personal_data(sheet):
    blob = json.dumps(sheet, ensure_ascii=False)
    for bad in ("1990", "05-05", "서울", "14:30"):
        assert bad not in blob
    assert sheet["meta"]["age"] == 36 and sheet["meta"]["age_kr"] == 37 and sheet["meta"]["sex"] == "여성"


def test_facts_shape(sheet):
    assert [p["key"] for p in sheet["natal"]["pillars"]] == ["year", "month", "day", "hour"]
    assert sum(sheet["natal"]["elements"].values()) == 8
    for dom in ("love", "career", "money"):
        assert len(sheet[dom]["months"]) == 12 and len(sheet[dom]["years"]) == 3
    assert {s["name"] for s in sheet["today"]["systems"]} == {"사주", "자미두수", "점성술"}


def test_hour_unknown_drops_hour_pillar():
    f = facts.build(BIRTH, None, 0, "male", "서울", TARGET)
    assert [p["key"] for p in f["natal"]["pillars"]] == ["year", "month", "day"]
    assert f["meta"]["hour_known"] is False


def test_every_chapter_picks_existing_facts(sheet):
    for tab, t in chapters.TABS.items():
        for ch in t["chapters"]:
            part = chapters.pick(sheet, ch["pick"])
            assert len(part) > 1, (tab, ch["id"])


def test_rule_fallback_for_every_chapter(sheet):
    for tab, t in chapters.TABS.items():
        for ch in t["chapters"]:
            body = chapters.generate(tab, ch["id"], sheet, use_ai=False)
            assert body["source"] == "rule" and body["blocks"]
            assert all(b["type"] in chapters.BLOCK_TYPES for b in body["blocks"])


def test_normalize_cleans_ai_output():
    raw = {"headline": "좋은 흐름" + chr(0x2014) + "이야", "lead": "사랑" + chr(0x611B) + " 이야기",
           "blocks": [{"type": "text", "body": "만날 확률이 80%야. 천천히 가도 좋아."},
                      {"type": "bogus", "body": "x"},
                      {"type": "checklist", "items": ["하나", "", "둘"]}]}
    out = chapters.normalize(raw)
    assert chr(0x2014) not in out["headline"] and chr(0x611B) not in out["lead"]
    assert out["blocks"][0]["body"] == "천천히 가도 좋아."
    assert [b["type"] for b in out["blocks"]] == ["text", "checklist"]
    assert out["blocks"][1]["items"] == ["하나", "둘"]
    with pytest.raises(ValueError):
        chapters.normalize({"blocks": [{"type": "quote", "body": "한 줄"}]})


def test_ai_chapter_is_cached(sheet, monkeypatch):
    calls = []

    def fake(system, prompt, timeout=0):
        calls.append(prompt)
        assert "1990" not in prompt
        return {"headline": "요약", "lead": "도입", "blocks": [{"type": "text", "body": "풀이"},
                                                               {"type": "quote", "body": "한 줄"}]}

    monkeypatch.setattr(chapters.ai, "available", lambda: True)
    monkeypatch.setattr(chapters.ai, "run_json", fake)
    a = chapters.generate("life", "love_nature", sheet)
    b = chapters.generate("life", "love_nature", sheet)
    assert a["source"] == b["source"] == "ai" and len(calls) == 1


@pytest.fixture()
def server(monkeypatch):
    from love_fortune import web
    monkeypatch.setenv("LOVE_FORTUNE_AI", "0")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _post(url, obj):
    req = urllib.request.Request(url, data=json.dumps(obj).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def test_v2_api_flow(server):
    rep = _post(server + "/api/v2/report", {"birth": "1990-05-05", "birth_time": "14:30",
                                            "sex": "female", "city": "서울"})
    assert rep["ai"] is False and set(rep["outline"]) == set(chapters.TABS)
    ch = _post(server + "/api/v2/chapter", {"token": rep["token"], "tab": "career", "chapter": "score"})
    assert ch["source"] == "rule"
    with pytest.raises(urllib.error.HTTPError) as e:
        _post(server + "/api/v2/chapter", {"token": "nope", "tab": "love", "chapter": "score"})
    assert e.value.code == 400


def test_static_paths(server):
    with urllib.request.urlopen(server + "/") as r:
        assert "app.js" in r.read().decode("utf-8")
    for bad in ("/classic", "/static/../web.py", "/static/x.js", "/img/abc.webp", "/api/v2/portrait"):
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(server + bad)
        assert e.value.code == 404


# ---------------------------------------------------------------- 계산 풀이·미리 만들기

def _all_text(body: dict) -> str:
    out = [body["headline"], body["lead"], body["closing"]]
    for b in body["blocks"]:
        out += [b.get("title", ""), b.get("body", "")]
        for i in b.get("items", []):
            out += [i] if isinstance(i, str) else [i["title"], i["body"]]
    return " ".join(x for x in out if x)


@pytest.mark.parametrize("hour", [14, None])
def test_rule_chapters_read_clean(hour):
    import re
    f = facts.build(BIRTH, hour, 30, "female", "서울", TARGET)
    rules = chapters.rule_all(f)
    cjk = re.compile("[" + chr(0x4E00) + "-" + chr(0x9FFF) + chr(0x2014) + "]")
    for tab, t in chapters.TABS.items():
        assert set(rules[tab]) == {c["id"] for c in t["chapters"]}
        for ch, body in rules[tab].items():
            txt = _all_text(body)
            assert body["headline"] and body["blocks"], (tab, ch)
            assert "None" not in txt and "{" not in txt and not cjk.search(txt), (tab, ch)
            assert "돈로" not in txt and "'절'야" not in txt, (tab, ch)


def test_lifetime_decade_uses_majority_dayun():
    # 대운이 30.0세에 바뀌는 사주: 30~39세는 끝나는 무인운이 아니라 새 정축운으로 본다
    f = facts.build(BIRTH, 14, 30, "female", "서울", TARGET)
    assert "정축운" in f["life"]["current"]
    assert "대운 시작 전" not in " ".join(f["life"]["decades"][1]["parts"][:1])


def test_josa_skips_quotes():
    from love_fortune.josa import j
    assert j("'절'", "야") == "'절'이야" and j("'묘'", "야") == "'묘'야"


def test_prefetch_orders_dedupes_and_waits(sheet, monkeypatch):
    import time
    from love_fortune import prefetch
    calls = []

    def fake_generate(tab, ch, f, use_ai=True):
        calls.append((tab, ch))
        time.sleep(0.01)
        return {"headline": ch, "lead": "", "blocks": [], "closing": "", "source": "ai"}

    monkeypatch.setattr(prefetch.chapters, "generate", fake_generate)
    with prefetch._cv:
        prefetch._jobs.clear()
        prefetch._heap.clear()
    n = prefetch.submit_all(sheet)
    got = prefetch.wait("life", "final", sheet, timeout=10)       # 맨 뒤 챕터를 당겨 받는다
    assert got and got["headline"] == "final"
    prefetch.submit_all(sheet)                                      # 같은 사실표는 다시 만들지 않는다
    deadline = time.time() + 20
    while prefetch.pending() and time.time() < deadline:
        time.sleep(0.05)
    assert prefetch.pending() == 0
    assert len(calls) == n == len(set(calls))
    assert calls.index(("life", "final")) < calls.index(("life", "dayun"))


def test_v2_report_includes_rule_chapters(server):
    rep = _post(server + "/api/v2/report", {"birth": "1990-05-05", "birth_time": "14:30",
                                            "sex": "female", "city": "서울"})
    for tab, t in chapters.TABS.items():
        for c in t["chapters"]:
            assert rep["rules"][tab][c["id"]]["source"] == "rule"


def test_ground_drops_invented_numbers_and_certainty():
    part = {"love.best": ["2027년 6월(병오)"], "meta": {"age": 36}}
    body = {"headline": "2027년 6월이 좋아", "lead": "36세의 너는 흐름이 좋아. 29세에 만난 사람이 있어.",
            "blocks": [{"type": "text", "title": "", "body": "3개월 안에 인연이 올 거야. 천천히 가도 좋아."},
                       {"type": "checklist", "title": "", "items": ["하루 30분 걷기", "먼저 인사하기"]},
                       {"type": "steps", "title": "", "items": [{"title": "STEP", "body": "반드시 결혼한다."},
                                                                {"title": "둘", "body": "대화를 늘려 봐."}]}],
            "closing": ""}
    out = chapters.ground(body, part)
    assert out["headline"] == "2027년 6월이 좋아"
    assert out["lead"] == "36세의 너는 흐름이 좋아."
    assert out["blocks"][0]["body"] == "천천히 가도 좋아."
    assert out["blocks"][1]["items"] == ["먼저 인사하기"]
    assert [i["body"] for i in out["blocks"][2]["items"]] == ["대화를 늘려 봐."]


def test_domain_tabs_are_today_only(sheet):
    # 연애·직장·금전 탭은 오늘 하루만: 챕터가 쓰는 사실은 today.* (연애 실전만 배우자궁·금성·만남 자리를 곁들인다)
    for tab in ("love", "career", "money"):
        for ch in chapters.TABS[tab]["chapters"]:
            extra = [p for p in ch["pick"] if not p.startswith("today.")]
            assert not extra or (tab == "love" and ch["id"] == "howto"), (tab, ch["id"], extra)
            assert not any(w.split(":")[0] in ("calendar", "years", "wonguk", "decades") for w in ch["widgets"])
    d = sheet["today"]["domains"]["love"]
    assert d["score"] == sheet["today"]["scores"]["love"]
    assert {s["name"] for s in d["systems"]} == {"사주", "자미두수", "점성술"}


def test_total_is_average_of_domains_plus_common(sheet):
    sc = sheet["today"]["scores"]
    avg = round((sc["love"] + sc["career"] + sc["money"]) / 3)
    assert abs(sc["total"] - avg) <= 12
    assert "평균" in sheet["today"]["total_reasons"][0]


def test_match_story_josa_and_no_duplicates():
    from love_fortune.matchmaking import compatibility
    r = compatibility(date(1990, 5, 5), 14, 30, "female", "서울", date(1988, 3, 3), 9, 0, "male", "부산")
    assert not any("흐름야" in x for x in r["story"])
    from love_fortune.web import api_match_data
    d = api_match_data(r)
    assert len(d["cautions"]) == len(set(d["cautions"]))


def test_domain_phrases_are_casual():
    import re
    from pathlib import Path
    src = Path(__file__).resolve().parent.parent / "love_fortune" / "domains.py"
    assert not re.findall(r'"[^"\n]*다"', src.read_text(encoding="utf-8"))


def test_share_roundtrip(server):
    rep = _post(server + "/api/v2/report", {"birth": "1990-05-05", "birth_time": "14:30",
                                            "sex": "female", "city": "서울"})
    sh = _post(server + "/api/v2/share", {"token": rep["token"]})
    assert sh["path"] == "/r/" + sh["id"]
    with urllib.request.urlopen(server + sh["path"]) as r:
        assert "app.js" in r.read().decode("utf-8")
    got = _post(server + "/api/v2/shared", {"id": sh["id"]})
    assert got["facts"] == rep["facts"] and got["token"] != rep["token"]
    blob = json.dumps(got, ensure_ascii=False)
    assert "1990-05-05" not in blob and "서울" not in blob
    ch = _post(server + "/api/v2/chapter", {"token": got["token"], "tab": "life", "chapter": "wonguk"})
    assert ch["blocks"]
    for bad in ("../x", "short"):
        with pytest.raises(urllib.error.HTTPError):
            _post(server + "/api/v2/shared", {"id": bad})


def test_chart_data_for_pictures(sheet):
    w = sheet["natal"]["astro"]["wheel"]
    assert len(w["bodies"]) == 7 and w["asc"] is not None
    assert all(0 <= b["lon"] < 360 for b in w["bodies"])
    pals = sheet["natal"]["ziwei"]["palaces"]
    assert sorted(p["branch"] for p in pals) == sorted("자축인묘진사오미신유술해")
    assert sum(p["now_daxian"] for p in pals) == 1 and sum(p["liunian"] for p in pals) == 1
    f = facts.build(BIRTH, None, 0, "female", "서울", TARGET)
    assert f["natal"]["astro"]["wheel"]["asc"] is None and f["natal"]["ziwei"] is None


def test_openrouter_backend(monkeypatch):
    import importlib
    from love_fortune import ai
    monkeypatch.setenv("LOVE_FORTUNE_AI_BACKEND", "openrouter")
    monkeypatch.setenv("LOVE_FORTUNE_OPENROUTER_MODEL", "some-provider/some-model")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    mod = importlib.reload(ai)
    try:
        assert mod.available() is False and mod.AI_MODEL == "some-provider/some-model"
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        assert mod.available() is True
        seen = {}

        class R:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return json.dumps({"choices": [{"message": {"content": '{"a": 1}'}}]}).encode()

        def fake_open(req, timeout=0):
            seen["url"], seen["auth"] = req.full_url, req.get_header("Authorization")
            seen["body"] = json.loads(req.data.decode())
            return R()

        monkeypatch.setattr(urllib.request, "urlopen", fake_open)
        assert mod.run_json("시스템", "질문") == {"a": 1}
        assert seen["auth"] == "Bearer test-key" and seen["body"]["model"] == "some-provider/some-model"
        assert seen["body"]["messages"][0] == {"role": "system", "content": "시스템"}
    finally:
        monkeypatch.delenv("LOVE_FORTUNE_AI_BACKEND")
        importlib.reload(ai)


def test_look_back_and_new_year(sheet):
    past = sheet["past"]
    assert past["rows"] and all(r["year"] < 2026 for r in past["rows"])
    sat = past["returns"]["saturn"]
    assert sat and sat[0]["start"][:4] in ("2019", "2020", "2021")          # 1990년생 첫 토성 회귀는 29~30세
    assert any(m["kind"] == "gyowun" for r in past["rows"] for m in r["marks"])
    ny = sheet["newyear"]
    assert ny["year"] == 2027 and ny["ganzhi"] == "정미"                      # 9월 이후엔 다음 해
    assert set(ny["months"]) == {"love", "career", "money"} and len(ny["months"]["love"]) == 12
    assert ny["ziwei"]["hua"] and len(ny["sky"]) == 2
    from love_fortune.newyear import target_year
    assert target_year(date(2026, 3, 1)) == 2026 and target_year(date(2026, 9, 1)) == 2027


def test_together_days_and_ilju(sheet):
    from love_fortune.web import together_days
    a = (date(1990, 5, 5), 14, 30, "female", "서울")
    b = (date(1988, 3, 3), 9, 0, "male", "부산")
    t = together_days(a, b, date(2026, 10, 1), 30)
    assert len(t["good"]) == 5 and len(t["tense"]) == 2
    assert t["good"][0]["both"] >= t["good"][-1]["both"] >= t["tense"][0]["both"]
    c = sheet["natal"]["ilju"]
    assert c["pillar"] == "경오" and c["title"] == "바위와 말" and c["modern"] == "흰 말"


def test_tojeong_matches_published_examples():
    from love_fortune import tojeong as T
    from love_fortune.tojeong_data import GUA
    # CHUNUN 예시: 1976 음력 8월 26일생의 2005년 = 212 (세는나이 30, 태세 20, 작은달 29 + 월건 14, 일진 병진 18)
    assert T.gua(1976, 8, 26, 2005)["gua"] == 212
    # 명문당 예시: 신사년 5월 갑오월 월건 18 + 큰달 30 → 중괘 6, 5월 16일 경오일 일진 15 → 하괘 1
    r = T.gua(1970, 5, 16, 2001)
    assert str(r["gua"])[1:] == "61" and "18(갑오월)" in r["steps"]["middle"] and "15(경오일)" in r["steps"]["lower"]
    # 만복가 예시: 계미년 32세 상괘 2, 7월 경신월 큰달 → 중괘 3, 7월 9일 신해일 → 하괘 1
    assert T.gua(1972, 7, 9, 2003)["gua"] == 231
    assert len(GUA) == 144 and {u * 100 + m * 10 + l for u in range(1, 9) for m in range(1, 7) for l in range(1, 4)} == set(GUA)


def test_remember_me_is_opt_in_and_device_only():
    """'이 기기에 기억하기'는 켜야만 저장하고, 브라우저에만 두며, 이름표·기억 칸은 서버에 보내지 않는다."""
    from love_fortune.web import STATIC_DIR
    html_ = (STATIC_DIR / "app.html").read_text(encoding="utf-8")
    js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    assert 'name="remember" type="checkbox" value="1">' in html_     # 기본은 꺼짐 (checked 없음)
    assert 'name="remember" type="checkbox" value="1" checked' not in html_
    assert html_.index('id="people"') < html_.index('id="fMain"')     # 바로 보기가 입력칸보다 위
    assert "delete q.remember;delete q.nick;" in js
    assert "if(remember){peopleSave(" in js
    assert "localStorage.removeItem('saju.recent')" in js and "recentSave" not in js
