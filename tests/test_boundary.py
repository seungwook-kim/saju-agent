"""균시차와 경계 출생 알림 검사."""
from datetime import date

from love_fortune import boundary as B
from love_fortune.astronomy import equation_of_time

# PyEphem 으로 구한 균시차(분, 그리니치 정오 기준). tools 없이 고정값으로 대조한다
EOT_REF = {"1990-01-01": -3.53, "1990-02-11": -14.25, "1990-04-15": -0.07, "1990-05-14": 3.71,
           "1990-06-13": 0.05, "1990-07-26": -6.51, "1990-09-01": -0.07, "1990-11-03": 16.41,
           "1990-12-25": 0.0, "2026-02-04": -13.87, "2026-09-26": 8.67, "1955-08-15": -4.53}


def test_equation_of_time_matches_pyephem():
    for d, ref in EOT_REF.items():
        assert abs(equation_of_time(date.fromisoformat(d)) - ref) < 1.0, d


def test_lichun_boundary_warns_month_and_year():
    # 2026 입춘 절입 = 2026-02-04 05:02 (한국 시각). 04:00 출생은 1시간 2분 전
    r = B.check(date(2026, 2, 4), 4, 0, "서울")
    kinds = {i["kind"]: i for i in r["items"]}
    assert kinds["month"]["current"] == "기축" and kinds["month"]["alt"] == "경인"
    assert kinds["year"]["current"] == "을사" and kinds["year"]["alt"] == "병오"


def test_unknown_hour_on_term_day():
    r = B.check(date(2026, 2, 4), None, 0, "서울")
    assert r["items"] and "기축 또는 경인" in r["items"][0]["text"]


def test_hour_boundary_and_quiet_cases():
    # 서울 1990-05-05 13:35 → 진태양시 약 13:06, 13시 경계와 6분 차이 → 시주가 바뀔 수 있음
    r = B.check(date(1990, 5, 5), 13, 35, "서울")
    assert any(i["kind"] == "hour" for i in r["items"])
    assert B.check(date(1990, 5, 5), 14, 30, "서울")["items"] == []
