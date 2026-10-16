"""절대 지어내지 않기, 나쁜 신호도 분명하게 (2026-09-28 사용자 결정)."""
import json
from datetime import date

import pytest

from love_fortune import chapters, facts, web
from love_fortune.chapters import ground_reply, terms_ok


@pytest.fixture(scope="module")
def summary():
    return web.agent_context(date(1990, 5, 5), 14, 30, "female", "서울", date(2026, 9, 28))[2]


def test_terms_must_be_in_facts():
    text = json.dumps({"ziwei": {"명궁": "탐랑", "재백": "화기"}, "astro": {"venus": "양자리"}}, ensure_ascii=False)
    assert terms_ok("명궁에 탐랑이 있어 끼가 많아.", text)
    assert terms_ok("재백궁에 화기가 붙어서 돈은 정말 조심해야 해.", text)      # 궁은 '궁' 뺀 이름으로 찾는다
    assert not terms_ok("부처궁에 천상이 있어서 좋은 배우자를 만나.", text)      # 사실표에 없는 궁·별
    assert not terms_ok("도화살이 들어와 인기가 많아.", text)                    # 없는 신살
    assert not terms_ok("금성이 전갈자리라 깊은 사랑을 해.", text)               # 없는 별자리
    assert terms_ok("자미두수와 사주, 점성술을 같이 보면 이래.", text)           # 체계 이름은 괜찮다


def test_strong_advice_ok_but_no_certain_future(summary):
    kept = ground_reply("이 달은 반드시 조심해. 너는 반드시 헤어질 것이다. 운명의 상대를 만나.", summary)
    assert "반드시 조심해" in kept and "헤어질" not in kept and "운명의 상대" not in kept


def test_chat_reply_drops_invented_terms_and_numbers(summary):
    reply = "오늘은 배우자성이 보여. 부처궁에 천상이 있어 좋은 사람을 만나. 52살에 결혼해."
    kept = ground_reply(reply, summary)
    assert "배우자성" in kept and "천상" not in kept and "52살" not in kept


def test_chapter_ground_drops_invented_terms():
    f = facts.build(date(1990, 5, 5), 14, 30, "female", "서울", date(2026, 9, 28))
    spec = chapters.TABS["love"]["chapters"][0]
    part = chapters.pick(f, spec["pick"])
    text = json.dumps(part, ensure_ascii=False)
    fake = next(t for t in ("천상", "파군", "천량", "칠살") if t not in text)
    body = {"headline": "연애 흐름", "lead": f"{fake}이 들어와 최고의 해야. 흐름을 볼게.", "closing": "",
            "blocks": [{"type": "text", "title": "t", "body": f"{fake} 덕분에 대박이야. 계산된 흐름을 볼게."}]}
    out = chapters.ground(body, part)
    assert fake not in json.dumps(out, ensure_ascii=False)


def test_prompts_say_bad_signs_plainly():
    assert "좋은 것만 골라 말하지 않는다" in chapters.SYSTEM and "분명하고 강하게" in chapters.SYSTEM
    assert "좋은 것만 골라 말하지 않는다" in web.SYSTEM_PROMPT and "절대 쓰지 않는다" in web.SYSTEM_PROMPT
    assert chapters.PROMPT_VERSION == "ch-9"


def test_chat_falls_back_to_calculation_when_all_invented(monkeypatch):
    # AI 답이 전부 지어낸 말이면 계산값 그대로의 답으로 바꾼다
    import urllib.request
    import threading
    from http.server import ThreadingHTTPServer
    monkeypatch.setattr(web, "cli_available", lambda: True)
    monkeypatch.setattr(web, "cli_chat", lambda *a: "부처궁에 천상이 있어서 37살에 운명의 상대를 만날 것이다.")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        def post(p, o):
            r = urllib.request.Request(base + p, data=json.dumps(o).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(r, timeout=30) as x:
                return json.loads(x.read())
        rep = post("/api/v2/report", {"birth": "1990-05-05", "birth_time": "14:30", "sex": "female", "city": "서울"})
        j = post("/api/chat", {"token": rep["token"], "message": "올해 연애운 어때"})
        assert j["mode"] == "local" and "천상" not in j["reply"] and "37살" not in j["reply"]
    finally:
        srv.shutdown()


def test_numbered_lines_kept_and_renumbered(summary):
    reply = "올해 흐름은 이래.\n1. 배우자성이 보여.\n2. 부처궁에 천상이 있어.\n3. 이 달은 반드시 조심해."
    kept = ground_reply(reply, summary)
    assert kept.splitlines() == ["올해 흐름은 이래.", "1. 배우자성이 보여.", "2. 이 달은 반드시 조심해."]


def test_numbered_formats_calculation_answers():
    assert chapters.numbered("오늘 직장운은 이래: 점수 60 / 관록궁 칠살 / 조심할 날") == \
        "오늘 직장운은 이래:\n1. 점수 60.\n2. 관록궁 칠살.\n3. 조심할 날."
    assert chapters.numbered("정관: 원칙과 책임의 기운") == "정관: 원칙과 책임의 기운"
    assert "1. 짧은 제목: 설명" in web.SYSTEM_PROMPT and "steps" in chapters.SYSTEM


def test_english_words_dropped(summary):
    # 우리말 풀이에 영어 단어가 섞인 문장은 뺀다 (2026-10-16 운영 학업 장 'Pace 조절이 관건이야')
    assert not chapters.latin_ok("Pace 조절이 관건이야.")
    assert chapters.latin_ok("IT 쪽 일과 잘 맞고 TOP 3 안에 들어.") and chapters.latin_ok("STEP 1, 정리부터 해.")
    kept = ground_reply("오늘은 Pace 조절이 관건이야. 천천히 정리해 봐.", summary)
    assert "Pace" not in kept and "천천히 정리해 봐" in kept
    body = {"headline": "Focus 가 중요한 날", "lead": "기본기에 힘쓰기 좋은 흐름이야.", "closing": "",
            "blocks": [{"type": "text", "title": "t", "body": "Routine 을 지켜. 복습이 핵심이야."}]}
    out = chapters.ground(body, {"x": 1})
    assert out["headline"] == "" and "Routine" not in json.dumps(out) and out["blocks"][0]["body"] == "복습이 핵심이야."
