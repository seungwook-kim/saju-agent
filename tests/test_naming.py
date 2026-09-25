"""이름 풀이 (naming.py, name_hanja.json) 검사. 한자는 코드포인트로만 쓴다."""
import pytest

from love_fortune import naming as N

# 인터넷 한국작명연구원 '혼동하기 쉬운 변획수 산정법' 33자 + 한국작명교육협회 예시(河 9, 四 4, 九 9)
PUBLISHED_STROKES = {
    0x4E16: 5, 0x81E3: 6, 0x5370: 6, 0x6210: 7, 0x5EF7: 7, 0x4E9E: 8, 0x6B66: 8, 0x6CF0: 9, 0x81F4: 9, 0x98DB: 9,
    0x80B2: 10, 0x54F2: 10, 0x5049: 11, 0x80E4: 11, 0x80FD: 12, 0x537F: 12, 0x6DF5: 12, 0x8DEF: 13, 0x88D5: 13,
    0x58FD: 14, 0x5BE6: 14, 0x8208: 15, 0x5BEC: 15, 0x9F8D: 16, 0x9053: 16, 0x9F9C: 16, 0x71D5: 16, 0x71E6: 17,
    0x9D3B: 17, 0x8C4A: 18, 0x7F85: 20, 0x74CA: 20, 0x82B1: 10, 0x6CB3: 9, 0x56DB: 4, 0x4E5D: 9,
}


def test_original_strokes_match_published_lists():
    table = {x["cp"]: x["w"] for x in N.hanja_table()}
    present = {cp: w for cp, w in PUBLISHED_STROKES.items() if cp in table}
    assert len(present) >= 34
    assert {cp: table[cp] for cp in present} == present


def test_four_ge_matches_published_examples():
    # 한국작명연구원 예시: 1자 성 2자 이름 (원25 형23 이16 정32), 외자 (원5 형13 이8 정13),
    # 2자 성 2자 이름 (원16 형31 이23 정35), 2자 성 외자 (원16 형35 이19 정35)
    assert N.four_ge([7], [16, 9]) == {"won": 25, "hyeong": 23, "i": 16, "jeong": 32}
    assert N.four_ge([8], [5]) == {"won": 5, "hyeong": 13, "i": 8, "jeong": 13}
    assert N.four_ge([10, 9], [12, 4]) == {"won": 16, "hyeong": 31, "i": 23, "jeong": 35}
    assert N.four_ge([10, 9], [16]) == {"won": 16, "hyeong": 35, "i": 19, "jeong": 35}
    assert N.four_ge([30], [40, 30])["jeong"] == 20          # 81 을 넘으면 80 을 뺀다


def test_sound_elements_match_published_examples():
    # 한국작명연구원 예: 이승환 = 토 금 토 (상생), 김영곤 = 목 토 목 (목극토 두 번)
    a = N.analyze("이", "승환")
    assert a["sound"]["major"]["elements"] == ["토", "금", "토"] and a["sound"]["major"]["verdict"] == "좋음"
    b = N.analyze("김", "영곤")
    assert b["sound"]["major"]["relations"] == ["ke", "ke"] and b["sound"]["major"]["verdict"] == "아쉬움"
    # 소수설(해례본)은 ㅇㅎ 수, ㅁㅂㅍ 토
    assert N.analyze("이", "민")["sound"]["minor"]["elements"] == ["수", "토"]


def test_suri_table_is_complete_and_reasoned():
    assert set(N.SURI) == set(range(1, 82))
    assert sum(v[0] == "good" for v in N.SURI.values()) == 40
    assert sum(v[0] == "bad" for v in N.SURI.values()) == 37
    assert N.SURI[78][0] == "split"


def test_full_analysis_with_hanja_and_saju():
    # 김(金 8) 지(智 12) 현(賢 15)
    d = N.analyze("김", "지현", [0x91D1, 0x667A, 0x8CE2], {"목": 0, "화": 2, "토": 2, "금": 3, "수": 1})
    assert d["suri"]["strokes"] == [8, 12, 15]
    assert d["suri"]["ge"]["jeong"]["num"] == 35
    assert d["saju"]["missing"] == ["목"]
    with pytest.raises(ValueError):
        N.analyze("김", "")


def test_surname_picker_puts_common_hanja_first():
    assert N.hanja_for("김", surname=True)[0]["cp"] == 0x91D1
    assert N.hanja_for("이", surname=True)[0]["cp"] == 0x674E
    assert all("hun" in x and x["strokes"] > 0 for x in N.hanja_for("민")[:10])
