"""domains.py, 영역별 오늘 운세 엔진 (로컬·결정적).

총운·직장운·금전운. 연애운 점수 엔진을 영역별로 응용한 구조이며,
서술은 전통 해석에 근거한 경향·흐름체.
"""
from __future__ import annotations

import hashlib

from .rules import ten_god, branch_relation, _jitter
from .manseryuk import STEM_ELEMENT
from .rules import SAENG, GEUK

CAREER_GOD_BONUS = {"정관": 5, "정인": 4, "식신": 3, "정재": 3, "편재": 2,
                    "비견": 1, "편인": 0, "상관": -1, "겁재": -2, "편관": -3}
CAREER_GOD_LINE = {
    "정관": "맡은 일에서 신뢰가 쌓이기 쉬운 흐름",
    "정인": "윗사람·선배의 지원이 따르기 쉬운 흐름",
    "식신": "준비한 결과물을 보이기 좋은 흐름",
    "정재": "꾸준한 업무가 실적으로 이어지기 쉬운 흐름",
    "편재": "밖으로 움직이는 일·영업이 잘 맞는 흐름",
    "비견": "동료와 호흡이 맞기 쉬운 흐름",
    "편인": "자기 페이스대로 파고들기 좋은 흐름",
    "상관": "말이 앞서기 쉬우니 문서로 정리하면 좋은 흐름",
    "겁재": "경쟁·비교에 에너지 쓰지 말고 내 일에 집중하기 좋은 흐름",
    "편관": "압박이 느껴지면 우선순위부터 다시 잡기 좋은 흐름",
}
MONEY_GOD_BONUS = {"정재": 6, "편재": 4, "식신": 3, "정관": 2, "상관": 1,
                   "정인": 1, "비견": -1, "편인": 0, "편관": -2, "겁재": -5}
MONEY_GOD_LINE = {
    "정재": "차곡차곡 모으는 재미가 있는 흐름",
    "편재": "움직인 만큼 들어올 여지가 있는 흐름, 다만 씀씀이 조절이 함께",
    "식신": "만들고 파는 쪽에 기회가 엿보이는 흐름",
    "정관": "월급·정기수입 라인이 안정적인 흐름",
    "상관": "아이디어가 돈이 될 실마리가 보이는 흐름",
    "정인": "아껴둔 것이 빛을 보는 흐름",
    "비견": "나눠 쓸 일은 분명히 정해두면 좋은 흐름",
    "편인": "조용히 모으기 좋은 흐름",
    "편관": "예상 밖 지출에 대비해두면 좋은 흐름",
    "겁재": "지갑이 가벼워지기 쉬우니 큰 결정은 미루면 좋은 흐름",
}

CAREER_TIPS = [
    "회의 전 요점을 세 줄로 정리해두기",
    "보고는 결론부터, 이유는 뒤에 붙이기",
    "동료 일을 10분만 거들어주기",
    "메신저·메일 답은 당일 안에 짧게 보내기",
    "점심은 평소와 다른 사람과 먹어보기",
    "퇴근 전 30분은 내일 할 일 정리하기",
    "배움에 30분 투자하기",
    "일정에 버퍼를 두고 무리한 약속 잡지 않기",
]
CAREER_AVOID = [
    "뒷말·험담에 동참하기",
    "메신저 장문 논쟁",
    "충동적인 사직·이직 언급",
    "마감 시각 무시하기",
    "점심 술자리",
    "상사 앞에서 동료 탓하기",
]
MONEY_TIPS = [
    "고정지출 목록을 한 번 훑어보기",
    "충동구매는 24시간 미뤄보기",
    "가계부에 5분만 기록하기",
    "비상금·예비비 잔액 확인하기",
    "안 쓰는 구독 정리하기",
    "오늘 쓴 돈 메모하기",
    "저축 자동이체 점검하기",
    "비싼 결정은 내일로 미루기",
]
MONEY_AVOID = [
    "충동 쇼핑",
    "지인과의 금전 거래",
    "고수익 제안에 즉답하기",
    "카드 할부 늘리기",
    "생활비를 넘는 외식·유흥",
    "보증 서기",
]

# 관록궁·재백궁 주성 한 줄 (14주성)
CAREER_STAR = {
    "자미": "중심을 잡는 역할이 어울리는 흐름, 리더 자리가 따라",
    "천기": "기획·아이디어 싸움이 유리한 흐름, 머리 쓰는 일이 잘 맞아",
    "태양": "사람 상대·밝은 자리가 유리한 흐름, 나서면 알아줘",
    "무곡": "실무·숫자·결과로 승부하기 좋은 흐름",
    "천동": "편안한 분위기에서 실력이 나오는 흐름",
    "염정": "원칙·규율 잡는 일이 잘 맞는 흐름",
    "천부": "관리·운영·뒷정리가 빛나는 흐름",
    "태음": "섬세한 일·문서·재무 라인이 잘 맞는 흐름",
    "탐랑": "사람 만나고 판을 벌리는 일이 잘 맞는 흐름",
    "거문": "말·글·분석으로 승부하기 좋은 흐름",
    "천상": "조율·중재 역할이 어울리는 흐름",
    "천량": "가르치고 돌보는 일이 잘 맞는 흐름",
    "칠살": "돌파·개척 업무가 잘 맞는 흐름",
    "파군": "변화·혁신 과제가 어울리는 흐름",
}
MONEY_STAR = {
    "자미": "큰 판을 보는 눈이 생기는 흐름, 장기 계획이 잘 맞아",
    "천기": "정보·타이밍 싸움이 유리한 흐름",
    "태양": "밝게 드러나는 곳에서 돈이 도는 흐름",
    "무곡": "실속 챙기기에 강한 흐름, 재테크 감각이 살아",
    "천동": "편안하게 들어오는 돈이 있는 흐름",
    "염정": "원칙 지키면 쌓이는 흐름",
    "천부": "창고를 채우는 흐름, 저축·자산관리가 잘 맞아",
    "태음": "조용히 불어나는 흐름, 적금·예금이 잘 맞아",
    "탐랑": "돌고 도는 돈이 많은 흐름, 씀씀이 관리가 함께",
    "거문": "말·지식으로 버는 흐름",
    "천상": "함께 굴리면 불어나는 흐름",
    "천량": "베푼 만큼 돌아오는 흐름",
    "칠살": "한 방보다 분산이 맞는 흐름",
    "파군": "판이 바뀌는 곳에 기회가 있는 흐름",
}

TOTAL_KEYWORDS = {
    "목": ["성장", "시작", "배움"],
    "화": ["열정", "표현", "만남"],
    "토": ["안정", "정리", "신뢰"],
    "금": ["결단", "정돈", "마무리"],
    "수": ["유연", "경청", "흐름"],
}


def _element_reasons(me_elem: str, today_elem: str, flavor: str) -> tuple[int, list[str]]:
    if SAENG[today_elem] == me_elem:
        tail = {"일": "일은 수월하게 풀려", "돈": "돈의 흐름이 살아나",
                "전반": "전반적으로 순조롭게 풀려"}[flavor]
        return 8, [f"오늘 {today_elem} 기운이 나({me_elem})를 돕는 흐름이라 {tail}"]
    if SAENG[me_elem] == today_elem:
        tail = {"일": "일에 베풀면 돌아와", "돈": "돈을 베풀면 돌아와",
                "전반": "베풀면 돌아와"}[flavor]
        return 1, [f"내가 흐름에 에너지를 주는 날이라 {tail}"]
    if GEUK[me_elem] == today_elem:
        tail = {"일": "일은 속도 조절이 좋아", "돈": "돈은 속도 조절이 좋아",
                "전반": "속도 조절이 좋아"}[flavor]
        return -4, [f"내 기운이 오늘 흐름을 누르는 날이라 {tail}"]
    if GEUK[today_elem] == me_elem:
        tail = {"일": "일은 무리하지 않는 게 좋아", "돈": "돈은 무리하지 않는 게 좋아",
                "전반": "무리하지 않는 게 좋아"}[flavor]
        return -6, [f"오늘 흐름이 나를 누르는 날이라 {tail}"]
    tail = {"일": "일의 리듬이 잘 맞아", "돈": "돈의 리듬이 잘 맞아",
            "전반": "하루 리듬이 잘 맞아"}[flavor]
    return 3, [f"나와 오늘 흐름이 같은 {me_elem} 기운이라 {tail}"]


def _branch_points(branches: list[int], today_branch: int, flavor: str):
    score, reasons = 0, []
    hap = chung = rest = 0
    for b in branches:
        for r in branch_relation(b, today_branch):
            if "육합" in r or "삼합" in r:
                hap += 1
            elif "육충" in r:
                chung += 1
            else:
                rest += 1
    if hap:
        score += min(12, 5 * hap)
        reasons.append(f"내 사주와 오늘 일진이 손잡는 자리가 {hap}개 있어 {flavor} 쪽 인연·기회가 엮이기 쉬워")
    if chung:
        score -= min(12, 6 * chung)
        reasons.append(f"오늘 일진과 정면으로 부딪치는 자리가 {chung}개 있어 {flavor} 일은 확인을 한 번 더 하면 좋아")
    if rest:
        score -= min(6, 3 * rest)
        reasons.append(f"얽매거나 깨뜨리는 자리가 {rest}개 있어 {flavor} 쪽 사소한 마찰은 바로 풀면 좋아")
    return score, reasons


def _pick(seed: str, pool: list[str], n: int) -> list[str]:
    order = sorted(range(len(pool)),
                   key=lambda i: hashlib.sha256(f"{seed}|{i}".encode()).hexdigest())
    return [pool[i] for i in order[:n]]


def career_score(day_stem: int, branches: list[int], today_stem: int,
                 today_branch: int, seed_extra: str = "") -> tuple[int, list[str], str]:
    reasons: list[str] = []
    score = 55
    me_elem = STEM_ELEMENT[day_stem]
    today_elem = STEM_ELEMENT[today_stem]
    s, r = _element_reasons(me_elem, today_elem, "일")
    score += s
    reasons += r
    s, r = _branch_points(branches, today_branch, "일")
    score += s
    reasons += r
    god = ten_god(day_stem, today_stem)
    score += CAREER_GOD_BONUS.get(god, 0)
    from .narrate import GOD_MEAN
    reasons.append(f"오늘 들어온 기운과 나는 일로 '{god}' 사이야. {GOD_MEAN[god]} {CAREER_GOD_LINE[god]}")
    score += _jitter(f"career-{day_stem}-{today_stem}-{today_branch}-{seed_extra}", -5, 5)
    return max(1, min(100, score)), reasons, today_elem


def money_score(day_stem: int, branches: list[int], today_stem: int,
                today_branch: int, seed_extra: str = "") -> tuple[int, list[str], str]:
    reasons: list[str] = []
    score = 55
    me_elem = STEM_ELEMENT[day_stem]
    today_elem = STEM_ELEMENT[today_stem]
    wealth_elem = GEUK[me_elem]
    if today_elem == wealth_elem:
        score += 6
        reasons.append(f"오늘 {today_elem} 기운이 내 재물 기운과 닿아 돈의 흐름이 살아나는 날")
    else:
        s, r = _element_reasons(me_elem, today_elem, "돈")
        score += s
        reasons += r
    s, r = _branch_points(branches, today_branch, "돈")
    score += s
    reasons += r
    god = ten_god(day_stem, today_stem)
    score += MONEY_GOD_BONUS.get(god, 0)
    from .narrate import GOD_MEAN
    reasons.append(f"오늘 들어온 기운과 나는 돈으로 '{god}' 사이야. {GOD_MEAN[god]} {MONEY_GOD_LINE[god]}")
    score += _jitter(f"money-{day_stem}-{today_stem}-{today_branch}-{seed_extra}", -5, 5)
    return max(1, min(100, score)), reasons, today_elem


def total_score(day_stem: int, branches: list[int], today_stem: int,
                today_branch: int, love: int, career: int, money: int,
                daxian_hua: list[str], liunian_branch: int,
                seed_extra: str = "") -> tuple[int, list[str], str, list[str]]:
    reasons: list[str] = []
    score = round((love + career + money) / 3)
    me_elem = STEM_ELEMENT[day_stem]
    today_elem = STEM_ELEMENT[today_stem]
    s, r = _element_reasons(me_elem, today_elem, "전반")
    score += s // 2
    reasons.append(f"연애 {love}·직장 {career}·금전 {money}의 평균에서 출발한 오늘 총운")
    reasons += r
    if "기" in daxian_hua:
        score -= 3
        reasons.append("현재 대운에 화기가 있어 무리한 확장보다 정리가 어울리는 흐름")
    if "록" in daxian_hua or "권" in daxian_hua:
        score += 3
        reasons.append("현재 대운에 화록·화권이 있어 밀어붙일 일이 통하기 쉬운 흐름")
    for rel in branch_relation(branches[2], liunian_branch):
        if "육합" in rel or "삼합" in rel:
            score += 3
            reasons.append("유년명궁이 내 일지와 호흡이 맞아 한 해의 리듬이 좋은 흐름")
            break
    score += _jitter(f"total-{day_stem}-{today_stem}-{today_branch}-{seed_extra}", -4, 4)
    score = max(1, min(100, score))
    keywords = _pick(f"kw-{today_branch}-{seed_extra}", TOTAL_KEYWORDS[today_elem], 3)
    return score, reasons, today_elem, keywords


def band_headline(score: int, kind: str) -> str:
    table = {
        "career": [(85, "밀어붙이기 좋은 흐름, 중요한 일을 앞에 배치하면 좋아"),
                   (70, "손발이 맞기 좋은 흐름, 협업·보고가 수월해"),
                   (55, "루틴을 지키기 좋은 흐름, 기본기가 빛나"),
                   (40, "관망·정리가 어울리는 흐름, 급한 결정은 미루면 좋아"),
                   (0, "충전이 어울리는 흐름, 쉬어가며 점검하면 좋아")],
        "money": [(85, "돈의 흐름이 살아나는 날, 계획한 집행을 하기 좋아"),
                  (70, "차곡차곡 모으기 좋은 흐름, 작은 절약이 쌓여"),
                  (55, "지키는 게 이기는 흐름, 현상 유지가 좋아"),
                  (40, "지갑 단속이 필요한 흐름, 큰 결정은 미루면 좋아"),
                  (0, "관망이 답인 흐름, 새 투자는 쉬어가면 좋아")],
        "total": [(85, "무엇이든 해보기 좋은 흐름, 좋은 기운을 나눠주면 좋아"),
                  (70, "하루가 순조롭게 풀리기 쉬운 흐름, 약속을 잡기 좋아"),
                  (55, "평온하게 보내기 좋은 흐름, 루틴대로 가면 좋아"),
                  (40, "속도 조절이 필요한 흐름, 쉬엄쉬엄 가면 좋아"),
                  (0, "나를 돌보기 좋은 흐름, 무리하지 않으면 좋아")],
    }
    for bar, line in table[kind]:
        if score >= bar:
            return line
    return table[kind][-1][1]
