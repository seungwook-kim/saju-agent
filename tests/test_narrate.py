"""tests for narrate.py, 상세 서사 검증."""
import re
from datetime import date

from love_fortune.narrate import (AUX_TALK, PALACE_TALK, narrate_palace,
                                  narrate_planet, narrate_aspect)
from love_fortune.cli import build_report
from love_fortune.synthesis import detailed_reading

BIRTH = date(1995, 2, 28)
TARGET = date(2026, 9, 20)
HAN = re.compile(r"[\u4e00-\u9fff]")
KANA = re.compile(r"[\u3040-\u30ff]")


def test_aux_tables_clean():
    assert len(AUX_TALK) >= 30
    assert len(PALACE_TALK) == 12
    for d in (AUX_TALK, PALACE_TALK):
        for k, v in d.items():
            assert not HAN.search(k + v), k
            assert not KANA.search(k + v)
            assert "—" not in k + v


def test_narrate_functions():
    p = {"name": "명궁", "stem_kr": "갑", "branch_kr": "신",
         "stars": ["염정", "천월", "봉고"], "hua": {"천월": "과"},
         "daxian": (7, 16)}
    s = narrate_palace(p, ["염정"])
    assert "명궁 자리" in s and "염정" in s
    # 출생 차트라 "지금" 이 아니라 "태어날 때" 로 말한다
    assert narrate_planet("태양", "물고기자리", 10, False, False).startswith("태어날 때 태양은")
    assert "10번 하우스 칸" in narrate_planet("태양", "물고기자리", 10, False, False)
    assert "긴장" in narrate_aspect("태양–목성 형(85.8°)")


def test_palace_daxian_timeframe():
    p = {"name": "명궁", "stem_kr": "갑", "branch_kr": "신",
         "stars": ["염정"], "hua": {}, "daxian": (7, 16)}
    assert "아직 오지 않은" in narrate_palace(p, ["염정"], 5)
    assert "지금 지나가는 중" in narrate_palace(p, ["염정"], 10)
    assert "이미 지나간" in narrate_palace(p, ["염정"], 20)
    assert "오지 않은" not in narrate_palace(p, ["염정"])
    assert "할 것이다" not in narrate_palace(p, ["염정"], 10)


def test_puli_in_outputs():
    text, md = build_report(BIRTH, 12, 0, "male", "부산", TARGET,
                            "all", True)
    assert "- 풀이:" in md
    assert "풀이:" in text
    assert "나 자신과 인생 방향" in text  # palace narrative
    assert "하우스 칸" in text  # house narrative
    ma = detailed_reading(BIRTH, 12, 0, "male", "부산", TARGET)
    assert ma["ziwei"]["palaces"]
