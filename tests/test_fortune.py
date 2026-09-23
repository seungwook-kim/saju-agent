"""tests, 결정적 동작·오프라인·개인정보 미저장 검증."""
from datetime import date

from love_fortune.cli import build_report
from love_fortune.manseryuk import four_pillars
from love_fortune.rules import branch_relation, love_score


def test_example_case_runs():
    birth = date(1995, 2, 28)
    target = date(2026, 9, 20)
    text, md = build_report(birth, 12, 0, "male", "부산", target)
    assert "오늘 연애운" in text
    assert "오늘 총운" in text and "오늘 직장운" in text and "오늘 금전운" in text
    assert "일간(나)" in text
    assert "타로" in text and "주역" in text and "오미쿠지" in text
    assert "자미두수" in text and "점성술" in text


def test_domain_filter():
    birth = date(1995, 2, 28)
    target = date(2026, 9, 20)
    text, md = build_report(birth, 12, 0, "male", "부산", target, "career")
    assert "오늘 직장운" in text
    assert "오늘 연애운" not in text and "오늘 금전운" not in text
    assert "오늘 직장운" in md and "오늘 연애운" not in md


def test_deterministic_same_date_same_result():
    birth = date(1995, 2, 28)
    target = date(2026, 9, 20)
    t1, _ = build_report(birth, 12, 0, "male", "부산", target)
    t2, _ = build_report(birth, 12, 0, "male", "부산", target)
    assert t1 == t2


def test_score_range():
    s, reasons, elem = love_score(3, [1, 2, 5, 6], 4, 7, "x")
    assert 1 <= s <= 100
    assert reasons and elem in ("목", "화", "토", "금", "수")


def test_no_pii_in_markdown():
    birth = date(1995, 2, 28)
    target = date(2026, 9, 20)
    _, md = build_report(birth, 12, 0, "male", "부산", target)
    for pii in ("1995-02-28", "1995", "부산", "male"):
        assert pii not in md, f"PII 유출: {pii}"


def test_no_network_imports():
    import love_fortune.cli as cli
    import love_fortune.advise as advise
    import love_fortune.manseryuk as mans
    import love_fortune.rules as rules
    import love_fortune.ziwei as ziwei
    import love_fortune.astro as astro
    import love_fortune.domains as domains
    import love_fortune.synthesis as synth
    import love_fortune.lunar as lunar
    import love_fortune.astronomy as astronomy
    import sys
    mods = [cli, advise, mans, rules, ziwei, astro, domains, synth,
            lunar, astronomy]
    for m in mods:
        src = open(m.__file__, encoding="utf-8").read()
        for banned in ("requests", "urllib.request", "urlopen", "socket",
                       "openai", "anthropic", "http.client"):
            assert banned not in src, f"{m.__name__}에 네트워크 흔적: {banned}"


def test_relations_known_pair():
    # 자(0)-오(6)는 육충 [정설]
    assert any("육충" in r for r in branch_relation(0, 6))
    # 자(0)-축(1)은 육합 [정설]
    assert any("육합" in r for r in branch_relation(0, 1))


def test_four_pillars_ilgan():
    fp = four_pillars(date(1995, 2, 28), 12, 0)
    assert fp["ilgan"] in ("갑", "을", "병", "정", "무", "기", "경", "신", "임", "계")
