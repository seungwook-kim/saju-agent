"""새 화면(탭·챕터·삽화)용 사실표·챕터·API 검사. AI·이미지 서버 없이 돈다."""
import json
import threading
import urllib.request
from datetime import date
from http.server import ThreadingHTTPServer

import pytest

from love_fortune import chapters, content_store, facts, portrait

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
    assert sheet["meta"]["age"] == 37 and sheet["meta"]["sex"] == "여성"


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
        return {"headline": "요약", "lead": "도입", "blocks": [{"type": "text", "body": "풀이"}]}

    monkeypatch.setattr(chapters.ai, "available", lambda: True)
    monkeypatch.setattr(chapters.ai, "run_json", fake)
    a = chapters.generate("love", "map", sheet)
    b = chapters.generate("love", "map", sheet)
    assert a["source"] == b["source"] == "ai" and len(calls) == 1


def test_portrait_scenes_are_deterministic(sheet):
    for tab, slots in {"love": ["partner"], "career": ["mentor"], "money": ["partner"],
                       "today": ["me"], "life": ["20s", "40s", "60s"]}.items():
        sc = portrait.scenes(tab, sheet)
        assert [s["slot"] for s in sc] == slots
        assert sc == portrait.scenes(tab, sheet)
        for s in sc:
            assert "Korean" in s["prompt"] and "서울" not in s["prompt"]


def test_portrait_off_when_server_down(sheet, monkeypatch):
    monkeypatch.setattr(portrait, "server_up", lambda: False)
    r = portrait.render("love", "partner", sheet)
    assert r["status"] == "off" and r["caption"]


@pytest.fixture()
def server(monkeypatch):
    from love_fortune import web
    monkeypatch.setenv("LOVE_FORTUNE_AI", "0")
    monkeypatch.setattr(portrait, "server_up", lambda: False)
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
    ch = _post(server + "/api/v2/chapter", {"token": rep["token"], "tab": "career", "chapter": "wonguk"})
    assert ch["source"] == "rule"
    pt = _post(server + "/api/v2/portrait", {"token": rep["token"], "tab": "life", "slot": "40s"})
    assert pt["status"] == "off"
    with pytest.raises(urllib.error.HTTPError) as e:
        _post(server + "/api/v2/chapter", {"token": "nope", "tab": "love", "chapter": "map"})
    assert e.value.code == 400


def test_static_and_image_paths(server):
    with urllib.request.urlopen(server + "/") as r:
        assert "app.js" in r.read().decode("utf-8")
    with urllib.request.urlopen(server + "/classic") as r:
        assert r.status == 200
    for bad in ("/static/../web.py", "/static/x.js", "/img/../../pyproject.toml", "/img/abc.webp"):
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(server + bad)
        assert e.value.code == 404
