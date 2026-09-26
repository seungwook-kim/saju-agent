"""today.py, '오늘'을 세 체계로 함께 본다: 사주 + 자미두수 + 점성술, 그리고 한국 택일.

예전 오늘 운세는 사주 일진과 원국의 합충·십신만 보고, 자미두수는 올해(유년)까지,
점성술은 '내 금성 원소 대 오늘 태양 원소' 한 줄뿐이었다. 여기서 체계마다 '오늘'에
해당하는 층을 계산해 영역별(연애·직장·금전) 점수 가감과 근거 문장을 만든다.

- 사주: 오늘 일진에서 내 일간의 십이운성, 오늘 들어온 신살(천을귀인·도화·역마·공망),
        억부 용신 기준으로 오늘 기운이 도움이 되는지
- 자미두수: 유일(오늘)이 걸린 궁, 유일 사화가 내 명반의 어느 영역에 붙는지
- 점성술: 오늘 하늘 행성과 출생 행성의 각도 (transit.py)
- 택일: 생기복덕·황도흑도·건제12신·충 (almanac.py), 보조 지표로 작게 반영

점수 폭과 가중치는 전통 해석의 방향(길·흉)을 따른 자작 수치이며 단정적 효력을 주장하지 않는다.
"""
from __future__ import annotations

from datetime import date

from . import almanac, store
from .josa import j
from .manseryuk import (BRANCHES_KR, STEMS_KR, TIANYI, KONGWANG, YIMA_AT, _trio_of,
                        day_pillar)
from .match import BRANCH_BONQI, DOHWA_MAP, STAGE_NAMES, TWELVE_STAGES
from .narrate import GOD_SHORT, PALACE_TALK
from .rules import ten_god

DOMAINS = ("love", "career", "money")

# 십이운성 기운 세기 (전통 분류: 제왕·건록이 가장 왕성, 병·사·절이 가장 약함)
STAGE_POINTS = {"제왕": 2, "건록": 2, "장생": 1, "관대": 1, "목욕": 0, "양": 0,
                "쇠": -1, "태": -1, "묘": -1, "병": -2, "사": -2, "절": -2}
STAGE_TALK = {"장생": "새로 태어나 자라는 기운", "목욕": "씻고 꾸미며 들뜨는 기운",
              "관대": "갓을 쓰고 세상에 나서는 기운", "건록": "제 몫을 받아 일하는 기운",
              "제왕": "가장 왕성하게 뻗는 기운", "쇠": "한풀 꺾여 차분해지는 기운",
              "병": "힘이 빠져 쉬어야 하는 기운", "사": "멈춰 서서 돌아보는 기운",
              "묘": "창고에 거둬 넣는 기운", "절": "끊고 새로 준비하는 기운",
              "태": "새 씨앗을 품는 기운", "양": "품에서 기르는 기운"}
GOD_GROUP = {"비견": "비겁", "겁재": "비겁", "정인": "인성", "편인": "인성",
             "식신": "식상", "상관": "식상", "정재": "재성", "편재": "재성",
             "정관": "관성", "편관": "관성"}
# 자미두수 궁 → 영역
PALACE_DOMAIN = {"부처(배우자)": "love", "자녀": "love", "복덕": "love",
                 "관록": "career", "천이": "career", "노복": "career", "형제": "career",
                 "재백": "money", "전택": "money"}
HUA_POINTS = {"록": 3, "권": 2, "과": 1, "기": -3}
HUA_TALK = {"록": "복이 붙는", "권": "힘이 실리는", "과": "이름이 나는", "기": "막힘이 걸리는"}
HUA_RESULT = {"록": "풀리기 쉬운 흐름이야.", "권": "힘을 받아 밀고 나가기 쉬운 흐름이야.",
              "과": "좋은 평을 듣기 쉬운 흐름이야.", "기": "막히기 쉬우니 서두르지 않는 게 좋아."}
DOMAIN_KR = {"love": "연애", "career": "직장", "money": "금전"}


def _signal(x: float) -> str:
    return "좋음" if x > 1 else "조심" if x < -1 else "보통"


def _saju(natal: dict, today: date, strong: bool | None) -> dict:
    ds, db = natal["ilgan_stem"], natal["day_branch"]
    yb = natal["pillars"]["year"][1]
    ts, tb = day_pillar(today)
    pts = {"all": 0, "love": 0, "career": 0, "money": 0}
    lines, tags = [], []                     # tags: 줄마다 어느 영역 몫인지 (all = 모든 영역 공통)
    stage = STAGE_NAMES[TWELVE_STAGES[ds].index(tb)]
    pts["all"] += STAGE_POINTS[stage]
    stage_q = j(f"'{stage}'", "야")          # '절'이야 / '묘'야 (따옴표 안 글자로 받침을 본다)
    lines.append(f"오늘 일진({STEMS_KR[ts]}{BRANCHES_KR[tb]})에서 내 일간 {STEMS_KR[ds]}의 기운 단계"
                 f"(십이운성)는 {stage_q}. {STAGE_TALK[stage]}이라 "
                 + ("힘 있게 움직이기 좋은 날" if STAGE_POINTS[stage] > 0 else
                    "무리하지 말고 페이스를 지키면 좋은 날" if STAGE_POINTS[stage] < 0 else
                    "평소 리듬대로 가면 되는 날") + "이야.")
    tags.append("all")
    if tb in TIANYI[ds]:
        pts["all"] += 2
        lines.append("오늘은 천을귀인(어려울 때 돕는 귀한 사람의 별)이 드는 날이라 도움을 청하면 통하기 쉬워.")
        tags.append("all")
    my_dohwa = {d for base, d in DOHWA_MAP if yb in base or db in base}
    if tb in my_dohwa:
        pts["love"] += 3
        lines.append("오늘은 내 도화(사람을 끄는 매력의 별)가 드는 날이라 만남과 호감이 늘기 쉬워.")
        tags.append("love")
    my_yima = {YIMA_AT[_trio_of(db)], YIMA_AT[_trio_of(yb)]}
    if tb in my_yima:
        pts["career"] += 1
        lines.append("오늘은 역마(움직이고 옮겨 다니는 별)가 드는 날이라 외근·이동이 많은 일에 맞아.")
        tags.append("career")
    idx60 = next(n for n in range(60) if n % 10 == ds and n % 12 == db)
    if tb in KONGWANG[idx60 // 10]:
        pts["all"] -= 1
        lines.append("오늘 일진이 내 공망(비어 있는 자리)에 들어 약속·결과가 허전하게 비기 쉬우니 확인을 한 번 더 해.")
        tags.append("all")
    god = ten_god(ds, ts)
    group = GOD_GROUP[god]
    if strong is not None:
        good = {"식상", "재성", "관성"} if strong else {"인성", "비겁"}
        if group in good:
            pts["all"] += 2
            lines.append(f"내 사주는 {'기운이 센 편(신강)' if strong else '기운이 약한 편(신약)'}이라 "
                         f"{'힘을 빼서 쓰는' if strong else '돕고 받쳐 주는'} 기운이 반가운데, 오늘 들어온 "
                         f"{j(f'{god}({GOD_SHORT[god]})', '은')} 딱 그쪽이라 도움이 되는 흐름이야.")
            tags.append("all")
        else:
            pts["all"] -= 1
            lines.append(f"내 사주는 {'기운이 센 편(신강)' if strong else '기운이 약한 편(신약)'}인데 오늘 들어온 "
                         f"{j(f'{god}({GOD_SHORT[god]})', '은')} 그 균형을 {'더 키우는' if strong else '더 흔드는'} "
                         "쪽이라 과하지 않게 쓰면 좋은 흐름이야.")
            tags.append("all")
    total = pts["all"] * 3 + pts["love"] + pts["career"] + pts["money"]
    return {"name": "사주", "points": pts, "lines": lines, "tags": tags, "signal": _signal(total / 2),
            "stage": stage}


def _ziwei(zw: dict | None) -> dict | None:
    if zw is None:
        return None
    pts = {"all": 0, "love": 0, "career": 0, "money": 0}
    lines, tags = [], []
    ld = zw["liuri"]
    lines.append(f"자미두수로 오늘(유일)은 내 {ld['palace']} 자리({ld['branch']})에 걸려, "
                 f"{PALACE_TALK.get(ld['palace'], '그 자리')}에 일이 모이기 쉬운 날이야.")
    dom = PALACE_DOMAIN.get(ld["palace"])
    tags.append(dom)                         # 영역이 없는 궁이면 None (점수에 안 들어가는 참고 줄)
    if dom:
        pts[dom] += 1
    star_palace = {s: p["name"] for p in zw["palaces"] for s in p["stars"]}
    for hua, star in ld["sihua"].items():
        pal = star_palace.get(star)
        if pal is None:
            continue
        d = PALACE_DOMAIN.get(pal, "all")
        pts[d] += HUA_POINTS[hua] if d != "all" else HUA_POINTS[hua] // 2
        # 점수에 들어가는 사화는 모두 근거 줄을 남긴다 (예전엔 권·과는 점수만 더하고 줄이 없었다)
        lines.append(f"오늘 일진이 {star}에 {j(f'화{hua}({HUA_TALK[hua]} 기운)', '을')} 붙여 내 {pal} 쪽이 "
                     + HUA_RESULT[hua])
        tags.append(d)
    lm = zw["liuyue"]
    lines.append(f"이번 달(유월)은 {lm['palace']} 자리에 걸려 한 달의 무게가 그쪽에 실려 있어.")
    tags.append(None)
    total = pts["all"] * 2 + pts["love"] + pts["career"] + pts["money"]
    return {"name": "자미두수", "points": pts, "lines": lines, "tags": tags, "signal": _signal(total)}


def _astro(birth: date, hour: int | None, minute: int, city: str, today: date) -> dict:
    from .transit import describe, transits
    tr = transits(birth, hour, minute, city, today)
    pts = {"all": 0}
    for k in DOMAINS:
        pts[k] = max(-6, min(6, round(tr["points"][k] * 3)))
    lines = describe(tr, limit=3)
    total = sum(pts[k] for k in DOMAINS)
    return {"name": "점성술", "points": pts, "lines": lines, "signal": _signal(total / 2),
            "transits": tr["hits"][:6]}


def _almanac(today: date, birth: date, sex: str, branches: list[int]) -> dict:
    info = almanac.day_info(today, birth, sex, branches)
    pts, why = almanac.day_luck_points(info)
    off = store.by_key("officer")[info["officer"]]
    sg = store.by_key("saenggi").get(info.get("saenggi", ""))
    ly, lm, ld, leap = info["lunar"]
    cal = (f"음력 {lm}월 {ld}일{'(윤달)' if leap else ''} · 일진 {info['iljin']} · "
           f"건제 '{info['officer']}'{'(좋은 날)' if info['officer_good'] else '(조심하는 날)'} "
           f"· {info['spirit']} {'황도일' if info['spirit_yellow'] else '흑도일'} · 28수 {info['mansion']}수")
    lines = [cal]
    lines.append(f"건제 '{info['officer']}': {off['meaning']}. {off['advice']}.")
    if sg:
        lines.append(f"생기복덕으로 보면 오늘은 나(세는나이 {info['age']}세)에게 '{sg['name']}'일, {sg['meaning']}.")
    extra = []
    if info["son_eomneun"]:
        extra.append("손 없는 날(이사·개업을 많이 잡는 날)")
    if info["wolgi"]:
        extra.append("월기일(음력 5·14·23일, 이사·혼례를 꺼리는 날)")
    extra.append(f"{info['clash_animal']}띠와 부딪치는 날")
    lines.append("오늘 달력: " + ", ".join(extra) + ".")
    return {"name": "택일", "points": pts, "lines": lines + why[:1], "info": info}


def layers(birth: date, hour: int | None, minute: int, sex: str, city: str,
           today: date, natal: dict, zw: dict | None, strong: bool | None) -> dict:
    """오늘을 세 체계와 택일로 본 결과. adj 는 영역별 점수 가감."""
    branches = [b for _s, b in natal["pillars"].values() if b is not None]
    saju = _saju(natal, today, strong)
    ziwei = _ziwei(zw)
    astro = _astro(birth, hour, minute, city, today)
    alm = _almanac(today, birth, sex, branches)
    systems = [s for s in (saju, ziwei, astro) if s is not None]
    adj = {}
    for k in DOMAINS:
        v = sum(s["points"].get("all", 0) + s["points"].get(k, 0) for s in systems)
        v += alm["points"] // 2
        adj[k] = max(-15, min(15, v))
    adj["total"] = max(-15, min(15, round(sum(adj[k] for k in DOMAINS) / 3) + alm["points"] // 2))
    sig = {s["name"]: s["signal"] for s in systems}
    goods = [n for n, v in sig.items() if v == "좋음"]
    bads = [n for n, v in sig.items() if v == "조심"]
    n = len(systems)
    if len(goods) == n:
        agree = f"{'세' if n == 3 else '두'} 체계가 모두 좋은 쪽을 가리키는 날이야. 미뤄 둔 일을 밀어붙이기 좋아."
    elif len(bads) == n:
        agree = f"{'세' if n == 3 else '두'} 체계가 모두 조심하라고 하는 날이야. 큰 결정은 미루고 정리에 힘쓰면 좋아."
    elif goods and not bads:
        agree = f"{', '.join(goods)} 쪽이 좋은 신호를 보내고 나머지는 잔잔한 날이야. 무난하게 흐름을 타면 돼."
    elif bads and not goods:
        agree = f"{', '.join(bads)} 쪽에서 조심 신호가 오고 나머지는 잔잔한 날이야. 그 부분만 한 번 더 살피면 돼."
    elif goods and bads:
        agree = (f"체계마다 신호가 엇갈리는 날이야 ({', '.join(goods)}는 좋음, {', '.join(bads)}는 조심). "
                 "좋은 쪽은 살리고 조심할 쪽은 한 번 더 확인하면 좋아.")
    else:
        agree = "세 체계 모두 특별히 치우치지 않은 잔잔한 날이야. 평소 리듬을 지키면 돼."
    best = max(DOMAINS, key=lambda k: adj[k])
    worst = min(DOMAINS, key=lambda k: adj[k])
    focus = (f"세 체계를 합치면 오늘은 {DOMAIN_KR[best]} 쪽에 힘이 실리고"
             + (f" {DOMAIN_KR[worst]} 쪽은 한 템포 쉬어 가면 좋은 흐름이야." if adj[worst] < 0 else " 나머지도 무난한 흐름이야."))
    return {"systems": systems, "almanac": alm, "adj": adj, "signals": sig,
            "agreement": agree, "focus": focus}
