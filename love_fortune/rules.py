"""rules.py, 오행·합충형파해·십신 규칙표 + 연애운 점수 엔진.

규칙 출처 표기:
- [정설] 육합·육충·삼합·오행 상생상극, 명리 교과서 공통.
- [민간 통설] 삼형·파·해의 세부 분류, 일간→행운숫자, 점수 가중치는 전통 통설 기반 자의적 수치.
  출처 불확실 규칙은 점수에만 반영하고 단정 서술을 하지 않는다.
"""
from __future__ import annotations

from .josa import j


from .manseryuk import STEM_ELEMENT, STEMS_KR

# [정설] 육합 (6쌍)
LIUHE = {0: 1, 1: 0, 2: 11, 11: 2, 3: 10, 10: 3,
         4: 9, 9: 4, 5: 8, 8: 5, 6: 7, 7: 6}
LIUHE_PAIRS = [("자", "축"), ("인", "해"), ("묘", "술"),
               ("진", "유"), ("사", "신"), ("오", "미")]

# [정설] 삼합 (4국)
SANHE = {
    frozenset((8, 0, 4)): "수국(신자진)",
    frozenset((11, 3, 7)): "목국(해묘미)",
    frozenset((2, 6, 10)): "화국(인오술)",
    frozenset((5, 9, 1)): "금국(사유축)",
}

# [정설] 육충 (6쌍), 띠 궁합 '상충'으로도 널리 알려짐
CHUNG = {0: 6, 6: 0, 1: 7, 7: 1, 2: 8, 8: 2,
         3: 9, 9: 3, 4: 10, 10: 4, 5: 11, 11: 5}

# [민간 통설] 삼형
SAMHYEONG = [frozenset((2, 5, 8)), frozenset((1, 10, 7))]
# [민간 통설] 자묘 상형
SELF_HYEONG_NOTE = "자묘 상형(예의 없는 형), 민간 통설"

# [민간 통설] 육파
PA = {0: 9, 9: 0, 1: 4, 4: 1, 2: 11, 11: 2,
      3: 6, 6: 3, 5: 8, 8: 5, 7: 10, 10: 7}

# [민간 통설] 육해
HAE = {0: 7, 7: 0, 1: 6, 6: 1, 2: 5, 5: 2,
       3: 4, 4: 3, 8: 11, 11: 8, 9: 10, 10: 9}

# [정설] 오행 상생 / 상극
SAENG = {"목": "화", "화": "토", "토": "금", "금": "수", "수": "목"}
GEUK = {"목": "토", "토": "수", "수": "화", "화": "금", "금": "목"}  # 내가 극하는 것

# [정설] 십신, 일간 기준 타 천간과의 관계 (음양 포함)
# 비견/겁재/식신/상관/편재/정재/편관/정관/편인/정인
_TEN_GODS = {
    # (같은오행?, 같은음양?) -> 십신
    (True, True): "비견", (True, False): "겁재",
}


def ten_god(day_stem: int, other_stem: int) -> str:
    """[정설] 십신 산출. 일간이 극하는 것은 재성, 극당하면 관성, 생하면 식상, 생받으면 인성."""
    if day_stem == other_stem:
        return "비견"
    me, other = STEM_ELEMENT[day_stem], STEM_ELEMENT[other_stem]
    same_yin = (day_stem % 2) == (other_stem % 2)
    if me == other:
        return "비견" if same_yin else "겁재"
    if SAENG[me] == other:  # 내가 생함
        return "식신" if same_yin else "상관"
    if SAENG[other] == me:  # 생받음
        return "편인" if same_yin else "정인"
    if GEUK[me] == other:  # 내가 극
        return "편재" if same_yin else "정재"
    return "편관" if same_yin else "정관"  # 극당함


def branch_relation(a: int, b: int) -> list[str]:
    """두 지지 사이의 관계 목록. [정설]/[민간 통설] 표기 포함."""
    rels: list[str] = []
    if LIUHE.get(a) == b:
        rels.append("육합[정설]")
    if CHUNG.get(a) == b:
        rels.append("육충[정설]")
    for trio, name in SANHE.items():
        if a in trio and b in trio and a != b:
            rels.append(f"삼합({name})[정설]")
    for trio in SAMHYEONG:
        if a in trio and b in trio and a != b:
            rels.append("삼형[민간 통설]")
    if (a, b) in [(0, 3), (3, 0)]:
        rels.append("자묘 상형[민간 통설]")
    if PA.get(a) == b:
        rels.append("파[민간 통설]")
    if HAE.get(a) == b:
        rels.append("해[민간 통설]")
    return rels


def _jitter(seed: str, lo: int = -5, hi: int = 5) -> int:
    """예전엔 날짜 해시로 ±5점을 흔들었다. 근거 없는 잡음이라 없앴다 (항상 0).

    같은 날 점수 차이는 이제 사주·자미두수·점성술·택일 층(today.py)에서만 난다.
    """
    return 0


# 연애운에서 오늘 기운이 '이성 인연의 별'일 때 주는 가점. 명리에서 남성에게는
# 재성(정재·편재), 여성에게는 관성(정관·편관)이 이성을 뜻한다. 예전엔 성별을
# 보지 않아 여성도 정재 날에 가장 높은 점수를 받았다. [민간 통설·자작 수치]
_GOD_BONUS_BASE = {"정인": 4, "식신": 3, "비견": 2, "겁재": -2, "상관": -1, "편인": 0}
_GOD_BONUS_SEX = {
    "male": {"정재": 5, "편재": 3, "정관": 2, "편관": -2},
    "female": {"정관": 5, "편관": 2, "정재": 2, "편재": 1},
    None: {"정재": 5, "편재": 2, "정관": 4, "편관": -3},   # 성별을 모를 때 (예전 값)
}
_SPOUSE_GODS = {"male": ("정재", "편재"), "female": ("정관", "편관")}


def love_score(day_stem: int, birth_branches: list[int],
               today_stem: int, today_branch: int,
               seed_extra: str = "", sex: str | None = None) -> tuple[int, list[str], str]:
    """오늘 연애운 점수(0~100) + 근거 문장 + 오늘 주도 오행.

    sex 가 주어지면 이성 인연의 별(남성 재성, 여성 관성)에 가점을 준다.
    가중치는 전통 통설 기반 수치[민간 통설·자작]이며 단정적 효력을 주장하지 않는다.
    """
    sex = sex if sex in ("male", "female") else None
    reasons: list[str] = []
    score = 55  # base
    me_elem = STEM_ELEMENT[day_stem]
    today_elem = STEM_ELEMENT[today_stem]

    # 1) 오늘 오행과 일간(나)의 생극, [정설] 상생상극 방향만 차용
    if SAENG[today_elem] == me_elem:
        score += 8
        reasons.append(f"오늘 {today_elem} 기운이 나({STEMS_KR[day_stem]}·{me_elem})를 생해주는 흐름")
    elif SAENG[me_elem] == today_elem:
        score += 1
        reasons.append("내가 오늘 흐름에 에너지를 주는 날, 베푸는 매력이 통하기 쉬운 흐름")
    elif GEUK[me_elem] == today_elem:
        score -= 4
        reasons.append("내 기운이 오늘 흐름을 극하는 날, 밀어붙이기보다 속도 조절이 어울리는 흐름")
    elif GEUK[today_elem] == me_elem:
        score -= 6
        reasons.append("오늘 흐름이 나를 극하는 날, 무리한 고백보다 가벼운 안부가 어울리는 흐름")
    else:
        score += 3
        reasons.append(f"나와 오늘 흐름이 같은 {me_elem} 기운, 공감대 형성이 수월한 흐름")

    # 2) 지지 관계: 내 사주 4지지 vs 오늘 일지
    hap = chung = hyeongpah = 0
    for b in birth_branches:
        for r in branch_relation(b, today_branch):
            if "육합" in r or "삼합" in r:
                hap += 1
            elif "육충" in r:
                chung += 1
            else:
                hyeongpah += 1
    if hap:
        score += min(12, 5 * hap)
        reasons.append(f"내 사주와 오늘 일진이 손잡는 합이 {hap}개 있어 인연이 이어지기 쉬운 흐름")
    if chung:
        score -= min(12, 6 * chung)
        reasons.append(f"오늘 일진과 정면으로 부딪치는 자리가 {chung}개 있어 확인을 한 번 더 하면 좋은 흐름")
    if hyeongpah:
        score -= min(6, 3 * hyeongpah)
        reasons.append(f"얽매거나 깨뜨리는 자리가 {hyeongpah}개 있어 사소한 오해는 바로 풀면 좋은 흐름")

    # 3) 오늘 일간과의 십신, [정설] 표 차용, 해석은 연애 흐름 한정
    from .narrate import GOD_MEAN
    god = ten_god(day_stem, today_stem)
    god_bonus = {**_GOD_BONUS_BASE, **_GOD_BONUS_SEX[sex]}
    score += god_bonus.get(god, 0)
    if sex and god in _SPOUSE_GODS[sex]:
        star = "재성(남성에게 이성 인연을 뜻하는 별)" if sex == "male"             else "관성(여성에게 이성 인연을 뜻하는 별)"
        reasons.append(f"오늘 들어온 {j(chr(39) + god + chr(39), '은')} {star}이라 인연이 가까이 오기 쉬운 흐름")
    reasons.append(f"오늘 들어온 기운과 나는 '{god}' 사이야. {GOD_MEAN[god]} "
                   + {"정재": "진심이 통하기 쉬운 흐름",
                      "정관": "신뢰가 쌓이기 쉬운 흐름",
                      "정인": "따뜻한 배려가 오가기 쉬운 흐름",
                      "식신": "유머·표현이 살기 쉬운 흐름",
                      "비견": "친구 같은 편안함이 흐르기 쉬운 흐름",
                      "겁재": "감정 소모에 주의가 필요한 흐름",
                      "상관": "말이 앞서기 쉬우니 경청이 좋은 흐름",
                      "편재": "설렘·이벤트가 어울리는 흐름",
                      "편관": "긴장·부담이 생기기 쉬운 흐름",
                      "편인": "혼자만의 시간도 필요한 흐름"}.get(god, "평이한 흐름"))

    # 4) 결정적 지터 (±5), 같은 날짜+생일에 항상 동일
    score += _jitter(f"{day_stem}-{today_stem}-{today_branch}-{seed_extra}", -5, 5)

    score = max(1, min(100, score))
    return score, reasons, today_elem


def headline(score: int) -> str:
    if score >= 85:
        return "설렘이 앞서기 좋은 흐름, 먼저 안부를 건네기 좋은 날"
    if score >= 70:
        return "호감이 쌓이기 좋은 흐름, 가벼운 약속을 잡기 좋은 날"
    if score >= 55:
        return "편안한 대화가 어울리는 흐름, 무리하지 않는 게 좋은 날"
    if score >= 40:
        return "관망이 어울리는 흐름, 경청과 관찰이 좋은 날"
    return "충전이 어울리는 흐름, 나를 돌보는 게 좋은 날"
