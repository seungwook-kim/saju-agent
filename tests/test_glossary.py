"""tests for glossary.py, 용어 풀이 검증."""
import re
from datetime import date

from love_fortune.glossary import TERMS, explain
from love_fortune.cli import build_report
from love_fortune.web import render_report_page, agent_context, local_agent_reply

BIRTH = date(1995, 2, 28)
TARGET = date(2026, 9, 20)
HAN = re.compile(r"[\u4e00-\u9fff]")
KANA = re.compile(r"[\u3040-\u30ff]")


def test_glossary_size_and_clean():
    assert len(TERMS) >= 100
    for term, desc in TERMS.items():
        assert not HAN.search(term + desc), term
        assert not KANA.search(term + desc), term
        assert "—" not in term + desc, term
    assert explain("정관") == TERMS["정관"]
    assert explain("없는용어") == ""


def test_glossary_in_report():
    text, md = build_report(BIRTH, 12, 0, "male", "부산", TARGET,
                            "all", True)
    assert "[용어 풀이" in text
    assert "## 용어 풀이" in md
    assert "- 일간:" in md and "- 화록:" in md


def test_glossary_chat():
    _, _, summary = agent_context(BIRTH, 12, 0, "male", "부산", TARGET)
    assert local_agent_reply("정관이 뭐야", summary).startswith("정관:")
    assert local_agent_reply("도화살이 뭐야?", summary).startswith("도화살:")
    assert local_agent_reply("상승궁이 뭔가요", summary).startswith("상승궁:")
    # 궁합이 도화보다 먼저 잡혀야 함 (긴 용어 우선)
    assert local_agent_reply("궁합이 뭐야", summary).startswith("궁합:")


def test_glossary_web_card():
    md, text, _ = agent_context(BIRTH, 12, 0, "male", "부산", TARGET)
    page = render_report_page(md, text, "tok123", "2026-09-20")
    assert "용어 풀이" in page
    assert "일간" in page
