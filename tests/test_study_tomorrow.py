"""학업 영역과 내일 묶음 (2026-10-15 사용자 결정).

- 오늘 묶음에 학업(study), 위 줄에 내일(tomorrow ...). 총운 = 연애·직장·금전·학업 네 영역 평균 + 그날 공통 기운
- 학업 무게는 근거가 있는 신호만 (db/init.sql source 의 study_*), 나머지는 0
- facts.tomorrow 는 facts.today 와 같은 모양 + date, 내일 탭에는 내일 이야기만
- 내일 장도 미리 만들기(prefetch)에 들어가고 오늘 장 뒤 순서
"""
import copy
import json
import threading
import urllib.request
from datetime import date, timedelta

import pytest

from love_fortune import chapters, facts as facts_mod, prefetch, store
from love_fortune.domains import STUDY_GOD_BONUS, study_score, total_score
from love_fortune.taekil import pick_dates
from love_fortune.today import _ziwei

BIRTH = (date(1990, 5, 5), 14, 30, "female", "서울")
TODAY = date(2026, 10, 15)
DOMS = ("love", "career", "money", "study")
TAB_IDS = ("today", "love", "career", "money", "study",
           "tomorrow", "tomorrow_love", "tomorrow_career", "tomorrow_money", "tomorrow_study")


@pytest.fixture(scope="module")
def sheet():
    return facts_mod.build(*BIRTH, TODAY)


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v)


# ---------------------------------------------------------------- 사실표 계약


def test_study_in_every_today_field(sheet):
    t = sheet["today"]
    for k in ("total", *DOMS, "domain_avg"):
        assert k in t["scores"], k
    assert set(DOMS) <= set(t["heads"]) and set(DOMS) == set(t["domains"])
    st = t["domains"]["study"]
    assert set(st) == set(t["domains"]["career"])            # 다른 영역과 같은 모양
    assert st["tips"] and st["avoid"] and 1 <= st["score"] <= 100
    assert t["scores"]["domain_avg"] == round(sum(t["scores"][d] for d in DOMS) / 4)
    assert "학업" in t["total_reasons"][0]                     # 총운 출발점이 네 영역 평균


def test_tomorrow_same_shape_and_date(sheet):
    t, tm = sheet["today"], sheet["tomorrow"]
    assert set(tm) == set(t) | {"date"} and tm["date"] == "2026-10-16"
    assert tm["term"] and tm["todo"] and tm["almanac"]
    for k in ("scores", "heads", "domains"):
        assert set(tm[k]) == set(t[k])
    # 내일 칸 = 다음 날을 기준으로 본 오늘 칸 (점수·한 줄 평이 같다)
    nxt = facts_mod.build(*BIRTH, TODAY + timedelta(days=1))["today"]
    assert tm["scores"] == nxt["scores"] and tm["heads"] == nxt["heads"] and tm["term"] == nxt["term"]


@pytest.mark.parametrize("birth", [BIRTH, (date(1985, 11, 20), None, 0, "male", "부산"),
                                   (date(1999, 1, 9), 22, 10, "female", "광주")])
def test_tomorrow_never_says_today(birth):
    f = facts_mod.build(*birth, TODAY)
    rules = chapters.rule_all(f)
    blob = list(_strings(f["tomorrow"])) + [x for tab, v in rules.items() if tab.startswith("tomorrow") for x in _strings(v)]
    assert blob and not [x for x in blob if "오늘" in x]
    assert any("내일" in x for x in blob)


# ---------------------------------------------------------------- 학업 무게 (근거 있는 것만)


def test_study_weights_have_sources():
    ids = {r["id"] for r in store.table("source")}
    assert {"study_sina", "study_mseanchan", "study_devcomma", "study_udn", "study_wiki_planets"} <= ids
    nonzero = {g for g, w in STUDY_GOD_BONUS.items() if w}
    assert nonzero == {"정인", "편인", "식신", "상관"}          # 근거를 찾은 십신만
    assert STUDY_GOD_BONUS["정인"] > STUDY_GOD_BONUS["편인"] > STUDY_GOD_BONUS["식신"] > STUDY_GOD_BONUS["상관"] > 0
    w = {r["code"]: r["w_study"] for r in store.table("planet")}
    assert {k for k, v in w.items() if v} == {"mercury", "jupiter"}


def test_study_score_follows_resource_star(monkeypatch):
    from love_fortune import domains
    monkeypatch.setattr(domains, "_jitter", lambda *a: 0)
    # 경금 일간(6): 무토(4)=편인, 기토(5)=정인, 임수(8)=식신, 갑목(0)=편재. 같은 지지에서 비교한다
    base = [6, 4, 6, 7]
    got = {g: study_score(6, base, s, 3, "x") for g, s in (("정인", 5), ("편인", 4), ("식신", 8), ("편재", 0))}
    assert {g: v[0] - got["편재"][0] for g, v in got.items()} == {"정인": 6, "편인": 4, "식신": 2, "편재": 0}
    assert any("'편재'" in x and "따로 더하거나 빼는 신호는 아닌" in x for x in got["편재"][1])


def test_munchang_day_counts_for_study(sheet):
    # 경금 일간의 문창귀인은 해. 2026-10-16 은 계해일
    tm = sheet["tomorrow"]
    saju = next(s for s in tm["domains"]["study"]["systems"] if s["name"] == "사주")
    assert any("문창귀인" in x for x in saju["lines"]) and saju["only"] >= 2


def _zw(day_palace, day_stars, sihua, extra=()):
    pals = [{"name": day_palace, "stars": list(day_stars)}] + [{"name": n, "stars": list(st)} for n, st in extra]
    return {"liuri": {"palace": day_palace, "branch": "자", "sihua": sihua},
            "palaces": pals, "liuyue": {"palace": day_palace}}


def test_ziwei_study_signals():
    # 유일이 관록궁 + 그 자리에 문성(천괴) + 화과가 문곡(명궁) → 관록 1 + 문성 1 + 화과 1
    z = _ziwei(_zw("관록", ["천괴"], {"록": "없는별", "권": "없는별", "과": "문곡", "기": "없는별"},
                   [("명궁", ["문곡"])]))
    assert z["points"]["study"] == 3 and z["points"]["career"] == 1
    # 문창 화기 (문창이 학업 자리 밖) → -3
    z = _ziwei(_zw("명궁", [], {"록": "없는별", "권": "없는별", "과": "없는별", "기": "문창"}, [("부모", ["문창"])]))
    assert z["points"]["study"] == -3 and any("공부 흐름이 막히기 쉬워" in x for x in z["lines"])
    # 문창이 관록궁에 있으면 관록궁 화기로 한 번만 센다 (겹쳐 세지 않음)
    z = _ziwei(_zw("명궁", [], {"록": "없는별", "권": "없는별", "과": "없는별", "기": "문창"}, [("관록", ["문창"])]))
    assert z["points"]["study"] == -3 and z["points"]["career"] == -3
    # 직접 근거만 (2026-10-15 사용자 결정): 관록궁 별에 붙은 화록·화권은 직장에만, 학업에는 0
    z = _ziwei(_zw("명궁", [], {"록": "무곡", "권": "천상", "과": "없는별", "기": "없는별"},
                   [("관록", ["무곡", "천상"])]))
    assert z["points"]["career"] == 5 and z["points"]["study"] == 0
    # 관록궁 별에 붙은 화과는 직장 +1, 학업은 문성인 화과로만 +1 (관록궁 몫으로는 세지 않음)
    z = _ziwei(_zw("명궁", [], {"록": "없는별", "권": "없는별", "과": "무곡", "기": "없는별"}, [("관록", ["무곡"])]))
    assert z["points"]["career"] == 1 and z["points"]["study"] == 1


def test_tips_change_by_day():
    # 팁·피할 것은 날짜·영역 해시로 고른다 (예전엔 태어난 날로만 골라 날마다 같았다)
    seen = {d: set() for d in ("career", "money", "study")}
    for i in range(10):
        t = facts_mod.build(*BIRTH, TODAY + timedelta(days=i))["today"]["domains"]
        for d in seen:
            seen[d].add((tuple(t[d]["tips"]), t[d]["avoid"]))
    assert all(len(v) >= 5 for v in seen.values()), {d: len(v) for d, v in seen.items()}
    a = facts_mod.build(*BIRTH, TODAY)["today"]["domains"]["study"]
    assert a == facts_mod.build(*BIRTH, TODAY)["today"]["domains"]["study"]      # 같은 날은 늘 같다


# ---------------------------------------------------------------- 총운 = 네 영역 평균 + 공통 기운


def test_total_score_uses_four_domains():
    a = total_score(6, [6, 4, 6, 7], 3, 9, 40, 60, 80, [], 0, "s", study=100)
    b = total_score(6, [6, 4, 6, 7], 3, 9, 40, 60, 80, [], 0, "s", study=20)
    assert a[0] - b[0] == 20                                   # 학업 80점 차이 → 평균 20점 차이
    assert "학업 100" in a[1][0]


def test_pick_total_includes_study():
    r = pick_dates(*BIRTH, date(2026, 10, 15), date(2026, 10, 21), "total")
    assert all("study" in x for x in r["rows"])
    r2 = pick_dates(*BIRTH, date(2026, 10, 15), date(2026, 10, 21), "study")
    assert [x["score"] for x in r2["rows"]] == sorted((x["study"] for x in r2["rows"]), reverse=True)


# ---------------------------------------------------------------- 탭·챕터


def test_tab_ids_and_order():
    ids = list(chapters.TABS)
    assert ids[:10] == list(TAB_IDS) and ids[10:] == ["newyear", "life"]
    for dom, word in (("love", "연애"), ("career", "직장운"), ("money", "금전운"), ("study", "학업운")):
        assert chapters.TABS[dom]["title"] == f"오늘의 {word}"
        assert chapters.TABS[f"tomorrow_{dom}"]["title"] == f"내일의 {word}"
        assert [c["id"] for c in chapters.TABS[f"tomorrow_{dom}"]["chapters"]] == \
               [c["id"] for c in chapters.TABS[dom]["chapters"]]
    assert chapters.TABS["tomorrow"]["title"] == "내일의 총운"


def test_tomorrow_picks_only_tomorrow_and_have_no_personal_data(sheet):
    for tab, t in chapters.TABS.items():
        for ch in t["chapters"]:
            ps = ch["pick"]
            if tab.startswith("tomorrow"):
                assert not any(p.startswith("today") for p in ps), (tab, ps)
                assert "tomorrow.date" in ps
            else:
                assert not any(p.startswith("tomorrow") for p in ps), (tab, ps)
            assert not any(p.startswith(("today.term", "today.todo", "tomorrow.term", "tomorrow.todo")) for p in ps)
            part = chapters.pick(sheet, ps)
            blob = json.dumps(part, ensure_ascii=False)
            assert "1990-05-05" not in blob and "서울" not in blob


def test_lifetime_cache_keys_untouched_by_new_fields(sheet):
    old = copy.deepcopy(sheet)
    del old["tomorrow"]
    for d in ("today",):
        for k in ("scores", "heads", "domains"):
            old[d][k].pop("study", None)
    for tab in ("newyear", "life"):
        for ch in chapters.TABS[tab]["chapters"]:
            assert chapters.key_of(tab, ch["id"], sheet) == chapters.key_of(tab, ch["id"], old)


def test_old_shared_sheet_without_new_fields(sheet):
    old = copy.deepcopy(sheet)
    del old["tomorrow"]
    for k in ("scores", "heads", "domains"):
        old["today"][k].pop("study")
    rules = chapters.rule_all(old)
    assert "study" not in rules and not any(t.startswith("tomorrow") for t in rules)
    assert "학업" not in rules["today"]["today"]["blocks"][0]["body"]
    assert not chapters.available("tomorrow_love", old) and chapters.available("love", old)


def test_prefetch_puts_tomorrow_after_today(monkeypatch, sheet):
    seen = []
    monkeypatch.setattr(prefetch, "submit", lambda tab, ch, f, prio: seen.append((prio, tab, ch)))
    n = prefetch.submit_all(sheet)
    assert n == len(seen) == 57
    order = [tab for _, tab, _ in sorted(seen)]
    last_today = max(i for i, t in enumerate(order) if t in TAB_IDS[:5])
    first_tomorrow = min(i for i, t in enumerate(order) if t.startswith("tomorrow"))
    last_tomorrow = max(i for i, t in enumerate(order) if t.startswith("tomorrow"))
    first_rest = min(i for i, t in enumerate(order) if t in ("newyear", "life"))
    assert last_today < first_tomorrow and last_tomorrow < first_rest
    assert sum(1 for t in order if t.startswith("tomorrow")) == 20 and order.count("study") == 4


def test_rule_chapters_for_new_tabs(sheet):
    rules = chapters.rule_all(sheet)
    assert rules["tomorrow"]["today"]["blocks"][0]["body"].startswith("내일 총운 ")
    assert "학업" in rules["today"]["today"]["blocks"][0]["body"]
    assert rules["study"]["score"]["headline"].startswith("오늘 학업 ")
    assert rules["tomorrow_study"]["score"]["headline"].startswith("내일 학업 ")


# ---------------------------------------------------------------- 공유 링크로 다시 열어도 내일이 있다


@pytest.fixture(scope="module")
def server():
    from http.server import ThreadingHTTPServer
    from love_fortune.web import Handler
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _post(url, obj):
    req = urllib.request.Request(url, data=json.dumps(obj).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def test_share_keeps_tomorrow(server):
    rep = _post(server + "/api/v2/report", {"birth": "1990-05-05", "birth_time": "14:30", "sex": "female", "city": "서울"})
    f = rep["facts"]
    nxt = (date.fromisoformat(f["meta"]["target"]) + timedelta(days=1)).isoformat()
    assert f["tomorrow"]["date"] == nxt and "study" in f["today"]["scores"]
    assert set(TAB_IDS) <= set(rep["rules"]) and set(TAB_IDS) <= set(rep["outline"])
    sh = _post(server + "/api/v2/share", {"token": rep["token"]})
    got = _post(server + "/api/v2/shared", {"id": sh["id"]})
    assert got["facts"]["tomorrow"]["date"] == nxt                    # 저장한 날의 다음 날
    assert "tomorrow_study" in got["rules"]
    body = _post(server + "/api/v2/chapter", {"token": got["token"], "tab": "tomorrow_study", "chapter": "score"})
    assert body["headline"].startswith("내일 학업 ")
