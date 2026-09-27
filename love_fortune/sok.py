"""sok.py, 속궁합(19) 풀이: 화성(욕망)·금성(끌림) 별자리와 두 사람 사이 각도, 사주 일지 궁합.

성인 확인을 켠 사람에게만 화면에 보인다. 표현은 솔직하되 노골적인 묘사는 하지 않는다.
별자리 풀이는 여러 해설을 대조해 공통으로 말하는 결만 옮겨 적었다 (문장을 옮기지 않고 새로 씀).
- 화성: swamihoroscope, astrolink, xonecole 의 별자리별 해설
- 금성: astrostyle, thehoodwitch 의 별자리별 해설
- 두 사람 금성·화성 각도: cafeastrology, teaandrosemary 의 금성-화성 시너스트리 해설
  (합이 가장 강하고, 삼합·육합은 자연스럽게 맞고, 사각·충은 끌림은 세지만 스타일이 부딪친다)
- 달·화성 각도: teaandrosemary 달-화성 해설, elsaelsa·astrologyking 달-화성 충 해설
- 사주: 일지(배우자 자리이자 몸 자리)끼리 합이면 끌리고 편하고, 충·형·원진은 주의 (사주클래스, 사자사주 궁합 해설)
"""
from __future__ import annotations

from .astro import SIGNS
from .manseryuk import BRANCHES_KR
from .rules import branch_relation

MARS = {
    "양자리": "원하면 바로 들이대는 직진형이야. 밀당 없이 뜨겁게 붙고, 그 에너지를 받아 줄 자신감 있는 상대랑 맞아.",
    "황소자리": "서두르지 않고 오감으로 천천히 즐기는 타입이야. 스킨십이랑 분위기가 중요하고, 한번 불붙으면 오래가.",
    "쌍둥이자리": "말로 불을 붙이는 타입이야. 대화, 장난, 새로운 시도가 없으면 금방 지루해해.",
    "게자리": "마음이 통해야 몸이 열리는 타입이야. 다정하게 감싸 주는 스타일이고, 아껴진다고 느낄 때 제일 뜨거워.",
    "사자자리": "주도권 잡고 제대로 보여 주고 싶은 타입이야. 로맨틱하고 통 크게 해 주고, 칭찬받으면 더 불타. 거절당하면 자존심이 확 상해.",
    "처녀자리": "디테일에 강한 타입이야. 상대가 뭘 좋아하는지 세심하게 챙기고, 깔끔함이랑 배려가 기본이야.",
    "천칭자리": "분위기랑 균형을 중요하게 보는 타입이야. 예쁜 공간에서 상대 취향에 맞춰 주고, 로맨스가 먼저야.",
    "전갈자리": "몸이랑 마음을 통째로 섞고 싶은 타입이야. 얕은 관계로는 안 차고, 깊고 강렬하게 빠져.",
    "사수자리": "자유롭고 모험적인 타입이야. 새로운 경험이랑 장난을 좋아하고, 매달리지는 않아.",
    "염소자리": "차근차근 쌓아 가는 타입이야. 인내심이 있고, 상대를 확실히 만족시키려는 끈기가 있어.",
    "물병자리": "정해진 틀을 싫어하는 실험가 타입이야. 머리로 통해야 흥미가 생기고, 색다른 걸 해 보고 싶어 해.",
    "물고기자리": "경계가 녹아내리는 몰입형이야. 분위기, 음악, 상상에 약하고, 상대에게 헌신적으로 맞춰 줘.",
}
VENUS = {
    "양자리": "첫눈에 확 끌리고 쫓는 걸 즐겨. 대담하게 표현하는 상대에게 설레.",
    "황소자리": "느리게 타오르는 감각파야. 촉감, 향, 분위기 같은 오감과 편안함이 중요해.",
    "쌍둥이자리": "말 잘 통하고 재밌는 사람한테 끌려. 대화가 곧 스킨십이야.",
    "게자리": "마음 열기까지 오래 걸리지만, 믿으면 깊고 다정해져. 보살핌받는 느낌에 약해.",
    "사자자리": "사랑받고 주목받을 때 빛나. 특별 대우랑 칭찬에 약해.",
    "처녀자리": "겉멋보다 진심이랑 성실함에 끌려. 세심하게 챙겨 주는 사람에게 열려.",
    "천칭자리": "아름다운 분위기랑 매너에 끌려. 조화롭고 품위 있는 관계를 원해.",
    "전갈자리": "깊고 강렬한 교감을 원해. 상대 속은 다 알고 싶어 하면서 자기 속은 천천히 열어.",
    "사수자리": "자유롭고 모험적인 연애가 좋아. 새로운 경험을 같이 하는 사람한테 끌려.",
    "염소자리": "천천히, 진지하게 가. 능력 있고 믿음직한 사람에게 끌리고, 믿음이 쌓이면 깊은 감각이 열려.",
    "물병자리": "독특하고 머리로 통하는 사람에게 끌려. 친구 같은 연애, 틀에 안 박힌 관계가 편해.",
    "물고기자리": "낭만이랑 상상에 약해. 음악, 분위기, 교감으로 꿈같은 연결을 원해.",
}
MOON_MARS = {
    "hard": "속마음(달)이랑 욕망(화성)이 부딪치는 각도야. 불은 세게 붙는데 몸이랑 마음이 따로 놀기 쉬워. "
            "몸은 잘 맞는데 마음이 허하거나, 마음은 편한데 밤이 심심한 식으로 엇갈릴 수 있어. 둘 다 채워 주는 사람이 필요해.",
    "soft": "속마음(달)이랑 욕망(화성)이 잘 이어지는 각도야. 마음이 통하면 몸도 자연스럽게 따라가.",
}
ASPECT = {  # 두 사람 금성·화성 각도
    "합": ("good", "제일 세게 붙는 조합이야. 만나자마자 끌림이 확 올 가능성이 커."),
    "삼합": ("good", "자연스럽게 잘 맞아. 로맨스랑 몸이 같이 가는 조합이야."),
    "육합": ("good", "잘 맞는 편이고, 신경 쓰면 더 좋아지는 조합이야."),
    "사각": ("warn", "끌림은 센데 스타일이 달라서 부딪치기 쉬워. 원하는 걸 말로 맞춰 가야 해."),
    "충": ("warn", "정반대라 끌림은 센데 스타일이 부딪치기 쉬워. 원하는 걸 말로 맞춰 가야 해."),
    "없음": ("mid", "둘 사이에 뚜렷한 각도는 없어."),
}
ORB = (("합", 0, 8), ("육합", 60, 5), ("사각", 90, 7), ("삼합", 120, 7), ("충", 180, 8))
YUANJIN = {0: 7, 7: 0, 1: 6, 6: 1, 2: 9, 9: 2, 3: 8, 8: 3, 4: 11, 11: 4, 5: 10, 10: 5}


def aspect_of(a: float, b: float) -> str:
    d = abs((a - b + 180) % 360 - 180)
    for name, deg, orb in ORB:
        if abs(d - deg) <= orb:
            return name
    return "없음"


def _sign_aspect(diff: int) -> str:
    diff %= 12
    return {0: "합", 4: "삼합", 8: "삼합", 2: "육합", 10: "육합", 3: "사각", 9: "사각", 6: "충"}.get(diff, "없음")


def good_signs(my_sign: str) -> tuple[list[str], list[str]]:
    """내 별(금성이나 화성)과 상대의 짝 별이 잘 맞는 별자리 / 부딪치는 별자리 (별자리 단위)."""
    i = SIGNS.index(my_sign)
    good = [SIGNS[(i + k) % 12] for k in (0, 4, 8, 2, 10)]
    hard = [SIGNS[(i + k) % 12] for k in (3, 9, 6)]
    return good, hard


def day_branch_match(db: int) -> dict:
    good = [b for b in range(12) if b != db and any(r.startswith(("육합", "삼합")) for r in branch_relation(db, b))]
    hard = [b for b in range(12) if b != db and (any(r.startswith(("육충", "삼형", "자묘")) for r in branch_relation(db, b))
                                                 or YUANJIN.get(db) == b)]
    return {"good": [BRANCHES_KR[b] for b in good], "hard": [BRANCHES_KR[b] for b in hard]}


def natal(nc: dict, day_branch: int, hour_known: bool) -> dict:
    """내 속궁합 성향 (사실표용)."""
    pos = nc["positions"]
    mars, venus = pos["mars"]["sign"], pos["venus"]["sign"]
    mm = None
    if hour_known:                         # 달은 하루에 13도쯤 움직여서 시간을 알아야 각도를 본다
        a = aspect_of(pos["moon"]["lon"], pos["mars"]["lon"])
        mm = MOON_MARS["hard"] if a in ("합", "충", "사각") else MOON_MARS["soft"] if a in ("삼합", "육합") else None
    g_v, h_v = good_signs(venus)
    g_m, h_m = good_signs(mars)
    return {
        "mars": {"sign": mars, "text": MARS[mars]},
        "venus": {"sign": venus, "text": VENUS[venus]},
        "moon_mars": mm,
        "partner_mars": {"good": g_v, "hard": h_v},       # 상대 화성이 내 금성과
        "partner_venus": {"good": g_m, "hard": h_m},      # 상대 금성이 내 화성과
        "day_branch": day_branch_match(day_branch),
    }


def pair(a_nc: dict, b_nc: dict, a_db: int, b_db: int) -> dict:
    """두 사람 속궁합: 금성·화성 교차 각도 두 개와 일지 관계."""
    pa, pb = a_nc["positions"], b_nc["positions"]
    rows = []
    for label, x, y in (("상대 화성 → 내 금성", pb["mars"]["lon"], pa["venus"]["lon"]),
                        ("상대 금성 → 내 화성", pb["venus"]["lon"], pa["mars"]["lon"])):
        asp = aspect_of(x, y)
        tone, text = ASPECT[asp]
        rows.append({"label": label, "aspect": asp, "tone": tone, "text": text})
    rels = branch_relation(a_db, b_db)
    if any(r.startswith(("육합", "삼합")) for r in rels):
        day = ("good", f"태어난 날 글자({BRANCHES_KR[a_db]}·{BRANCHES_KR[b_db]})가 손잡는 사이야. 끌리고 편한 조합으로 봐.")
    elif any(r.startswith(("육충", "삼형", "자묘")) for r in rels) or YUANJIN.get(a_db) == b_db:
        day = ("warn", f"태어난 날 글자({BRANCHES_KR[a_db]}·{BRANCHES_KR[b_db]})가 부딪치거나 조이는 사이야. 몸이 맞아도 싸움이 잦기 쉬워서 조율이 필요해.")
    else:
        day = ("mid", f"태어난 날 글자({BRANCHES_KR[a_db]}·{BRANCHES_KR[b_db]})는 합도 충도 아닌 무난한 사이야.")
    good = sum(r["tone"] == "good" for r in rows) + (day[0] == "good")
    return {"rows": rows, "day": {"tone": day[0], "text": day[1]}, "good": good, "total": 3,
            "a": {"mars": pa["mars"]["sign"], "venus": pa["venus"]["sign"]},
            "b": {"mars": pb["mars"]["sign"], "venus": pb["venus"]["sign"]}}
