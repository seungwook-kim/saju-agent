"""자미두수 명반을 iztro 결과와 대조한다.

tests/data/iztro_charts.json 은 iztro(npm) 로 뽑은 명반 60개다. 한국·중국 음력이
같은 날만 골랐다 (iztro 는 중국 달력을 쓴다). 개발 중에는 2,886개를 대조해
전 항목이 일치하는 것을 확인했고, 여기엔 그 일부를 고정해 둔다.
"""
import json
from pathlib import Path

import pytest

from love_fortune.ziwei import chart_from_lunar

DATA = json.loads((Path(__file__).parent / "data" / "iztro_charts.json").read_text(encoding="utf-8"))
NAME = {"녹존": "록존", "영성": "령성", "대보": "태보", "부처(배우자)": "부처", "건록": "임관"}
GUO = {2: "수이국", 3: "목삼국", 4: "금사국", 5: "토오국", 6: "화육국"}
MAJOR = {"자미", "천기", "태양", "무곡", "천동", "염정", "천부",
         "태음", "탐랑", "거문", "천상", "천량", "칠살", "파군"}
MINOR = {"좌보", "우필", "문창", "문곡", "천괴", "천월", "록존", "경양",
         "타라", "천마", "화성", "령성", "지공", "지겁"}
ADJ = {"홍란", "천희", "천요", "함지", "천형", "화개", "고진", "과숙", "태보", "봉고",
       "천재", "천수", "삼태", "팔좌", "은광", "천귀", "천공", "천곡", "천허", "용지", "봉각"}


def n(x: str) -> str:
    return NAME.get(x, x)


@pytest.mark.parametrize("z", DATA["charts"], ids=lambda z: "-".join(map(str, z["lunar"])))
def test_chart_matches_iztro(z):
    ly, lm, ld, leap = z["lunar"]
    ch = chart_from_lunar(ly, lm, ld, leap, z["hb"], z["sex"])
    assert GUO[ch["guo"]] == z["five"]
    assert n(ch["mingzhu"]) == z["soul"]
    assert n(ch["shenzhu"]) == z["body"]
    for p in ch["palaces"]:
        q = z["palaces"][p["branch_kr"]]
        mine = {n(s) for s in p["stars"]}
        where = f"{p['branch_kr']}궁"
        assert n(p["name"]) == q["name"], where
        assert p["stem_kr"] == q["stem"], where
        assert mine & MAJOR == {s for s, _ in q["major"]}, where
        assert mine & MINOR == {s for s, _ in q["minor"]} & MINOR, where
        assert mine & ADJ == set(q["adj"]) & ADJ, where
        assert ("절공" in mine) == bool({"절로", "공망"} & set(q["adj"])), where
        assert {n(s): h for s, h in p["hua"].items()} == \
            {s: h for s, h in q["major"] + q["minor"] if h}, where
        assert list(p["daxian"]) == q["range"], where
        assert n(ch["changsheng_at"][p["branch_kr"]]) == q["cs"], where
        assert ch["boshi_at"][p["branch_kr"]] == q["bs"], where
