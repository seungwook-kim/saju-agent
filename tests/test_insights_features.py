"""새 기능 검사: 세 체계 합의도, 골든타임, 절기 달 날짜, 속궁합(19), 태어난 시간 찾기, 근거 보기."""
import re
from datetime import date

import pytest

from love_fortune import facts, insights, rectify, sok
from love_fortune.astro import SIGNS, natal_chart

HAN = re.compile(r"[一-鿿]")
B, T = date(1990, 5, 5), date(2026, 9, 27)


@pytest.fixture(scope="module")
def sheet():
    return facts.build(B, 14, 30, "female", "서울", T)


def test_jie_bounds_follow_solar_terms():
    assert insights.jie_bounds(2026, 12) == (date(2026, 12, 7), date(2027, 1, 4))
    assert insights.jie_bounds(2027, 3) == (date(2027, 3, 6), date(2027, 4, 4))
    s, e = insights.jie_bounds(2027, 2)
    assert s.month == 2 and s.day in (3, 4, 5) and e.month == 3


def test_months_carry_calendar_dates(sheet):
    for dom in ("love", "career", "money"):
        for r in sheet[dom]["months"]:
            assert r["from"] < r["to"] and r["from"][:7] == r["ym"]


def test_consensus_shape(sheet):
    rows = sheet["insights"]["consensus"]
    assert len(rows) == 10 and rows[0]["year"] == T.year
    for r in rows:
        for dom in ("love", "career", "money"):
            c = r["domains"][dom]
            assert c["n"] == 3 and all(c[k] in (-1, 0, 1) for k in ("saju", "ziwei", "astro"))
            assert c["up"] == sum(c[k] > 0 for k in ("saju", "ziwei", "astro"))
            assert not HAN.search(" ".join(v for v in c["why"].values() if v))


def test_consensus_without_birth_time_uses_saju_only():
    f = facts.build(B, None, 0, "female", "서울", T)
    c = f["insights"]["consensus"][0]["domains"]["love"]
    assert c["n"] == 1 and c["ziwei"] is None and c["astro"] is None
    assert f["sok"]["moon_mars"] is None           # 달은 시간을 알아야 각도를 본다


def test_golden_month_is_the_strongest(sheet):
    g = sheet["insights"]["golden"]
    m = g["month"]
    assert m and m["from"] >= "2026-09" and m["power"] >= 1 and m["parts"]
    assert g["year"]["year"] in [r["year"] for r in sheet["insights"]["consensus"]]


def test_sok_tables_cover_every_sign_without_hanja():
    for table in (sok.MARS, sok.VENUS):
        assert set(table) == set(SIGNS)
        for t in table.values():
            assert not HAN.search(t) and "—" not in t and t.endswith(".")


def test_sok_aspects_and_compatible_signs():
    assert sok.aspect_of(10, 12) == "합" and sok.aspect_of(10, 130) == "삼합"
    assert sok.aspect_of(10, 100) == "사각" and sok.aspect_of(10, 190) == "충" and sok.aspect_of(10, 45) == "없음"
    good, hard = sok.good_signs("염소자리")
    assert {"염소자리", "황소자리", "처녀자리", "전갈자리", "물고기자리"} == set(good)
    assert {"양자리", "천칭자리", "게자리"} == set(hard)
    assert sok.day_branch_match(2) == {"good": ["오", "술", "해"], "hard": ["사", "신", "유"]}


def test_sok_pair():
    a, b = natal_chart(B, 14, 30, "서울"), natal_chart(date(1992, 3, 3), 9, 0, "부산")
    p = sok.pair(a, b, 6, 2)
    assert len(p["rows"]) == 2 and p["day"]["tone"] == "good" and 0 <= p["good"] <= 3


def test_rectify_candidates_and_ranking():
    cands = rectify.candidates(B, "서울")
    assert [c["branch"] for c in cands] == list("자축인묘진사오미신유술해")
    assert cands[0]["clock"] == "23:29~01:28"          # 서울 진태양시 보정 약 29분
    evs = [{"year": 2012, "kind": "love"}, {"year": 2015, "kind": "move"}, {"year": 2018, "kind": "job"}]
    r = rectify.rectify(B, "female", "서울", evs)
    scores = [c["score"] for c in r["candidates"]]
    assert len(scores) == 12 and scores == sorted(scores, reverse=True)
    assert r["events"] == 3 and len(r["candidates"][0]["hits"]) == 3
    with pytest.raises(ValueError):
        rectify.rectify(B, "female", "서울", [{"year": 1980, "kind": "love"}])
    with pytest.raises(ValueError):
        rectify.rectify(B, "female", "서울", [{"year": 2012, "kind": "lottery"}])


def test_outline_has_pick_for_evidence():
    from love_fortune import chapters
    o = chapters.outline()
    assert all("pick" in c and c["pick"] for t in o.values() for c in t["chapters"])
    flow = next(c for c in o["life"]["chapters"] if c["id"] == "love_flow")
    assert "consensus:love" in flow["widgets"]


def test_static_has_new_features():
    from love_fortune.web import STATIC_DIR
    js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    html = (STATIC_DIR / "app.html").read_text(encoding="utf-8")
    for needle in ("class=\"evid\"", "data-ics", "/api/v2/rectify", "saju.adult", "function consensus", "pastBySystem"):
        assert needle in js, needle
    assert 'id="shGold"' in html
