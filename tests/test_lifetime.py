"""tests for lifetime.py, 평생 타임라인 검증."""
import re
from datetime import date

from love_fortune.lifetime import lifetime_reading
from love_fortune.cli import build_report
from love_fortune.web import local_agent_reply, agent_context

BIRTH = date(1995, 2, 28)
TARGET = date(2026, 9, 20)
HAN = re.compile(r"[\u4e00-\u9fff]")
KANA = re.compile(r"[\u3040-\u30ff]")


def test_lifetime_structure():
    lt = lifetime_reading(BIRTH, 12, 0, "male", "부산", TARGET)
    assert len(lt["decades"]) == 9
    assert lt["decades"][0]["range"] == (0, 9)
    assert [p["name"] for p in lt["phases"]] == ["초년", "중년", "말년"]
    assert len(lt["years"]) == 11
    row2026 = next(y for y in lt["years"] if y["year"] == 2026)
    assert row2026["age"] == 31
    assert "병오" in row2026["line"] and "유년 부처" in row2026["line"]
    assert "현재연대" not in row2026["line"]
    assert "30~39세" in lt["current"]["line"]
    assert "아래 연대별" in lt["current"]["short"]
    assert "몸은" in lt["decades"][3]["parts"][-1]


def test_lifetime_deterministic():
    a = lifetime_reading(BIRTH, 12, 0, "male", "부산", TARGET)
    b = lifetime_reading(BIRTH, 12, 0, "male", "부산", TARGET)
    assert a == b


def test_lifetime_in_report_and_md():
    text, md = build_report(BIRTH, 12, 0, "male", "부산", TARGET,
                            "all", True)
    assert "[평생 운세 타임라인]" in text
    assert "## 평생 운세" in md
    assert "[연대]" in md and "[해]" in md
    text2, _ = build_report(BIRTH, 12, 0, "male", "부산", TARGET)
    assert "[평생 운세 타임라인]" not in text2


def test_lifetime_no_cjk_no_pii():
    text, md = build_report(BIRTH, 12, 0, "male", "부산", TARGET,
                            "all", True)
    for blob in (text, md):
        assert not HAN.search(blob)
        assert not KANA.search(blob)
    for pii in ("1995-02-28", "1995", "부산", "male"):
        assert pii not in md


def test_lifetime_chat():
    _, _, summary = agent_context(BIRTH, 12, 0, "male", "부산", TARGET)
    r = local_agent_reply("평생 운세가 궁금해", summary)
    assert "평생" in r
    r2 = local_agent_reply("앞으로 10년은 어때", summary)
    assert "평생" in r2 or "연대" in r2
    r3 = local_agent_reply("내 용신이 뭐야", summary)
    assert "용신" in r3 or "평생" in r3


def test_lifetime_yongsin_cards():
    from love_fortune.cli import build_report as _br
    _, md = _br(BIRTH, 12, 0, "male", "부산", TARGET, "all", True)
    assert "타고난 기질" in md and "신강약 추정" in md
    assert "격국" in md and "[대운]" in md
