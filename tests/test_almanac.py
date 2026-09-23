"""한국 택일 달력(almanac)을 기준 자료와 대조한다."""
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from love_fortune import almanac as A
from love_fortune.manseryuk import day_pillar

DATA = Path(__file__).parent / "data"
LP = json.loads((DATA / "almanac_lunar_python.json").read_text(encoding="utf-8"))
SG = json.loads((DATA / "saenggi_table.json").read_text(encoding="utf-8"))
BR = "자축인묘진사오미신유술해"


def test_officer_and_spirit_rules_match_lunar_python():
    # 월지×일지 144칸 전부 (규칙으로 만든 값과 lunar-python 표)
    for key, name in LP["officer"].items():
        mb, db = map(int, key.split(","))
        assert A.OFFICERS[(db - mb) % 12] == name, key
    for key, name in LP["spirit"].items():
        mb, db = map(int, key.split(","))
        assert A.SPIRITS[(db - A._QINGLONG_AT[mb]) % 12] == name, key


def test_mansion_cycle_matches_lunar_python():
    for iso, name in LP["mansion"]:
        assert A.mansion(date.fromisoformat(iso)) == name, iso


@pytest.mark.parametrize("sex", ["male", "female"])
def test_saenggi_matches_gunghap_table(sex):
    for row in SG["table"][sex]:
        for age in row["ages"]:
            got = A.saenggi_table(age, sex)
            for name, branches in row["cells"].items():
                assert {BR[b] for b in got[name]} == set(branches), (sex, age, name)


def test_day_info_2026_09_23():
    info = A.day_info(date(2026, 9, 23), birth=date(1995, 2, 28), sex="male")
    assert info["iljin"] == "경자" and info["officer"] == "평" and info["spirit"] == "사명"
    assert info["mansion"] == "기" and info["spirit_yellow"] and not info["officer_good"]
    assert info["lunar"] == (2026, 8, 13, False) and not info["son_eomneun"]
    assert info["age"] == 32 and info["saenggi"] in A.SAENGGI_NAMES
    assert info["directions"] == {"삼살": "북", "대장군": "동"}     # 병오년


def test_son_eomneun_and_wolgi():
    d = date(2026, 9, 1)
    days = [d + timedelta(days=i) for i in range(60)]
    for x in days:
        info = A.day_info(x)
        assert info["son_eomneun"] == (info["lunar"][2] % 10 in (9, 0))
        assert info["wolgi"] == (info["lunar"][2] in (5, 14, 23))


def test_month_branch_changes_on_jie_day():
    # 2026 백로는 9월 7일 23:41 (한국 표준시). 그날부터 유월로 본다
    assert A.month_branch_of_day(date(2026, 9, 6)) == 8
    assert A.month_branch_of_day(date(2026, 9, 7)) == 9
    assert day_pillar(date(2026, 9, 7))
