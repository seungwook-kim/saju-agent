"""tests for match.py, 인연 아키타입 엔진 검증."""
from datetime import date

from love_fortune.match import spouse_archetype, _stage, dohwa_info
from love_fortune.cli import build_report

BIRTH = date(1995, 2, 28)
TARGET = date(2026, 9, 20)

# 단정적 예언 금지 문구 스캔용
BANNED = ["할 것이다", "만날 것이다", "결혼할", "이혼할", "헤어질 것이다"]


def test_archetype_keys():
    ma = spouse_archetype(BIRTH, 12, "male", TARGET)
    for k in ("god", "side", "god_rel", "star_line", "stage", "stage_love",
              "dohwa_lines", "hong_line", "timing", "ziwei_main",
              "ziwei_detail", "venus", "venus_detail", "moon",
              "moon_need", "meet_top3"):
        assert k in ma, k
    assert len(ma["meet_top3"]) == 3


def test_archetype_deterministic():
    a = spouse_archetype(BIRTH, 12, "male", TARGET)
    b = spouse_archetype(BIRTH, 12, "male", TARGET)
    assert a == b


def test_no_fatalistic_phrasing():
    ma = spouse_archetype(BIRTH, 12, "male", TARGET)
    blobs = [ma["side"], ma["star_line"], ma["stage_love"], ma["hong_line"],
             ma["timing"], ma["ziwei_detail"]["mind"],
             ma["venus_detail"]["style"], ma["moon_need"]] + ma["meet_top3"]
    for b in blobs:
        for ban in BANNED:
            assert ban not in b, f"단정 문구 발견: {ban} in {b[:40]}"


def test_report_contains_match_section():
    text, md = build_report(BIRTH, 12, 0, "male", "부산", TARGET)
    assert "만날 인연 아키타입" in text
    assert "만날 인연 아키타입" in md
    assert "배우자궁" in text and "부처궁" in text and "금성" in text


def test_match_no_pii_in_markdown():
    _, md = build_report(BIRTH, 12, 0, "male", "부산", TARGET)
    for pii in ("1995-02-28", "1995", "부산", "male"):
        assert pii not in md


def test_stage_table_spot_checks():
    assert _stage(8, 0) == "제왕"   # 임자일주
    assert _stage(0, 0) == "목욕"   # 갑자일주
    assert _stage(6, 6) == "목욕"   # 경오일주


def test_dohwa_spot_check():
    # 년지 해(11) → 해묘미 그룹 도화글자는 자(0). 월지에 자가 있으면 성립.
    info = dohwa_info([11, 0, 2, 6])
    assert info["chars"] == {0: ["월지"]}
    # 1995-02-28 남자 실제 사주(년 해·월 인·일 인·시 오)엔 도화 글자가 없음 → 빈 결과 정상
    assert dohwa_info([11, 2, 2, 6])["chars"] == {}
