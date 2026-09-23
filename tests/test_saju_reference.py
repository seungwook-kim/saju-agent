"""사주 4기둥을 lunar-python(6tail) 결과와 대조한다.

tests/data/saju_pillars.json 은 lunar-python 으로 뽑은 240명이다. 절반은 월주가
틀리기 쉬운 12월~2월 출생으로 골랐다. 개발 중에는 4,000명을 대조해 전부 일치했다.
"""
import json
from datetime import date
from pathlib import Path

import pytest

from love_fortune.manseryuk import four_pillars

DATA = json.loads((Path(__file__).parent / "data" / "saju_pillars.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("c", DATA["cases"], ids=lambda c: c["birth"] + " " + c["time"])
def test_pillars_match_lunar_python(c):
    h, m = map(int, c["time"].split(":"))
    fp = four_pillars(date.fromisoformat(c["birth"]), h, m, c["city"])
    assert fp["strings"] == c["pillars"]
