"""원국 상세(지장간·12운성·신살·귀인·띠 궁합)와 월운·세운 시그널."""
from datetime import date

from love_fortune.manseryuk import four_pillars, STEMS_KR, BRANCHES_KR
from love_fortune.natal_extra import (HIDDEN, MUNCHANG, amrok, animal_compat, geumyeo, hakdang,
                                      natal_sinsal, pillars_detail, sinsal12_at)
from love_fortune.signals import month_signals, year_signals

S = lambda s: STEMS_KR.index(s)
B = lambda b: BRANCHES_KR.index(b)


def test_hidden_stems_korean_table():
    # 정해 만세력 월률분야 표 (여기·중기·정기)
    ref = {"자": "임계", "축": "계신기", "인": "무병갑", "묘": "갑을", "진": "을계무", "사": "무경병",
           "오": "병기정", "미": "정을기", "신": "무임경", "유": "경신", "술": "신정무", "해": "무갑임"}
    for b, stems in ref.items():
        assert "".join(STEMS_KR[x] for x in HIDDEN[B(b)]) == stems, b


def test_sinsal12_rule():
    # 해묘미 삼합: 겁살 신, 재살 유, 천살 술, 지살 해, 년살 자, 월살 축, 망신 인, 장성 묘,
    # 반안 진, 역마 사, 육해 오, 화개 미 (대구신문 칼럼 등)
    ref = ["겁살", "재살", "천살", "지살", "년살", "월살", "망신살", "장성살", "반안살", "역마살", "육해살", "화개살"]
    for name, br in zip(ref, "신유술해자축인묘진사오미"):
        assert sinsal12_at(B("해"), B(br)) == name


def test_guiin_tables():
    assert [BRANCHES_KR[MUNCHANG[s]] for s in range(10)] == list("사오신유신유해자인묘")
    assert BRANCHES_KR[hakdang(S("경"))] == "사" and BRANCHES_KR[hakdang(S("갑"))] == "해"
    assert BRANCHES_KR[amrok(S("신"))] == "진" and BRANCHES_KR[amrok(S("경"))] == "사"
    assert BRANCHES_KR[geumyeo(S("갑"))] == "진" and BRANCHES_KR[geumyeo(S("을"))] == "사"


def test_sample_chart_matches_reference_result():
    # 1995-02-28 사시: 월률분야 지장간·12운성·12신살 표로 손계산한 값
    n = four_pillars(date(1995, 2, 28), 10, 0, "서울")
    p = {x["key"]: x for x in pillars_detail(n)}
    assert p["hour"]["hidden"] == ["무", "경", "병"] and p["hour"]["stage"] == "장생"
    assert [p[k]["stage"] for k in ("year", "month", "day")] == ["병", "절", "절"]
    s = natal_sinsal(n)
    assert {g["name"] for g in s["guiin"]} == {"문창귀인", "학당귀인", "암록"}
    names = {x["name"] for x in s["sinsal"]}
    assert {"겁살", "망신살"} <= names


def test_animal_compat_standard_rule():
    a = animal_compat(B("해"))
    assert {x["animal"] for x in a["good"]} == {"호랑이", "토끼", "양"}
    assert {x["animal"] for x in a["bad"]} == {"뱀", "원숭이", "용"}


def test_signals_have_reasons():
    n = four_pillars(date(1995, 2, 28), 10, 0, "서울")
    ms = month_signals(n, "male", date(2026, 9, 24))
    assert len(ms) == 12 and ms[0]["ganzhi"] == "정유"
    mar = next(r for r in ms if (r["year"], r["month"]) == (2027, 3))
    assert mar["labels"]["love"] == "밀고 나갈 때" and "도화(끌림의 별)가 드는 때" in mar["why"]["love"]
    ys = year_signals(n, "male", 2026)
    assert [r["ganzhi"] for r in ys] == ["병오", "정미", "무신"]
