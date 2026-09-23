"""matchmaking.py, 궁합 엔진 (로컬·결정적).

두 사람의 사주(일간·일지·년지·오행·십신) + 자미두수(명궁) + 점성술
(태양·달·금성 원소, 주요 시너스트리 각도)을 대칭적으로 합산한다.
점수는 0~100이 아니라 1~100, 순서를 바꿔도 같은 점수(대칭)가 나온다.
서술은 전통 해석에 근거한 경향·흐름체.
"""
from __future__ import annotations

import hashlib
from datetime import date

from .manseryuk import four_pillars, STEMS_KR, BRANCHES_KR, STEM_ELEMENT
from .rules import ten_god, branch_relation
from .match import BRANCH_BONQI
from .ziwei import ziwei_chart
from .astro import natal_chart, SIGN_ELEMENT, ASPECTS
from .narrate import GOD_SHORT, _rel_text

# 천간합 5쌍
STEM_HAP = [{0, 5}, {1, 6}, {2, 7}, {3, 8}, {4, 9}]
# 띠 원진살 6쌍 (민간 통설)
WONJIN = [{0, 7}, {1, 6}, {2, 9}, {3, 8}, {4, 11}, {5, 10}]
# 띠 삼합 4국
TRIOS = [{8, 0, 4}, {2, 6, 10}, {5, 9, 1}, {11, 3, 7}]

SYNASTRY_PAIRS = [
    (("sun", "태양"), ("sun", "태양")),
    (("moon", "달"), ("moon", "달")),
    (("venus", "금성"), ("venus", "금성")),
    (("sun", "태양"), ("moon", "달")),
    (("moon", "달"), ("sun", "태양")),
    (("venus", "금성"), ("mars", "화성")),
    (("mars", "화성"), ("venus", "금성")),
]


def _elem_rel(a: str, b: str) -> str:
    from .rules import SAENG, GEUK
    if a == b:
        return "same"
    if SAENG[a] == b or SAENG[b] == a:
        return "saeng"
    if GEUK[a] == b or GEUK[b] == a:
        return "geuk"
    return "same"


def _west_rel(a: str, b: str) -> str:
    """서양 점성술 원소 궁합 (불·공기 / 흙·물 통함)."""
    if a == b:
        return "same"
    if {a, b} in ({"불", "공기"}, {"흙", "물"}):
        return "match"
    return "clash"


def _jitter(seed: str) -> int:
    """예전엔 해시로 ±3점을 흔들었다. 근거 없는 잡음이라 없앴다 (항상 0)."""
    return 0


def compatibility(a_birth: date, a_hour: int, a_minute: int, a_sex: str,
                  a_city: str, b_birth: date, b_hour: int, b_minute: int,
                  b_sex: str, b_city: str) -> dict:
    na = four_pillars(a_birth, a_hour, a_minute, a_city)
    nb = four_pillars(b_birth, b_hour, b_minute, b_city)
    sa, sb = na["ilgan_stem"], nb["ilgan_stem"]
    dba, dbb = na["day_branch"], nb["day_branch"]
    yba, ybb = na["pillars"]["year"][1], nb["pillars"]["year"][1]
    ea, eb = STEM_ELEMENT[sa], STEM_ELEMENT[sb]

    score = 55
    plus: list[str] = []
    minus: list[str] = []
    info: list[str] = []

    # 1. 일간 천간합·극
    if {sa, sb} in STEM_HAP:
        score += 8
        plus.append(f"두 일간 {STEMS_KR[sa]}·{STEMS_KR[sb]}은 서로 합이 드는 짝이라 끌어당기기 쉬운 흐름")
    elif STEM_ELEMENT[sa] != STEM_ELEMENT[sb]:
        from .rules import GEUK
        if GEUK[ea] == eb or GEUK[eb] == ea:
            score -= 3
            minus.append(f"두 일간 기운({ea}·{eb})이 서로 견제하는 결이라 속도 조절이 필요한 흐름")

    # 2. 일지 관계
    for r in branch_relation(dba, dbb):
        if "육합" in r or "삼합" in r:
            score += 8
            plus.append(f"두 일지 {BRANCHES_KR[dba]}·{BRANCHES_KR[dbb]}는 손잡는 합이라 생활 리듬이 맞기 쉬운 흐름")
        elif "육충" in r:
            score -= 8
            minus.append(f"두 일지 {BRANCHES_KR[dba]}·{BRANCHES_KR[dbb]}는 정면으로 부딪치는 자리라 부딪힐 땐 쉬어가면 좋은 흐름")
        else:
            score -= 3
            minus.append(f"두 일지 {BRANCHES_KR[dba]}·{BRANCHES_KR[dbb]}는 {_rel_text([r])} 관계라 사소한 것은 바로 풀면 좋은 흐름")

    # 3. 띠 궁합
    trio_hit = any(yba in t and ybb in t for t in TRIOS)
    hap_hit = any(branch_relation(yba, ybb) and ("육합" in r) for r in branch_relation(yba, ybb))
    chung_hit = any("육충" in r for r in branch_relation(yba, ybb))
    wonjin_hit = {yba, ybb} in WONJIN
    if trio_hit:
        score += 6
        plus.append(f"두 띠({na['year_animal']}·{nb['year_animal']})는 같은 삼합 팀이라 큰 방향이 맞는 흐름")
    if hap_hit:
        score += 4
        plus.append(f"두 띠는 서로 합이 드는 짝이라 정이 붙기 쉬운 흐름")
    if chung_hit:
        score -= 6
        minus.append(f"두 띠는 정면으로 부딪치는 짝이라 예민한 날은 거리를 두면 좋은 흐름")
    if wonjin_hit:
        score -= 4
        minus.append(f"두 띠는 원진살 짝이라(민간 통설) 오해가 생기면 확인을 한 번 더 하면 좋은 흐름")
    if not (trio_hit or hap_hit or chung_hit or wonjin_hit):
        info.append(f"두 띠({na['year_animal']}·{nb['year_animal']})는 무난하게 어울리는 흐름")

    # 4. 오행 양방향
    for me, you, who in ((ea, eb, "상대"), (eb, ea, "나")):
        rel = _elem_rel(me, you)
        if rel == "saeng":
            score += 4
            plus.append(f"{who}에게 생해주는 기운이 흘러 보살핌이 오가는 흐름")
        elif rel == "same":
            score += 2
            plus.append(f"같은 {me} 기운이라 말이 잘 통하는 흐름")
        else:
            score -= 3
            minus.append(f"기운이 서로 견제하는 결이라 밀어붙이기보다 맞춰가면 좋은 흐름")

    # 5. 십신 양방향
    _god_bonus = {"정재": 3, "정관": 3, "정인": 3, "식신": 3, "편재": 2,
                  "편관": -2, "편인": 0, "비견": 2, "겁재": -2, "상관": -1}
    for g, who in ((ten_god(sa, sb), "상대방은 나에게"), (ten_god(sb, sa), "나는 상대에게")):
        score += _god_bonus.get(g, 0)
        plus.append(f"{who} '{g}'({GOD_SHORT[g]}) 관계로 만나는 흐름")

    # 6. 자미 명궁 관계 (한쪽이라도 시간 미상이면 제외)
    za = ziwei_chart(a_birth, a_hour, a_minute, a_sex, a_city)
    zb = ziwei_chart(b_birth, b_hour, b_minute, b_sex, b_city)
    if za is None or zb is None:
        info.append("시간 미상인 쪽이 있어 자미 명궁 관계는 제외")
    else:
        for r in branch_relation(za["mingong_branch"], zb["mingong_branch"]):
            if "육합" in r or "삼합" in r:
                score += 4
                plus.append(f"두 명궁({za['mingong']}·{zb['mingong']})이 손잡는 자리라 인생 방향이 맞는 흐름")
            elif "육충" in r:
                score -= 4
                minus.append(f"두 명궁({za['mingong']}·{zb['mingong']})이 부딪치는 자리라 생활 리듬은 맞춰가면 좋은 흐름")

    # 7. 점성술 (원소 + 시너스트리)
    ca = natal_chart(a_birth, a_hour, a_minute, a_city)
    cb = natal_chart(b_birth, b_hour, b_minute, b_city)
    for pair, label, pts in ((("sun", "sun"), "태양끼리", 4),
                             (("moon", "moon"), "달끼리", 4),
                             (("venus", "venus"), "금성끼리", 3)):
        ea2 = SIGN_ELEMENT[ca["positions"][pair[0]]["sign"]]
        eb2 = SIGN_ELEMENT[cb["positions"][pair[1]]["sign"]]
        rel = _west_rel(ea2, eb2)
        if rel in ("match", "same"):
            score += pts
            plus.append(f"{label} 원소가 잘 맞아 기본 궁합이 좋은 흐름")
        else:
            score -= 2
            minus.append(f"{label} 원소가 달라 서로 맞춰가면 좋은 흐름")
    syn_plus = 0
    syn_minus = 0
    syn_lines = []
    for (ba, na_), (bb, nb_) in SYNASTRY_PAIRS:
        la = ca["positions"][ba]["lon"]
        lb = cb["positions"][bb]["lon"]
        diff = abs(la - lb)
        diff = min(diff, 360.0 - diff)
        for ang, aname, orb in ASPECTS:
            if abs(diff - ang) <= orb:
                if aname in ("합", "삼합", "육합") and syn_plus < 2:
                    score += 3
                    syn_plus += 1
                    syn_lines.append(f"내 {na_}와 상대 {nb_}가 {aname}이라 통하기 쉬운 지점이 있어")
                elif aname in ("충", "형") and syn_minus < 2:
                    score -= 2
                    syn_minus += 1
                    syn_lines.append(f"내 {na_}와 상대 {nb_}가 {aname}이라 삐걱일 땐 쉬어가면 좋아")
                break
    plus.extend(syn_lines)

    seed = f"{a_birth.isoformat()}|{b_birth.isoformat()}|{a_sex}|{b_sex}"
    seed_rev = f"{b_birth.isoformat()}|{a_birth.isoformat()}|{b_sex}|{a_sex}"
    score += _jitter(seed if seed <= seed_rev else seed_rev)
    score = max(1, min(100, score))

    if score >= 80:
        head = "숨결이 잘 맞는 흐름, 서로에게 좋은 거울이 되기 쉬운 사이"
    elif score >= 65:
        head = "맞춰가면 깊어지는 흐름, 대화가 약이 되는 사이"
    elif score >= 50:
        head = "노력이 필요한 흐름, 규칙을 정하면 편안해지는 사이"
    else:
        head = "부딪힘이 잦은 흐름, 거리와 속도를 조율하면 좋은 사이"

    strengths = plus[:5]
    cautions = minus[:4]
    story = [f"두 사람 점수는 {score}점이야. {head} 쪽으로 읽으면 돼."]
    if strengths:
        story.append("잘 맞는 점은 " + ", 또 ".join(strengths[:2]) + "야.")
    if cautions:
        story.append("조심할 점은 " + ", 또 ".join(cautions[:2]) + "야.")
    if info:
        story.append("참고로 " + ", 또 ".join(info[:2]) + "야.")
    story.append("점수는 출발점일 뿐이야. 부딪히는 날은 쉬어가고, 맞는 날은 더 가까워지면 돼.")
    return {
        "score": score, "head": head, "story": story,
        "plus": plus, "minus": minus, "info": info,
        "strengths": strengths, "cautions": cautions,
        "a_ilgan": STEMS_KR[sa], "b_ilgan": STEMS_KR[sb],
        "a_day_branch": BRANCHES_KR[dba], "b_day_branch": BRANCHES_KR[dbb],
        "a_animal": na["year_animal"], "b_animal": nb["year_animal"],
        "a_mingong": za["mingong"] if za else "시간 미상이라 제외",
        "b_mingong": zb["mingong"] if zb else "시간 미상이라 제외",
        "a_sun": ca["positions"]["sun"]["sign"],
        "b_sun": cb["positions"]["sun"]["sign"],
    }
