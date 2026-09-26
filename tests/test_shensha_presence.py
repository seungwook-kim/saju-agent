"""신살 줄은 글자가 원국에 있을 때만 '있다'고 말해야 한다 (화개·장성·공망·고진과숙 표시 오류 회귀)."""
import random
import re
from datetime import date

from love_fortune.manseryuk import BRANCHES_KR, four_pillars, shensha

POS = {"년지": "year", "월지": "month", "일지": "day", "시지": "hour"}


def test_presence_matches_chart():
    rnd = random.Random(11)
    for _ in range(300):
        b = date(rnd.randint(1940, 2015), rnd.randint(1, 12), rnd.randint(1, 28))
        h = rnd.choice([None, rnd.randint(0, 23)])
        P = four_pillars(b, h, 0, "서울")["pillars"]
        chart = {BRANCHES_KR[br] for _s, br in P.values() if br is not None}
        for name, line in shensha(b, h, 0, "서울").items():
            if name == "괴강":
                continue
            head, _, rest = line.partition(", ")
            letters = set(re.findall(r"[가-힣](?=·|$)|(?<=·)[가-힣]", head)) or set(head.split()[-1:])
            if name == "고진과숙":
                letters = {head.split()[1][0], head.split()[-1]}
            present = bool(letters & chart)
            assert ("원국에 없어" in rest) != present, (b, h, name, line, chart)
            for pos in re.findall(r"(년지|월지|일지|시지)", rest):
                assert BRANCHES_KR[P[POS[pos]][1]] in letters, (b, h, name, line)
