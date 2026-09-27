"""대운 x 원국 합·충·형·파·해 검사."""
import re
from datetime import date

from love_fortune import dayun_rel as D
from love_fortune.manseryuk import BRANCHES_KR, STEMS_KR, dayun, four_pillars

HAN = re.compile(r"[\u4e00-\u9fff]")
S = STEMS_KR.index
B = BRANCHES_KR.index


def test_stem_pairs():
    assert D.stem_kinds(S("갑"), S("기")) == ["천간합"]
    assert D.stem_kinds(S("정"), S("임")) == ["천간합"]
    assert D.stem_kinds(S("갑"), S("경")) == ["천간충"]
    assert D.stem_kinds(S("정"), S("계")) == ["천간충"]
    assert D.stem_kinds(S("무"), S("기")) == []       # 무기는 충이 아니다


def test_branch_pairs():
    assert D.branch_kinds(B("자"), B("축")) == ["합"]
    assert D.branch_kinds(B("자"), B("오")) == ["충"]
    assert set(D.branch_kinds(B("축"), B("미"))) == {"충", "형"}
    assert D.branch_kinds(B("진"), B("진")) == ["형"]       # 자형
    assert D.branch_kinds(B("자"), B("자")) == []
    assert D.branch_kinds(B("묘"), B("오")) == ["파"]
    assert D.branch_kinds(B("축"), B("오")) == ["해"]
    assert D.branch_kinds(B("자"), B("진")) == ["삼합"]
    assert "형" in D.branch_kinds(B("자"), B("묘"))


def test_build_rows_and_text():
    import random
    rnd = random.Random(7)
    for _ in range(150):
        b = date(rnd.randint(1940, 2015), rnd.randint(1, 12), rnd.randint(1, 28))
        hour = rnd.choice([None, rnd.randint(0, 23)])
        sex = rnd.choice(["male", "female"])
        P = four_pillars(b, hour, 0, "서울")["pillars"]
        rows = D.build(P, dayun(b, hour, 0, sex, "서울", date(2026, 9, 26)))
        assert len(rows) == 8 and sum(r["now"] for r in rows) <= 1
        for r in rows:
            assert ("hour" in r["cells"]) == (hour is not None)
            t = r["line"]
            assert t.startswith(r["ganzhi"] + "운은 ") and t.endswith((".",))
            assert not HAN.search(t) and "None" not in t and "  " not in t
            assert "할 것이다" not in t and "반드시" not in t


def test_chapter_and_widget():
    from love_fortune import chapters, facts, rule_chapters
    f = facts.build(date(1990, 5, 5), 14, 30, "female", "서울", date(2026, 9, 26))
    assert len(f["life"]["dayun_rel"]) == 8
    ch = rule_chapters.life(f, "dayun")
    assert any(b.get("title") == "대운이 원국과 만나는 자리" for b in ch["blocks"])
    spec = next(c for c in chapters.TABS["life"]["chapters"] if c["id"] == "dayun")
    assert "dayunrel" in spec["widgets"] and "life.dayun_rel" in spec["pick"]
