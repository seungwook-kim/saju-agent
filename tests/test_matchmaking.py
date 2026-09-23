"""tests for matchmaking.py, 궁합 엔진 검증."""
import re
from datetime import date

from love_fortune.matchmaking import compatibility
from love_fortune.cli import build_match_report
from love_fortune.web import render_match_page, local_agent_reply

A = (date(1995, 2, 28), 12, 0, "male", "부산")
B = (date(1997, 6, 15), 9, 0, "female", "서울")
HAN = re.compile(r"[\u4e00-\u9fff]")
KANA = re.compile(r"[\u3040-\u30ff]")


def _r():
    return compatibility(*A, *B)


def test_score_range_and_keys():
    r = _r()
    assert 1 <= r["score"] <= 100
    for k in ("head", "strengths", "cautions", "info",
              "a_ilgan", "b_ilgan", "a_day_branch", "b_day_branch"):
        assert k in r, k
    assert isinstance(r["strengths"], list)


def test_symmetric_and_deterministic():
    r1 = compatibility(*A, *B)
    r2 = compatibility(*B, *A)
    assert r1["score"] == r2["score"]
    r3 = compatibility(*A, *B)
    assert r1 == r3


def test_report_no_pii_and_clean():
    text, md = build_match_report(*A, *B)
    assert "궁합" in text and "잘 맞는 점" in text
    assert "## 잘 맞는 점" in md
    for pii in ("1995", "1997", "부산", "서울", "male", "female"):
        assert pii not in md, pii
    for blob in (text, md):
        assert not HAN.search(blob)
        assert not KANA.search(blob)
        assert "—" not in blob
    assert "할 것이다" not in text


def test_web_match_page_and_chat():
    r = _r()
    page, summary = render_match_page(r, "tok999")
    assert "tok999" in page
    assert str(r["score"]) in page
    assert "잘 맞는 점" in page
    assert "1995" not in page and "부산" not in page
    assert not HAN.search(page)
    reply = local_agent_reply("우리 궁합 어때", summary)
    assert "궁합" in reply
    reply2 = local_agent_reply("궁합이 뭐야", summary)
    assert reply2.startswith("궁합:")


def test_match_story():
    from love_fortune.matchmaking import compatibility
    r = compatibility(date(1995, 2, 28), 12, 0, "male", "부산",
                      date(1997, 6, 15), 9, 0, "female", "서울")
    assert len(r["story"]) >= 3 and str(r["score"]) in r["story"][0]
    assert "할 것이다" not in "".join(r["story"])
    reply = local_agent_reply("우리 궁합 어때", render_match_page(r, "t")[1])
    assert "두 사람 점수" in reply
