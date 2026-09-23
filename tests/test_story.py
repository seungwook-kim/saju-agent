"""tests for story.py, 이야기식 해설 검증."""
import re
from datetime import date

from love_fortune.story import build_stories
from love_fortune.synthesis import detailed_reading
from love_fortune.cli import build_report
from love_fortune.web import render_report_page, agent_context, local_agent_reply

BIRTH = date(1995, 2, 28)
TARGET = date(2026, 9, 20)
HAN = re.compile(r"[\u4e00-\u9fff]")
KANA = re.compile(r"[\u3040-\u30ff]")


def _ma():
    return detailed_reading(BIRTH, 12, 0, "male", "부산", TARGET)


def test_stories_structure_and_clean():
    from love_fortune.manseryuk import four_pillars
    from love_fortune.advise import build_advice
    natal = four_pillars(BIRTH, 12, 0, "부산")
    ma = _ma()
    adv = build_advice(natal["ilgan"], "화", TARGET, BIRTH)
    stories = build_stories(natal, ma, adv, TARGET)
    assert set(stories) == {"total", "love", "career", "money", "life"}
    for key, paras in stories.items():
        assert len(paras) >= 2, key
        for p in paras:
            assert not HAN.search(p), (key, p[:40])
            assert not KANA.search(p)
            assert "—" not in p
    assert "부처궁" in " ".join(stories["love"])
    assert "관록궁" in " ".join(stories["career"])


def test_stories_in_report_and_page():
    text, md = build_report(BIRTH, 12, 0, "male", "부산", TARGET,
                            "all", True)
    assert "[이야기]" in md
    page = render_report_page(md, text, "tok123", "2026-09-20")
    assert "오늘 이야기" in page and "연애 이야기" in page
    assert "직장 이야기" in page and "금전 이야기" in page
    assert "평생 이야기" in page


def test_story_chat():
    _, _, summary = agent_context(BIRTH, 12, 0, "male", "부산", TARGET)
    r = local_agent_reply("쉽게 설명해줘", summary)
    assert "총운" in r
    r2 = local_agent_reply("직장운 쉽게 풀어줘", summary)
    assert "직장" in r2
