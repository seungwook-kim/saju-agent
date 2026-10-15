"""2026-10 새 디자인 적용, 서버 쪽 시험.

- 사실표 새 칸 today.term(절기)·today.todo(오늘 할 일·피할 일)
- 새 칸은 챕터 AI 의 pick 밖이라 저장된 AI 풀이 키(cache_key)가 그대로다
- 길일 점수 하나로 (각 날의 score = 순위·이야기·화면이 같이 쓰는 값)
- 받침에 맞는 조사, 장 안에서 용어 풀이 괄호는 한 번만, 십이운성 '쇠' 구분, '탈과 해' 풀이
"""
import copy
import re
from datetime import date, timedelta

import pytest

from love_fortune import chapters, facts as facts_mod, store
from love_fortune.astronomy import TERM_NAME, season_term
from love_fortune.taekil import pick_dates

BIRTH = (date(1990, 5, 5), 14, 30, "female", "서울")
TODAY = date(2026, 10, 15)


@pytest.fixture(scope="module")
def sheet():
    return facts_mod.build(*BIRTH, TODAY)


# ---------------------------------------------------------------- 절기

# 2026년 24절기 날짜 (tests/test_official_reference.py 의 천문연구원 기준 자료와 같은 값)
TERMS_2026 = [(285, "01-05"), (300, "01-20"), (315, "02-04"), (330, "02-19"), (345, "03-05"), (0, "03-20"),
              (15, "04-05"), (30, "04-20"), (45, "05-05"), (60, "05-21"), (75, "06-06"), (90, "06-21"),
              (105, "07-07"), (120, "07-23"), (135, "08-07"), (150, "08-23"), (165, "09-07"), (180, "09-23"),
              (195, "10-08"), (210, "10-23"), (225, "11-07"), (240, "11-22"), (255, "12-07"), (270, "12-22")]


@pytest.mark.parametrize("lon,md", TERMS_2026)
def test_season_term_matches_kasi_2026(lon, md):
    d = date.fromisoformat(f"2026-{md}")
    t = season_term(d)
    assert t["name"] == TERM_NAME[lon] and t["date"] == d.isoformat()     # 드는 날부터 새 절기
    before = season_term(d - timedelta(days=1))
    assert before["next"] == TERM_NAME[lon] and before["next_date"] == d.isoformat()
    assert before["name"] == TERM_NAME[(lon - 15) % 360]


@pytest.mark.parametrize("d,name", [
    # 한국천문연구원 발표: 2021 입춘 2월 3일 23:59, 2025 입춘 2월 3일 23:10, 2024 동지 12월 21일 18:21
    (date(2021, 2, 3), "입춘"), (date(2025, 2, 3), "입춘"), (date(2024, 12, 21), "동지"),
])
def test_season_term_known_kasi_days(d, name):
    assert season_term(d)["name"] == name and season_term(d)["date"] == d.isoformat()
    assert season_term(d - timedelta(days=1))["next"] == name


def test_season_term_out_of_table_is_none():
    assert season_term(date(1850, 1, 1)) is None and season_term(date(2100, 1, 1)) is None


def test_fact_term(sheet):
    assert sheet["today"]["term"] == {"name": "한로", "date": "2026-10-08", "next": "상강", "next_date": "2026-10-23"}


# ---------------------------------------------------------------- 오늘 할 일·피할 일


def test_fact_todo_from_facts_only(sheet):
    t = sheet["today"]
    todo = t["todo"]
    doms = t["domains"]
    assert set(todo) >= {"do", "do_domain", "avoid"}
    # do: 팁이 있는 영역 중 점수가 가장 높은 영역의 첫 팁 (지어내지 않는다)
    tipped = [k for k in ("love", "career", "money", "study") if doms[k]["tips"]]
    best = max(tipped, key=lambda k: doms[k]["score"])
    assert todo["do_domain"] == best and todo["do"] == doms[best]["tips"][0]
    # avoid: 피할 것이 있는 영역 중 점수가 가장 낮은 영역의 것
    avoided = [k for k in ("love", "career", "money", "study") if doms[k]["avoid"]]
    worst = min(avoided, key=lambda k: doms[k]["score"])
    assert todo["avoid"] == doms[worst]["avoid"]
    assert todo == {"do": "충동구매는 24시간 미뤄보기", "do_domain": "money",          # 팁은 날짜 해시로 고른다
                    "avoid": "충동적인 사직·이직 언급", "avoid_domain": "career"}


def test_todo_falls_back_to_almanac_then_empty():
    empty = {k: {"score": 50, "tips": [], "avoid": ""} for k in ("love", "career", "money")}
    t = facts_mod.today_todo(empty, {"saenggi": "화해"})
    assert t["do"] == "" and t["do_domain"] == ""
    assert t["avoid"].startswith("탈과 해(") and t["avoid"].endswith("날이야") and t["avoid_domain"] == "almanac"
    assert facts_mod.today_todo(empty, {"clash_me": ["인"]})["avoid"].startswith("오늘 일진이 내 사주의 인과 ")
    assert facts_mod.today_todo(empty, {"saenggi": "생기"}) == {"do": "", "do_domain": "", "avoid": "", "avoid_domain": ""}


# ---------------------------------------------------------------- 저장된 AI 풀이 키는 그대로


def test_new_fields_not_in_any_pick():
    for tab in chapters.TABS.values():
        for ch in tab["chapters"]:
            for p in ch["pick"]:
                assert p != "today" and not p.startswith(("today.term", "today.todo")), (ch["id"], p)


def test_cache_keys_unchanged_by_new_fields(sheet):
    old = copy.deepcopy(sheet)
    del old["today"]["term"], old["today"]["todo"]
    n = 0
    for tab, t in chapters.TABS.items():
        for ch in t["chapters"]:
            assert chapters.key_of(tab, ch["id"], sheet) == chapters.key_of(tab, ch["id"], old), (tab, ch["id"])
            n += 1
    assert n > 30


# ---------------------------------------------------------------- 길일 점수 하나로


@pytest.mark.parametrize("domain", ["total", "love", "career", "money"])
def test_pick_score_is_rank_score(domain):
    r = pick_dates(*BIRTH, date(2026, 10, 15), date(2026, 11, 13), domain)
    rows = r["rows"]
    assert all(x["score"] == x[domain] for x in rows)
    assert [x["score"] for x in rows] == sorted((x["score"] for x in rows), reverse=True)
    assert f"{rows[0]['score']}점이야" in r["story"][0]
    assert f"평균은 {sum(x['score'] for x in rows) // len(rows)}점" in r["story"][0]
    assert f"차이는 {rows[0]['score'] - rows[-1]['score']}점" in r["story"][2]


def test_pick_report_shows_same_score():
    from love_fortune.cli import build_pick_report
    s, e = date(2026, 10, 15), date(2026, 10, 21)
    r = pick_dates(*BIRTH, s, e, "total")
    text, md = build_pick_report(*BIRTH, s, e, "total", 3, r)
    top = r["rows"][0]
    assert f"1위: {top['label']} {top['ganzhi']} 총운 {top['score']}점" in md
    assert f"{top['score']}점" in r["story"][0]


# ---------------------------------------------------------------- 조사


def test_match_day_branch_josa():
    from love_fortune.matchmaking import compatibility
    r = compatibility(*BIRTH, date(1992, 3, 3), 9, 0, "male", "서울")   # 일지 오·인
    lines = r["strengths"] + r["cautions"]
    assert any("두 일지 오·인은 " in x for x in lines)
    assert not any("오·인는" in x for x in r["strengths"] + r["cautions"] + r["story"])


_STARS = ("자미", "천기", "태양", "무곡", "천동", "염정", "천부", "태음", "탐랑", "거문", "천상", "천량", "칠살", "파군",
          "홍란", "천희", "함지", "천요", "문창", "문곡")
_GODS = ("비견", "겁재", "식신", "상관", "편재", "정재", "편관", "정관", "편인", "정인")
_PLANETS = ("태양", "금성", "수성", "화성", "목성", "토성")


def _has_batchim(w):
    return (ord(w[-1]) - 0xAC00) % 28 != 0


def _bad_josa(text):
    """이름 뒤 조사가 받침과 어긋난 곳을 찾는다 (예: '자미이', '겁재으로', '금성와', '오·인는')."""
    bad = []
    for w in set(_STARS + _GODS + _PLANETS):
        if not _has_batchim(w):
            wrong = ("은", "이", "을", "과", "이야", "으로")
        elif (ord(w[-1]) - 0xAC00) % 28 == 8:          # ㄹ 받침은 '로'가 맞다 (칠살로)
            wrong = ("는", "가", "를", "와", "야", "으로")
        else:
            wrong = ("는", "가", "를", "와", "야", "로")
        for jo in wrong:
            bad += [m.group(0) for m in re.finditer(re.escape(w) + "'?" + jo + r"(?=[\s,.]|$)", text)]
    bad += re.findall(r"[가-힣]·[가-힣]{1}(?:는|은|가|이) ", text)
    return [b for b in bad if not _ok_pair(b)]


def _ok_pair(s):
    m = re.match(r"[가-힣]·([가-힣])(는|은|가|이) $", s)
    if not m:
        return False
    w, jo = m.groups()
    return (jo in ("은", "이")) == _has_batchim(w)


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v)


@pytest.mark.parametrize("birth", [
    (date(1990, 5, 5), 14, 30, "female", "서울"), (date(1985, 11, 20), 6, 0, "male", "부산"),
    (date(1999, 1, 9), 22, 10, "female", "광주"), (date(1977, 7, 30), 3, 45, "male", "서울"),
])
def test_no_josa_mismatch_in_sheet_and_chapters(birth):
    f = facts_mod.build(*birth, TODAY)
    blob = "\n".join(_strings(f)) + "\n" + "\n".join(_strings(chapters.rule_all(f)))
    assert _bad_josa(blob) == []


def test_stage_quote_josa_for_open_syllable():
    from love_fortune.josa import j
    assert j("'쇠'", "이야") == "'쇠'야" and j("'절'", "이야") == "'절'이야"


# ---------------------------------------------------------------- 용어 풀이 괄호


def test_gloss_once_per_chapter():
    body = {"headline": "부처궁(배우자를 보는 자리) 이야기", "lead": "부처궁(배우자를 보는 자리)에는 칠살이 있어.",
            "blocks": [{"type": "text", "title": "", "body": "도화(사람을 끄는 매력의 별)가 들어. 도화(매력의 별)가 또 나와."},
                       {"type": "cards", "title": "", "items": [{"title": "부처궁(배우자를 보는 자리)", "body":
                                                                  "삼합(순하게 흘러가는 각도, 오차 1.93도), 삼합(순하게 흘러가는 각도, 오차 1.93도)"}]},
                       {"type": "checklist", "title": "", "items": ["오늘 단계는 '쇠'야.", "'쇠' 단계는 차분해."]}],
            "closing": ""}
    out = chapters.gloss_once(body)
    assert out["headline"] == "부처궁(배우자를 보는 자리) 이야기"
    assert out["lead"] == "부처궁에는 칠살이 있어."
    assert out["blocks"][0]["body"] == "도화(사람을 끄는 매력의 별)가 들어. 도화가 또 나와."
    assert out["blocks"][1]["items"][0]["title"] == "부처궁"
    assert out["blocks"][1]["items"][0]["body"].count("오차 1.93도") == 2      # 숫자가 든 괄호는 값이라 그대로
    assert out["blocks"][2]["items"] == ["오늘 단계는 '쇠'(기운이 한풀 꺾이는 단계)야.", "'쇠' 단계는 차분해."]
    assert body["lead"].startswith("부처궁(")                                # 원본은 건드리지 않는다


def test_rule_chapters_gloss_short_and_once(sheet):
    for tab, chs in chapters.rule_all(sheet).items():
        for cid, body in chs.items():
            seen = {}
            for s in _strings({k: body[k] for k in ("headline", "lead", "blocks", "closing")}):
                for m in re.finditer(r"([가-힣]+)\(([^()]{3,})\)", s):
                    assert len(m.group(2)) <= 60, (tab, cid, m.group(0))
                    if not re.search(r"\d", m.group(2)):
                        key = (m.group(1), m.group(2))
                        assert key not in seen, (tab, cid, m.group(0))
                        seen[key] = 1


def test_soe_stage_is_told_apart(sheet):
    line = sheet["today"]["systems"][0]["lines"][0]       # 이 예시는 오늘 일간 경의 단계가 '쇠'
    assert "'쇠'(기운이 한풀 꺾이는 단계)야" in line


def test_tal_hae_is_explained(sheet):
    assert store.by_key("saenggi")["화해"]["meaning"].startswith("탈과 해(")
    assert any("탈과 해(뜻밖의 사고와 손해)" in x for x in sheet["today"]["almanac"])
