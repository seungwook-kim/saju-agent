"""yongsin.py, 신강약·격국·용신 추정 + 일간 성격 + 대운 풀이 (로컬·결정적).

정통 명리(월령·통근·투출)의 뼈대를 그대로 쓰되, 점수화는 간략 추정임을
밝히고 구성 요소(득령·통근·투출)는 사실 그대로 보여준다.
일간 성격은 고전 통설의 정형화된 풀이를 정리한 것이다.
"""
from __future__ import annotations

STEMS_KR = ["갑", "을", "병", "정", "무", "기", "경", "신", "임", "계"]
BRANCHES_KR = ["자", "축", "인", "묘", "진", "사", "오", "미", "신", "유", "술", "해"]

# 일간 10별 성격 풀이 (고전 통설 정리)
ILGAN_CHARACTER = {
    # 다른 풀이와 같은 말투(반말)로 쓴다. 예전엔 '~이다', '~좋다' 문어체라 한 문단 안에서 말투가 섞였다.
    "갑": "곧게 뻗는 소나무 기질이야. 시작하면 밀고 나가는 힘이 있고, "
           "남 앞에 서는 걸 마다하지 않아. 고집이 셀 때는 한 박자 쉬면 좋아.",
    "을": "덩굴식물 기질이야. 유연하게 감아 올라가며 적응력이 뛰어나. "
           "겉은 부드러워도 속은 목표가 분명해. 우유부단해 보일 땐 기준을 하나로 잡으면 좋아.",
    "병": "한낮 태양 기질이야. 밝고 열정적이며 베푸는 걸 좋아해. "
           "타오르듯 앞만 보다 지치기 쉬우니 페이스를 조절하면 좋아.",
    "정": "촛불 기질이야. 섬세하고 따뜻하며 상대를 살뜰히 챙겨. "
           "걱정이 많아지면 혼자 끙끙 앓으니 말로 꺼내면 좋아.",
    "무": "큰 산 기질이야. 묵직하고 믿음직하며 약속을 지켜. "
           "고집으로 굳어지기 전에 다른 길을 한 번 보면 좋아.",
    "기": "기름진 밭 기질이야. 포용력이 넓고 돌보는 손이 커. "
           "걱정이 쌓이면 몸으로 오기 쉬우니 쉬는 시간을 챙기면 좋아.",
    "경": "바위 기질이야. 결단력이 강하고 밀어붙이는 힘이 있어. "
           "서두르면 부서지기 쉬우니 큰 결정은 하룻밤 묵히면 좋아.",
    "신": "잘 벼린 보석 기질이야. 예민하고 정교하며 미적 감각이 뛰어나. "
           "날이 서면 주변과 부딪히니 한 박자 부드럽게 가면 좋아.",
    "임": "넓은 바다 기질이야. 품이 크고 사람을 가리지 않으며 통이 커. "
           "흘러넘치기 쉬우니 한 곳에 모으는 그릇을 정하면 좋아.",
    "계": "새벽 이슬 기질이야. 직감이 예리하고 총명하며 눈치가 빨라. "
           "생각이 많아지면 행동이 늦어지니 작은 것부터 움직이면 좋아.",
}

# 녹·양인 자리 (일간 → (녹지지, 양인지지))
LU_YANGBLADE = {
    0: (2, 3), 1: (3, 2), 2: (5, 6), 3: (6, 5), 4: (5, 6),
    5: (6, 5), 6: (8, 9), 7: (9, 8), 8: (11, 0), 9: (0, 11),
}

GEGUK_MEAN = {
    "건록격": "스스로 일어서는 힘이 강한 구조야. 독립심과 추진력이 장점이야.",
    "양인격": "칼날 같은 결단력이 있는 구조야. 속도가 무기지만 급하면 다칠 수 있어.",
    "정관격": "반듯하고 신뢰받는 구조야. 책임과 원칙이 빛나는 때가 많아.",
    "편관격": "강하게 밀어붙이는 구조야. 위기에서 두각을 나타내.",
    "정인격": "학문과 뒷받침이 따르는 구조야. 준비된 자리에 앉으면 커져.",
    "편인격": "엉뚱한 재능이 튀는 구조야. 남과 다른 길에서 통해.",
    "식신격": "표현하고 만드는 구조야. 결과물을 내면 알아줘.",
    "상관격": "끼와 말이 넘치는 구조야. 무대에 서면 빛나.",
    "정재격": "착실히 모으는 구조야. 꾸준함이 자산이 돼.",
    "편재격": "크게 움직이는 구조야. 판이 벌어지면 통해.",
    "비견격": "동료와 어깨를 나누는 구조야. 함께 가면 멀리 가.",
    "겁재격": "승부욕으로 뚫는 구조야. 경쟁에서 살아남아.",
}


def analyze(ds: int, stems: list[int], branches: list[int],
            bonqi: list[int], month_branch: int) -> dict:
    """신강약 추정 + 격국 + 용신. 구성 요소는 사실, 점수는 간략 추정."""
    from .rules import ten_god, STEM_ELEMENT, SAENG
    from .manseryuk import BRANCH_ELEMENT
    me_elem = STEM_ELEMENT[ds]
    mb_elem = BRANCH_ELEMENT[month_branch]
    # 득령: 월지가 나를 낳거나 같으면 득령
    deukryeong = SAENG[mb_elem] == me_elem or mb_elem == me_elem
    # 통근: 지지에 같은 오행이 있으면 통근
    tonggeun = [nm for nm, b in zip(("년", "월", "일", "시"), branches)
                if BRANCH_ELEMENT[b] == me_elem]
    # 투출: 천간에 비겁·인성이 있으면 투출
    tuchul = []
    for nm, s in zip(("년", "월", "일", "시"), stems):
        g = ten_god(ds, s)
        if g in ("비견", "겁재", "정인", "편인"):
            tuchul.append(f"{nm}간 {STEMS_KR[s]}({g})")
    score = 50
    if deukryeong:
        score += 20
    score += min(20, 10 * len(tonggeun))
    score += min(10, 5 * len(tuchul))
    strong = score >= 60
    # 격국: 월지 본기 기준 (녹·양인 우선)
    lu, yd = LU_YANGBLADE[ds]
    if month_branch == lu:
        geguk = "건록격"
    elif month_branch == yd:
        geguk = "양인격"
    else:
        month_god = ten_god(ds, bonqi[month_branch])
        geguk = {"비견": "비견격", "겁재": "겁재격", "식신": "식신격",
                 "상관": "상관격", "정재": "정재격", "편재": "편재격",
                 "정관": "정관격", "편관": "편관격", "정인": "정인격",
                 "편인": "편인격"}.get(month_god, "비견격")
    # 용신 (부억 간략법): 강하면 누르고 빼고, 약하면 돕고 세운다
    if strong:
        yongsin = "관성·식상·재성 기운 (힘을 빼고 다스리는 쪽)"
    else:
        yongsin = "인성·비겁 기운 (돕고 세우는 쪽)"
    return {
        "score": score, "strong": strong,
        "strong_label": "신강 쪽" if strong else "신약 쪽",
        "deukryeong": deukryeong,
        "tonggeun": tonggeun, "tuchul": tuchul,
        "geguk": geguk, "geguk_mean": GEGUK_MEAN[geguk],
        "yongsin": yongsin,
    }


def narrate_dayun_steps(steps: list[dict], ds: int, db: int) -> list[str]:
    """대운 8스텝 풀이문."""
    from .rules import ten_god, branch_relation
    from .narrate import GOD_SHORT, _rel_text, _eun
    out = []
    for s in steps:
        stem = STEMS_KR.index(s["ganzhi"][0])
        branch = BRANCHES_KR.index(s["ganzhi"][1])
        god = ten_god(ds, stem)
        rel = _rel_text(branch_relation(db, branch))
        tail = "" if rel.endswith("사이") else " 사이야"
        out.append(f"{s['ganzhi']}운({s['from']}~{s['to']}세): "
                   f"천간 {s['ganzhi'][0]}{_eun(s['ganzhi'][0])} 나에게 "
                   f"{GOD_SHORT[god]} 기운, 지지 {s['ganzhi'][1]}{_eun(s['ganzhi'][1])} 일지와 "
                   f"{rel}{tail}.")
    return out
