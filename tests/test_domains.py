"""tests for domains.py, 4개 영역 + 한자·가나 없음 검증."""
import re
from datetime import date

from love_fortune.domains import (career_score, money_score, total_score,
                                  band_headline)
from love_fortune.synthesis import detailed_reading
from love_fortune.cli import build_report
from love_fortune.web import (render_report_page, agent_context,
                              local_agent_reply)

BIRTH = date(1995, 2, 28)
TARGET = date(2026, 9, 20)
HAN = re.compile(r"[\u4e00-\u9fff]")
KANA = re.compile(r"[\u3040-\u30ff]")


def test_domain_scores_range():
    for fn in (career_score, money_score):
        s, reasons, elem = fn(6, [11, 2, 2, 6], 3, 9, "x")
        assert 1 <= s <= 100
        assert reasons and elem in ("목", "화", "토", "금", "수")
    s, reasons, elem, kw = total_score(6, [11, 2, 2, 6], 3, 9, 51, 60, 70,
                                      ["록"], 6, "x")
    assert 1 <= s <= 100 and len(kw) == 3


def test_domain_deterministic():
    a = career_score(6, [11, 2, 2, 6], 3, 9, "seed")
    b = career_score(6, [11, 2, 2, 6], 3, 9, "seed")
    assert a == b


def test_band_headlines():
    assert band_headline(90, "career") != band_headline(10, "career")
    assert band_headline(90, "money") != band_headline(10, "money")
    assert band_headline(90, "total") != band_headline(10, "total")


def test_reading_has_domains():
    ma = detailed_reading(BIRTH, 12, 0, "male", "부산", TARGET)
    for k in ("career", "money", "total"):
        assert k in ma
    assert 1 <= ma["career"]["score"] <= 100
    assert len(ma["career"]["tips"]) == 3 and ma["career"]["avoid"]
    assert len(ma["money"]["tips"]) == 3 and ma["money"]["avoid"]
    assert len(ma["total"]["keywords"]) == 3
    assert len(ma["career"]["palaces"]) == 4
    assert len(ma["money"]["palaces"]) == 4
    assert ma["career"]["palaces"][0].startswith("본궁")
    text, md = build_report(BIRTH, 12, 0, "male", "부산", TARGET)
    assert "관록궁 삼방사정" in text and "재백궁 삼방사정" in text
    assert "관록궁 삼방" in md and "재백궁 삼방" in md
    # 심화 내용
    assert len(ma["dist"]) == 3 and "원국 분포" in ma["dist"][0]
    assert len(ma["career_extra"]) == 5 and "지금 대운" in ma["career_extra"][0]
    assert len(ma["money_extra"]) == 5 and "지금 대운" in ma["money_extra"][0]
    assert len(ma["love_extra"]) == 1 and "부처궁" in ma["love_extra"][0]
    assert "원국 분포" in text and "원국 분포" in md
    assert "토성(책임과 과제)은" in text and "금성(취향과 돈감각)은" in text


def test_monthly_readings():
    ma = detailed_reading(BIRTH, 12, 0, "male", "부산", TARGET)
    assert len(ma["monthly"]) == 12
    sep = next(r for r in ma["monthly"] if r["month"] == 9)
    assert sep["ganzhi"] == "정유"
    assert 1 <= sep["career"] <= 100 and 1 <= sep["money"] <= 100
    assert "으뜸은" in sep["line"]
    text, md = build_report(BIRTH, 12, 0, "male", "부산", TARGET)
    assert "월별 직장 흐름" in text and "월별 금전 흐름" in text
    assert "월별 직장 흐름" in md and "월별 금전 흐름" in md
    assert "으뜸은" not in md  # 총운 탭 월별 표는 제거됨
    a = detailed_reading(BIRTH, 12, 0, "male", "부산", TARGET)["monthly"]
    b = detailed_reading(BIRTH, 12, 0, "male", "부산", TARGET)["monthly"]
    assert a == b
    ma = detailed_reading(BIRTH, 12, 0, "male", "부산", TARGET)
    assert len(ma["dayun_full"]) == 8
    assert ma["dayun_full"][0].startswith("정축운")
    assert "소운" in ma["lifetime"]["years"][2]["line"]


def test_no_cjk_in_outputs():
    text, md = build_report(BIRTH, 12, 0, "male", "부산", TARGET)
    for blob in (text, md):
        assert not HAN.search(blob), HAN.search(blob).group(0)
        assert not KANA.search(blob)
    _, _, summary = agent_context(BIRTH, 12, 0, "male", "부산", TARGET)
    for q in ["안녕", "오늘 직장운 어때", "금전운 알려줘", "오늘 총운 어때",
              "배우자는 어떤 사람이야", "도화살 있어", "타로 알려줘"]:
        r = local_agent_reply(q, summary)
        assert not HAN.search(r), (q, HAN.search(r).group(0))
        assert not KANA.search(r)


def test_web_tabs():
    md, text, _ = agent_context(BIRTH, 12, 0, "male", "부산", TARGET)
    page = render_report_page(md, text, "tok123", "2026-09-20")
    for tab in ("tab-total", "tab-love", "tab-career", "tab-money"):
        assert tab in page, tab
    for word in ("오늘 총운", "오늘 연애운", "오늘 직장운", "오늘 금전운"):
        assert word in page, word
    assert "tok123" in page
    assert not HAN.search(page)
    # 링 점수와 본문 점수 일치 (회귀: 기본값 50 표시 버그 방지)
    import re as _re
    md_score = int(_re.search(r"오늘 총운: \*\*(\d+)점", md).group(1))
    ring = _re.search(r'<div class="ring"[^>]*>(\d+)</div>', page).group(1)
    assert ring == str(md_score), (ring, md_score)
    assert f"오늘 총운은 {md_score}점" in page
    assert "0~9세" in page and "80~89세" in page
    assert "연대별 타임라인" in page
    assert "<details>" in page and "연도별 표 펼치기" in page
