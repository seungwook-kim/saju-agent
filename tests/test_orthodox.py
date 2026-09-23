"""tests for orthodox upgrade, 음력·절기·자미·실측점성·대운 검증."""
from datetime import date, datetime

from love_fortune.lunar import solar_to_lunar, true_solar_time
from love_fortune.astronomy import sun_position, day_number, solar_term_moment
from love_fortune.ziwei import ziwei_chart
from love_fortune.astro import natal_chart, astro_chart
from love_fortune.manseryuk import four_pillars, dayun, shensha
from love_fortune.synthesis import detailed_reading
from love_fortune.cli import build_report

BIRTH = date(1995, 2, 28)
TARGET = date(2026, 9, 20)


def test_lunar_anchors():
    assert solar_to_lunar(1995, 2, 28) == (1995, 1, 29, False)
    assert solar_to_lunar(2024, 2, 10) == (2024, 1, 1, False)
    assert solar_to_lunar(2025, 1, 29) == (2025, 1, 1, False)
    assert solar_to_lunar(2000, 2, 5) == (2000, 1, 1, False)
    assert solar_to_lunar(1990, 1, 27) == (1990, 1, 1, False)


def test_true_solar_busan():
    dt, corr, lon, ok = true_solar_time(1995, 2, 28, 12, 0, "부산")
    assert ok and abs(lon - 129.08) < 0.01
    assert (dt.hour, dt.minute) == (11, 43)  # 12:00 - 16.5분
    assert -20 < corr < -10


def test_lichun_2026():
    lichun = solar_term_moment(2026, 315.0)
    assert (lichun.month, lichun.day) == (2, 4)


def test_four_pillars_exact():
    fp = four_pillars(BIRTH, 12, 0, "부산")
    assert fp["strings"]["year"].startswith("을해")
    assert fp["strings"]["month"].startswith("무인")
    assert fp["strings"]["day"].startswith("경인")
    assert fp["strings"]["hour"].startswith("임오")
    assert fp["ilgan"] == "경"


def test_ziwei_hand_verified():
    z = ziwei_chart(BIRTH, 12, 0, "male", "부산")
    assert z["lunar"] == (1995, 1, 29, False)
    assert z["mingong"] == "신" and z["shengong"] == "신"
    assert z["guo"] == 2
    assert z["ming_main"] == "염정"
    assert z["spouse_main"] == "칠살"
    assert z["sihua"] == {"록": "천기", "권": "천량", "과": "자미", "기": "태음"}
    assert z["mingzhu"] == "거문" and z["shenzhu"] == "천기"
    # 사화 낙궁 확인
    by_star = {}
    for p in z["palaces"]:
        for s, h in p["hua"].items():
            by_star[s] = (p["name"], h)
    assert by_star["천기"] == ("질액", "록")
    assert by_star["천량"] == ("자녀", "권")
    assert by_star["자미"] == ("재백", "과")
    assert by_star["태음"] == ("노복", "기")
    # 대운: 수이국 7세 시작, 을해년 음년 남명 → 역행, 명궁 7~16세
    ming = next(p for p in z["palaces"] if p["name"] == "명궁")
    assert ming["daxian"] == (7, 16)


def test_astro_real_signs():
    nc = natal_chart(BIRTH, 12, 0, "부산")
    assert nc["positions"]["sun"]["sign"] == "물고기자리"
    # 음력 29일(삭 직전), 달은 태양보다 약 25° 뒤진 물병자리
    assert nc["positions"]["moon"]["sign"] == "물병자리"
    assert nc["positions"]["venus"]["sign"] == "염소자리"  # 297.2° (pymeeus 대조 확인)
    assert nc["asc"]["sign"] == "쌍둥이자리"  # ASC 79.9°
    assert abs(nc["asc"]["lon"] - 79.9) < 1.0


def test_dayun_direction():
    du = dayun(BIRTH, 12, 0, "male", "부산")
    assert du["direction"] == "역행"  # 을해년 음년 + 남명
    # 역행 → 직전 절기(입춘 2/4)까지 약 24일 → 24/3 ≈ 8세 대운 시작
    assert 7.0 < du["start_age"] < 9.0


def test_shensha_keys():
    sh = shensha(BIRTH, 12, 0, "부산")
    for k in ("천을귀인", "역마", "화개", "공망", "장성", "괴강", "고진과숙"):
        assert k in sh


def test_detailed_reading_deterministic():
    a = detailed_reading(BIRTH, 12, 0, "male", "부산", TARGET)
    b = detailed_reading(BIRTH, 12, 0, "male", "부산", TARGET)
    assert a == b
    assert a["ziwei_main"] == "칠살"
    assert a["venus"] == "염소자리"


def test_report_orthodox_labels():
    text, md = build_report(BIRTH, 12, 0, "male", "부산", TARGET)
    for token in ("정통", "진태양시", "음력", "오행국", "생년사화",
                  "대운", "유년", "상승궁", "하우스", "어스펙트", "천을귀인"):
        assert token in text, token
    assert "간략판" not in text and "간략판" not in md
    assert "(재미·참고용)" not in text and "(재미·참고용)" not in md


def test_match_no_pii_in_markdown():
    _, md = build_report(BIRTH, 12, 0, "male", "부산", TARGET)
    for pii in ("1995-02-28", "1995", "부산", "male"):
        assert pii not in md
