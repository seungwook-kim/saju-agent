"""오늘 세 체계 종합(today.py)과 리포트 구성."""
from datetime import date

from love_fortune.cli import build_report
from love_fortune.synthesis import detailed_reading

BIRTH, TARGET = date(1995, 2, 28), date(2026, 9, 24)


def test_three_systems_and_almanac():
    t = detailed_reading(BIRTH, 12, 0, "male", "부산", TARGET)["today"]
    assert [s["name"] for s in t["systems"]] == ["사주", "자미두수", "점성술"]
    assert all(s["signal"] in ("좋음", "보통", "조심") and s["lines"] for s in t["systems"])
    assert t["almanac"]["lines"] and t["agreement"] and t["focus"]
    assert all(-15 <= v <= 15 for v in t["adj"].values())
    # 태어난 시간을 모르면 자미두수는 빠진다
    t2 = detailed_reading(BIRTH, None, 0, "male", "부산", TARGET)["today"]
    assert [s["name"] for s in t2["systems"]] == ["사주", "점성술"]


def test_scores_have_no_random_jitter():
    # 같은 날 같은 입력이면 같은 점수, 그리고 해시 잡음이 없어 사주 층만으로 설명된다
    a = detailed_reading(BIRTH, 12, 0, "male", "부산", TARGET)["total"]
    b = detailed_reading(BIRTH, 12, 0, "male", "부산", TARGET)["total"]
    assert a == b


def test_report_order_today_first_then_natal_then_period():
    text, md = build_report(BIRTH, 12, 0, "male", "부산", TARGET)
    order = ["[오늘 세 체계 종합]", "[오늘 총운]", "[오늘 연애운]", "[오늘 직장운]", "[오늘 금전운]",
             "[타고난 명식]", "[이번 달·올해 흐름]", "[재미로 보는 점괘]"]
    pos = [text.index(x) for x in order]
    assert pos == sorted(pos)
    # 오늘 총운 칸 안에는 30일 표가 없다 (기간 칸으로 옮김)
    today_part = text[text.index("[오늘 총운]"):text.index("[타고난 명식]")]
    assert "일운 30일" not in today_part and "월별 직장 흐름" not in today_part
    # 출생 차트는 '지금' 이 아니라 '태어날 때'
    assert "태양은 지금" not in text and "태어날 때" in text
    assert "오미쿠지" not in text.split("[용어 풀이")[0]
    assert "## 오늘 세 체계 종합" in md and "1995" not in md and "부산" not in md
