"""natal_extra.py, 원국을 더 자세히: 지장간·기둥별 12운성·12신살·귀인·원진·띠 궁합.

출처 대조 (2026-09 조사, 둘 이상이 맞는 것만 넣음)
- 지장간: 한국 월률분야 (여기·중기·정기). 만세력 강의 자료와 상용 사주 서비스 표기가 같고,
  lunar-python(중국 간략표)은 인·신·사·해의 여기 무토를 빼서 쓰지 않았다.
- 기둥별 12운성: 일간이 각 지지에서 갖는 단계. lunar-python 지세와 대조 (match.TWELVE_STAGES).
- 12신살: 삼합의 첫 글자(생지)에서 지살을 시작해 차례로 12개. 대구신문 칼럼·나무위키 등과 같다.
  년지 기준이 기본이고 일지 기준을 함께 본다.
- 문창귀인: 사주스터디·사자사주와 상용 사주 서비스 세 곳이 같다.
- 학당귀인: 일간의 장생 자리. 한 사이트는 경금을 해로 적었으나 같은 표에 '장생'이라 써 놓아
  앞뒤가 맞지 않아 정의(장생)를 따랐다 (상용 서비스도 경금→사).
- 암록: 일간 건록과 육합하는 지지. 여러 사이트가 같은 규칙 (예: 신금→진).
- 금여록: 건록에서 두 칸 앞 (갑→진, 을→사 ...).
- 띠 궁합: 삼합·육합이면 잘 맞음, 충·원진·육해면 조심, 나머지는 무난 (널리 쓰는 12지 궁합법).
"""
from __future__ import annotations

from .josa import j
from .manseryuk import BRANCHES_KR, STEMS_KR, ZODIAC_ANIMALS
from .match import STAGE_NAMES, TWELVE_STAGES

# 지장간 (여기, 중기, 정기): 천간 번호. 중기가 없으면 두 개
HIDDEN = {
    0: (8, 9), 1: (9, 7, 5), 2: (4, 2, 0), 3: (0, 1), 4: (1, 9, 4), 5: (4, 6, 2),
    6: (2, 5, 3), 7: (3, 1, 5), 8: (4, 8, 6), 9: (6, 7), 10: (7, 3, 4), 11: (4, 0, 8),
}
TRIOS = [(8, 0, 4), (2, 6, 10), (5, 9, 1), (11, 3, 7)]      # 신자진, 인오술, 사유축, 해묘미
SINSAL12 = ["지살", "년살", "월살", "망신살", "장성살", "반안살",
            "역마살", "육해살", "화개살", "겁살", "재살", "천살"]
SINSAL_TALK = {
    "지살": "새 출발·이동의 기운", "년살": "사람을 끄는 매력의 기운(도화)",
    "월살": "기운이 마르고 막히기 쉬운 자리", "망신살": "나를 드러내다 체면이 걸리기 쉬운 자리",
    "장성살": "앞장서 이끄는 기운", "반안살": "안장에 올라 인정받는 기운",
    "역마살": "멀리 움직이고 옮겨 다니는 기운", "육해살": "사람 사이 마찰이 생기기 쉬운 자리",
    "화개살": "혼자 몰두하는 예술·학문의 기운", "겁살": "빼앗기거나 갑자기 흔들리기 쉬운 자리",
    "재살": "갇히고 다투기 쉬운 자리", "천살": "뜻밖의 일을 조심할 자리",
}
LOK = {0: 2, 1: 3, 2: 5, 3: 6, 4: 5, 5: 6, 6: 8, 7: 9, 8: 11, 9: 0}          # 건록
MUNCHANG = {0: 5, 1: 6, 2: 8, 3: 9, 4: 8, 5: 9, 6: 11, 7: 0, 8: 2, 9: 3}     # 문창귀인
LIUHE = {0: 1, 1: 0, 2: 11, 11: 2, 3: 10, 10: 3, 4: 9, 9: 4, 5: 8, 8: 5, 6: 7, 7: 6}
CHUNG = {b: (b + 6) % 12 for b in range(12)}
WONJIN = {0: 7, 7: 0, 1: 6, 6: 1, 2: 9, 9: 2, 3: 8, 8: 3, 4: 11, 11: 4, 5: 10, 10: 5}
YUKHAE = {0: 7, 7: 0, 1: 6, 6: 1, 2: 5, 5: 2, 3: 4, 4: 3, 8: 11, 11: 8, 9: 10, 10: 9}
GWIMUN = {0: 9, 9: 0, 1: 6, 6: 1, 2: 7, 7: 2, 3: 8, 8: 3, 4: 11, 11: 4, 5: 10, 10: 5}
GUIIN_TALK = {
    "문창귀인": "배우고 글로 풀어내는 재주의 별", "학당귀인": "공부와 가르침에 강한 별",
    "암록": "남모르게 들어오는 도움과 재물의 별", "금여록": "곁사람 덕을 보는 복의 별",
}
PILLARS = (("year", "년주"), ("month", "월주"), ("day", "일주"), ("hour", "시주"))


def _trio(b: int) -> tuple[int, int, int]:
    return next(t for t in TRIOS if b in t)


def sinsal12_at(base: int, target: int) -> str:
    """base 지지(년지·일지) 삼합을 기준으로 target 지지가 12신살 중 무엇인지."""
    return SINSAL12[(target - _trio(base)[0]) % 12]


def hakdang(ds: int) -> int:
    return TWELVE_STAGES[ds][0]          # 장생 자리


def amrok(ds: int) -> int:
    return LIUHE[LOK[ds]]


def geumyeo(ds: int) -> int:
    return (LOK[ds] + 2) % 12


def pillars_detail(natal: dict) -> list[dict]:
    """기둥별 천간·지지·지장간·12운성. 시간 미상이면 시주는 빠진다."""
    ds = natal["ilgan_stem"]
    out = []
    for key, label in PILLARS:
        s, b = natal["pillars"][key]
        if s is None or b is None:
            continue
        from .match import BRANCH_BONQI
        from .rules import ten_god
        out.append({"key": key, "label": label, "stem": STEMS_KR[s], "branch": BRANCHES_KR[b],
                    "stem_god": "일간(나)" if key == "day" else ten_god(ds, s),
                    "branch_god": ten_god(ds, BRANCH_BONQI[b]),
                    "hidden": [STEMS_KR[h] for h in HIDDEN[b]],
                    "stage": STAGE_NAMES[TWELVE_STAGES[ds].index(b)]})
    return out


def natal_sinsal(natal: dict) -> dict:
    """원국에 든 12신살(년지·일지 기준)과 귀인, 원진·귀문."""
    ds = natal["ilgan_stem"]
    items = [(label, natal["pillars"][key][1]) for key, label in PILLARS
             if natal["pillars"][key][1] is not None]
    yb, db = natal["pillars"]["year"][1], natal["pillars"]["day"][1]
    sinsal = []
    for base_name, base in (("년지", yb), ("일지", db)):
        for label, b in items:
            name = sinsal12_at(base, b)
            if name in ("지살", "장성살"):       # 삼합 자기 자리라 흔한 것은 빼지 않고 함께 보인다
                pass
            sinsal.append({"base": base_name, "at": label, "branch": BRANCHES_KR[b],
                           "name": name, "talk": SINSAL_TALK[name]})
    guiin = []
    for name, target in (("문창귀인", MUNCHANG[ds]), ("학당귀인", hakdang(ds)),
                         ("암록", amrok(ds)), ("금여록", geumyeo(ds))):
        where = [label for label, b in items if b == target]
        if where:
            guiin.append({"name": name, "branch": BRANCHES_KR[target], "at": where,
                          "talk": GUIIN_TALK[name]})
    pairs = []
    for i in range(len(items)):
        for k in range(i + 1, len(items)):
            (la, a), (lb, b) = items[i], items[k]
            if WONJIN[a] == b:
                pairs.append(f"{la}·{lb} 원진(서로 미워하고 끌리는 묘한 긴장)")
            if GWIMUN[a] == b:
                pairs.append(f"{la}·{lb} 귀문(예민하고 직감이 날카로운 기운)")
    return {"sinsal": sinsal, "guiin": guiin, "pairs": pairs}


def animal_compat(my_branch: int) -> dict:
    """내 띠 기준 12띠 궁합: 잘 맞음·무난·조심."""
    good, bad, mid = [], [], []
    trio = _trio(my_branch)
    for b in range(12):
        if b == my_branch:
            continue
        why = []
        if b in trio:
            why.append("삼합(한 팀으로 뭉치는 사이)")
        if LIUHE[my_branch] == b:
            why.append("육합(손잡는 사이)")
        warn = []
        if CHUNG[my_branch] == b:
            warn.append("충(정면으로 부딪치는 사이)")
        if WONJIN[my_branch] == b:
            warn.append("원진(서로 서운하기 쉬운 사이)")
        if YUKHAE[my_branch] == b:
            warn.append("육해(작은 마찰이 쌓이기 쉬운 사이)")
        row = {"animal": ZODIAC_ANIMALS[b], "branch": BRANCHES_KR[b], "why": why or warn}
        (good if why and not warn else bad if warn else mid).append(row)
    return {"me": ZODIAC_ANIMALS[my_branch], "good": good, "mid": mid, "bad": bad}


# ---------------------------------------------------------------- 일주 카드
# 일간 물상: 일간 기질 풀이(yongsin.ILGAN_CHARACTER)의 첫 비유와 같다
STEM_IMAGE = {0: "소나무", 1: "덩굴", 2: "한낮의 태양", 3: "촛불", 4: "큰 산", 5: "기름진 밭",
              6: "바위", 7: "보석", 8: "넓은 바다", 9: "새벽 이슬"}
# 요즘 널리 쓰는 색 이름 (오방색: 목 푸른·화 붉은·토 누런·금 흰·수 검은).
# 띠에 색을 붙이는 것은 2007년 무렵부터 퍼진 요즘 표현이고 전통 풍속은 아니다 (문화일보 2026 설특집 기사 등)
STEM_COLOR = {0: "푸른", 1: "푸른", 2: "붉은", 3: "붉은", 4: "누런", 5: "누런", 6: "흰", 7: "흰", 8: "검은", 9: "검은"}
# 백호대살 일곱 간지 (여러 사주 사이트 공통): 갑진·을미·병술·정축·무진·임술·계축
BAEKHO = {(0, 4), (1, 7), (2, 10), (3, 1), (4, 4), (8, 10), (9, 1)}


def ilju_card(natal: dict, spouse_god: str, jindohwa: bool) -> dict:
    """일주(태어난 날의 간지) 카드. 전통 물상(일간 비유 + 일지 띠 동물)이 중심이고 색 이름은 요즘 표현으로 따로 둔다."""
    from .manseryuk import KUIGANG
    ds, db = natal["ilgan_stem"], natal["day_branch"]
    marks = []
    if (ds, db) in KUIGANG:
        marks.append({"name": "괴강", "talk": "결단력이 아주 강한 일주 (연해자평 기준 경진·경술·임진·무술)"})
    if (ds, db) in BAEKHO:
        marks.append({"name": "백호", "talk": "한번 잡은 목표를 끝까지 밀어붙이는 센 기운의 일주"})
    if jindohwa:
        marks.append({"name": "진도화", "talk": "일주 자체에 사람을 끄는 매력이 담긴 일주"})
    stage = STAGE_NAMES[TWELVE_STAGES[ds].index(db)]
    return {"pillar": STEMS_KR[ds] + BRANCHES_KR[db], "image": STEM_IMAGE[ds], "animal": ZODIAC_ANIMALS[db],
            "title": f"{j(STEM_IMAGE[ds], '와')} {ZODIAC_ANIMALS[db]}", "modern": f"{STEM_COLOR[ds]} {ZODIAC_ANIMALS[db]}",
            "stage": stage, "spouse_god": spouse_god, "marks": marks}
