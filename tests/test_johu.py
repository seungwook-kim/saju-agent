"""조후용신 표와 풀이 문장 검사."""
import re
from datetime import date

from love_fortune import johu

HAN = re.compile(r"[\u4e00-\u9fff]")


def test_table_shape():
    assert set(johu.TABLE) == set(johu.STEMS)
    for stem, row in johu.TABLE.items():
        assert len(row) == 12, stem
        for cell in row:
            assert cell and all(c in johu.STEMS for c in cell), (stem, cell)
            assert len(set(cell)) == len(cell), (stem, cell)


def test_cells_follow_original_text():
    # 궁통보감 원문의 '먼저 … 다음 …' 문장으로 정한 칸 (정리표끼리 순서가 갈리던 곳 포함)
    cases = {("신", "축"): "병임",   # 12월 신금: 병 먼저, 임 다음
             ("신", "해"): "임병",   # 10월 신금: 임수 먼저, 병화 다음
             ("임", "오"): "계경",   # 5월 임수: 계수가 용, 경금이 보좌
             ("기", "신"): "계병",   # 가을 기토: 계 먼저, 병 다음
             ("기", "유"): "계병",
             ("갑", "진"): "경임",   # 3월 갑목: 경금 먼저, 임수 다음
             ("갑", "사"): "계정",   # 4월 갑목: 계 먼저, 정 다음
             ("병", "사"): "임경",   # 4월 병화: 오로지 임수, 경금이 물의 근원
             ("경", "자"): "정갑",   # 11월 경금: 정·갑을 쓴다
             ("정", "미"): "갑임",   # 6월 정화: 오로지 갑목, 임수 다음
             # 다섯 정리표가 모두 같은 칸
             ("갑", "인"): "병계", ("을", "자"): "병", ("병", "오"): "임경", ("계", "신"): "정"}
    for (stem, month), main in cases.items():
        assert "".join(johu.lookup(stem, month)[:2]) == main, (stem, month)


def test_text_particles_and_no_hanja():
    bad = re.compile(r"(목|금)\([^)]*\)(야|를|가)[ .]|(화|토|수)\([^)]*\)(이야|을|이)[ .]")
    for ds in range(10):
        for mb in range(12):
            for strong in (True, False):
                r = johu.analyze(ds, mb, [ds], strong)
                t = " ".join(r["text"])
                assert not HAN.search(t), t
                assert not bad.search(t), (ds, mb, bad.search(t).group(0))
                assert "None" not in t and "  " not in t


def test_agreement_with_eokbu():
    # 한여름 갑목: 계수는 나를 받쳐 주는 기운(인성). 신약이면 억부와 같은 쪽, 신강이면 다른 쪽
    assert johu.analyze(0, 6, [0], strong=False)["agree"] is True
    r = johu.analyze(0, 6, [0], strong=True)
    assert r["agree"] is False and "계절 맞추기를 먼저" in " ".join(r["text"])


def test_facts_and_chapter_carry_johu():
    from love_fortune import facts, rule_chapters
    f = facts.build(date(1990, 5, 5), 14, 30, "female", "서울", date(2026, 9, 26))
    jh = f["natal"]["johu"]
    assert jh["main"] and all(x[-1] in "목화토금수" for x in jh["main"])
    ch = rule_chapters.life(f, "wonguk")
    titles = [b.get("title") for b in ch["blocks"]]
    assert "계절로 본 용신(조후)" in titles
