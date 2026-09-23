"""tests for taekil.py, 길일 고르기 검증."""
import re
from datetime import date

from love_fortune.taekil import pick_dates, MAX_DAYS
from love_fortune.cli import build_pick_report
from love_fortune.web import render_pick_page, local_agent_reply

BIRTH = date(1995, 2, 28)
S = date(2026, 10, 1)
E = date(2026, 10, 7)
HAN = re.compile(r"[一-鿿]")
KANA = re.compile(r"[぀-ヿ]")


def test_pick_structure_and_order():
    r = pick_dates(BIRTH, 12, 0, "male", "부산", S, E, "total")
    assert r["count"] == 7 and r["domain"] == "total"
    scores = [x["total"] for x in r["rows"]]
    assert scores == sorted(scores, reverse=True)
    assert [x["rank"] for x in r["rows"]] == list(range(1, 8))
    for row in r["rows"]:
        assert 1 <= row["love"] <= 100
        assert 1 <= row["career"] <= 100
        assert 1 <= row["money"] <= 100


def test_pick_deterministic_and_limits():
    a = pick_dates(BIRTH, 12, 0, "male", "부산", S, E, "love")
    b = pick_dates(BIRTH, 12, 0, "male", "부산", S, E, "love")
    assert a == b
    try:
        pick_dates(BIRTH, 12, 0, "male", "부산", S, date(2027, 6, 1), "total")
        raise AssertionError("62일 초과 허용됨")
    except ValueError:
        pass
    try:
        pick_dates(BIRTH, 12, 0, "male", "부산", E, S, "total")
        raise AssertionError("역전 허용됨")
    except ValueError:
        pass


def test_pick_story():
    r = pick_dates(BIRTH, 12, 0, "male", "부산", S, E, "total")
    assert len(r["story"]) == 3 and "1위" in r["story"][0]
    assert "할 것이다" not in "".join(r["story"])
    assert not HAN.search("".join(r["story"]))
    text, md = build_pick_report(BIRTH, 12, 0, "male", "부산", S, E, "total", 3)
    assert "1위" in text and "1위" in md


def test_pick_report_clean():
    text, md = build_pick_report(BIRTH, 12, 0, "male", "부산", S, E, "total", 3)
    assert "길일 고르기" in text and "상위 3일" in text
    assert "## 상위 일자" in md and "## 전체 표" in md
    for pii in ("1995", "부산", "male"):
        assert pii not in md, pii
    for blob in (text, md):
        assert not HAN.search(blob)
        assert not KANA.search(blob)
        assert "—" not in blob


def test_pick_web_and_chat():
    from love_fortune.taekil import pick_dates as _pd
    r = _pd(BIRTH, 12, 0, "male", "부산", S, E, "career")
    page, summary = render_pick_page(r, "tok777")
    assert "tok777" in page and "길일" in page
    assert "1995" not in page and "부산" not in page
    reply = local_agent_reply("좋은 날 골라줘", summary)
    assert "택일" in reply or "상위" in reply
