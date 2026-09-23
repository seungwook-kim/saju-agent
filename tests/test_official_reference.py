"""공식·천체력 기준 자료와 대조한다.

- tests/data/kasi_lunar.json: 한국천문연구원 음양력 변환 결과 63건 (음력 날짜, 윤달, 일진).
  개발 중에는 204건을 대조해 전부 일치했다.
- 2026년 24절기: NASA DE441 과 천문연구원 특일 정보로 계산한 공개 자료(분 단위).
"""
import json
from datetime import date, datetime
from pathlib import Path

import pytest

from love_fortune.astronomy import solar_term_moment
from love_fortune.lunar import solar_to_lunar
from love_fortune.manseryuk import day_pillar, ganzhi_str

KASI = json.loads((Path(__file__).parent / "data" / "kasi_lunar.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("c", KASI["cases"], ids=lambda c: c["solar"])
def test_lunar_and_iljin_match_kasi(c):
    d = date.fromisoformat(c["solar"])
    assert list(solar_to_lunar(d.year, d.month, d.day)) == c["lunar"]
    assert ganzhi_str(*day_pillar(d)) == c["iljin"]


TERMS_2026 = [(285, "01-05 17:23"), (300, "01-20 10:44"), (315, "02-04 05:02"), (330, "02-19 00:51"),
              (345, "03-05 22:58"), (0, "03-20 23:45"), (15, "04-05 03:39"), (30, "04-20 10:39"),
              (45, "05-05 20:48"), (60, "05-21 09:36"), (75, "06-06 00:48"), (90, "06-21 17:24"),
              (105, "07-07 10:56"), (120, "07-23 04:13"), (135, "08-07 20:42"), (150, "08-23 11:18"),
              (165, "09-07 23:41"), (180, "09-23 09:05"), (195, "10-08 15:29"), (210, "10-23 18:37"),
              (225, "11-07 18:52"), (240, "11-22 16:23"), (255, "12-07 11:52"), (270, "12-22 05:50")]


@pytest.mark.parametrize("lon,when", TERMS_2026)
def test_solar_terms_2026_within_a_minute(lon, when):
    ref = datetime.strptime(f"2026-{when}", "%Y-%m-%d %H:%M")
    got = solar_term_moment(2026, float(lon))
    assert abs((got - ref).total_seconds()) < 60
