"""tests for unknown birth time, 시간 미상 경로 검증."""
import re
from datetime import date

from love_fortune.cli import build_report, _parse_hm
from love_fortune.manseryuk import four_pillars
from love_fortune.synthesis import detailed_reading
from love_fortune.web import agent_context, local_agent_reply
from love_fortune.matchmaking import compatibility
from love_fortune.taekil import pick_dates
from love_fortune.ziwei import ziwei_chart
from love_fortune.lifetime import lifetime_reading

BIRTH = date(1995, 2, 28)
TARGET = date(2026, 9, 20)
HAN = re.compile(r"[\u4e00-\u9fff]")
KANA = re.compile(r"[\u3040-\u30ff]")


def test_parse_hm_unknown():
    assert _parse_hm("모름") == (None, 0)
    assert _parse_hm("unknown") == (None, 0)
    assert _parse_hm("12:00") == (12, 0)


def test_four_pillars_unknown():
    n = four_pillars(BIRTH, None, 0, "부산")
    assert n["hour_unknown"] is True
    assert n["pillars"]["hour"] == (None, None)
    assert n["strings"]["hour"] == "시간 미상"


def test_ziwei_none_when_unknown():
    assert ziwei_chart(BIRTH, None, 0, "male", "부산") is None


def test_report_unknown_runs_clean():
    text, md = build_report(BIRTH, None, 0, "male", "부산", TARGET, "all", True)
    assert "시간 미상" in text and "시간 미상" in md
    assert "오늘 연애운" in text and "오늘 직장운" in text
    for blob in (text, md):
        assert not HAN.search(blob)
        assert not KANA.search(blob)
        assert "—" not in blob
        assert "할 것이다" not in blob
        for pii in ("1995", "부산", "male"):
            assert pii not in md, pii


def test_report_unknown_deterministic():
    a = build_report(BIRTH, None, 0, "male", "부산", TARGET, "all", True)
    b = build_report(BIRTH, None, 0, "male", "부산", TARGET, "all", True)
    assert a == b


def test_reading_unknown_fields():
    ma = detailed_reading(BIRTH, None, 0, "male", "부산", TARGET)
    assert ma["hour_unknown"] is True
    assert ma["ziwei"] is None
    assert ma["time_notice"]
    assert len(ma["meet_top3"]) == 3
    assert len(ma["ilun"]) == 30


def test_lifetime_unknown():
    lt = lifetime_reading(BIRTH, None, 0, "male", "부산", TARGET)
    assert len(lt["decades"]) == 9 and len(lt["years"]) == 11
    assert "시간 미상" in lt["decades"][0]["line"]


def test_chat_unknown():
    md, text, summary = agent_context(BIRTH, None, 0, "male", "부산", TARGET)
    assert "시간안내" in summary
    r = local_agent_reply("오늘 직장운 어때", summary)
    assert "직장운" in r
    r2 = local_agent_reply("자미두수 알려줘", summary)
    assert "미상" in r2 or "자미" in r2


def test_match_unknown():
    r = compatibility(BIRTH, None, 0, "male", "부산",
                      date(1997, 6, 15), 9, 0, "female", "서울")
    assert 1 <= r["score"] <= 100
    assert "시간 미상" in r["a_mingong"]


def test_pick_unknown():
    r = pick_dates(BIRTH, None, 0, "male", "부산",
                   date(2026, 10, 1), date(2026, 10, 7), "total")
    assert r["count"] == 7 and len(r["story"]) == 3
