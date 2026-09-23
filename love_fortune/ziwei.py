"""ziwei.py, 자미두수 정통 명반 (로컬·결정적).

계산 근거 (iztro 배성결 문서 + 자미두수전서 구결 대조):
- 명신궁 정하기: 인궁에서 정월 시작, 생월까지 순행, 그 궁에서 자시 시작해
  생시까지 거꾸로 세면 명궁, 앞으로 세면 신궁
- 궁간 오호둔(인수 정하기) + 간지 수치로 오행국 정하기
  (갑을1 병정2 무기3 경신4 임계5 / 자오축미1 인신묘유2 진술사해3,
  합이 5를 넘으면 5를 뺌, 목1 금2 수3 화4 토5에 따라 목3국 금4국 수2국 화6국 토5국)
- 자미성 나누기몫·나머지 구결 + 천부는 자미 대각선 맞춤 + 자미계 거꾸로
  (천기-1, 태양-3, 무곡-4, 천동-5, 염정-8) + 천부계 앞으로
  (태음+1, 탐랑+2, 거문+3, 천상+4, 천량+5, 칠살+6, 파군+10)
- 보조별·잡성 30여 종 + 생년사화(남파/통행본: 무년 과는 우필, 경년 과는 태음,
  임년 과는 좌보) + 대운소운 + 장생박사십이신

입력 시각은 진태양시로 보정하고, 음력은 내장 한국 음력표(1900-2049)로 변환한다.
배치 결과는 iztro 와 대량 대조해 검증했다 (tests/test_ziwei_iztro.py).
윤달은 상반월은 본월·하반월은 다음달 관례. 밤자시(23시 이후)는 다음날 자시 관례.
"""
from __future__ import annotations

from datetime import date, timedelta

from .lunar import solar_to_lunar, birth_moment
from .manseryuk import STEMS_KR, BRANCHES_KR, STEM_ELEMENT, normalize_sex, ZI_MODE

MAIN_STARS = ["자미", "천기", "태양", "무곡", "천동", "염정",
              "천부", "태음", "탐랑", "거문", "천상", "천량", "칠살", "파군"]
PEACH = {"홍란", "천희", "함지", "천요"}

PALACES = ["명궁", "형제", "부처(배우자)", "자녀", "재백", "질액",
           "천이", "노복", "관록", "전택", "복덕", "부모"]

# 오호둔: 연간에서 인궁 천간 정하기
HU_DUN = {0: 2, 5: 2, 1: 4, 6: 4, 2: 6, 7: 6, 3: 8, 8: 8, 4: 0, 9: 0}
# 간지 수치 (오행국 계산용)
STEM_NUM = {0: 1, 1: 1, 2: 2, 3: 2, 4: 3, 5: 3, 6: 4, 7: 4, 8: 5, 9: 5}
BRANCH_NUM = {0: 1, 6: 1, 1: 1, 7: 1, 2: 2, 8: 2, 3: 2, 9: 2,
              4: 3, 10: 3, 5: 3, 11: 3}
GUO_OF = {1: 3, 2: 4, 3: 2, 4: 6, 5: 5}  # 목3국 금4국 수2국 화6국 토5국

# 자미 위치에서 천부 위치 구하기
ZIWEI_TO_TIANFU = {2: 2, 8: 8, 1: 3, 3: 1, 7: 9, 9: 7,
                   0: 4, 4: 0, 5: 11, 11: 5, 6: 10, 10: 6}

# 생년사화 남파/통행본 (연간 → 록·권·과·기)
SIHUA = {
    0: ("염정", "파군", "무곡", "태양"),
    1: ("천기", "천량", "자미", "태음"),
    2: ("천동", "천기", "문창", "염정"),
    3: ("태음", "천동", "천기", "거문"),
    4: ("탐랑", "태음", "우필", "천기"),
    5: ("무곡", "탐랑", "천량", "문곡"),
    6: ("태양", "무곡", "태음", "천동"),
    7: ("거문", "태양", "문곡", "문창"),
    8: ("천량", "자미", "좌보", "무곡"),
    9: ("파군", "거문", "태음", "탐랑"),
}
HUA_NAME = {"록": "화록", "권": "화권", "과": "화과", "기": "화기"}

# 녹존 (연간 → 지지)
LU_CUN = {0: 2, 1: 3, 2: 5, 4: 5, 3: 6, 5: 6, 6: 8, 7: 9, 8: 11, 9: 0}
# 천괴/천월 (연간 → (괴성, 월성)). 갑무경은 축미, 을기는 자신, 병정은 해유,
# 신은 오인, 임계는 묘사. 예전엔 무(4)가 빠지고 기(5)가 축미로 잘못 들어가
# 무년생은 명반 계산이 통째로 죽었다.
KUI_YUE = {0: (1, 7), 4: (1, 7), 6: (1, 7), 1: (0, 8), 5: (0, 8),
           2: (11, 9), 3: (11, 9), 7: (6, 2), 8: (3, 5), 9: (3, 5)}
# 천마·함지·화개·고진과숙·화성영성 (연지 삼합 그룹)
TRIOS = [(8, 0, 4), (2, 6, 10), (5, 9, 1), (11, 3, 7)]
MA_AT = {(8, 0, 4): 2, (2, 6, 10): 8, (5, 9, 1): 11, (11, 3, 7): 5}
XIANCHI_AT = {(8, 0, 4): 9, (2, 6, 10): 3, (5, 9, 1): 6, (11, 3, 7): 0}
HUAGAI_AT = {(8, 0, 4): 4, (2, 6, 10): 10, (5, 9, 1): 1, (11, 3, 7): 7}
GUCHEN_AT = {(2, 3, 4): (5, 1), (5, 6, 7): (8, 4),
             (8, 9, 10): (11, 7), (11, 0, 1): (2, 10)}
# (legacy table, actual lookup uses _guchen_of)
HUOLING_AT = {(2, 6, 10): (1, 3), (8, 0, 4): (2, 10),
              (5, 9, 1): (3, 10), (11, 3, 7): (9, 10)}
# 절공 (연간)
JIEKONG = {0: (8, 9), 5: (8, 9), 1: (6, 7), 6: (6, 7), 2: (4, 5),
           7: (4, 5), 3: (2, 3), 8: (2, 3), 4: (0, 1), 9: (0, 1)}
# 명주는 명궁 지지로, 신주는 태어난 해의 지지로 정한다
MINGZHU = {0: "탐랑", 1: "거문", 11: "거문", 2: "녹존", 10: "녹존",
           3: "문곡", 9: "문곡", 5: "무곡", 7: "무곡",
           4: "염정", 8: "염정", 6: "파군"}
SHENZHU = {0: "화성", 6: "화성", 1: "천상", 7: "천상", 2: "천량",
           8: "천량", 3: "천동", 9: "천동", 5: "천기", 11: "천기",
           4: "문창", 10: "문창"}
# 소운 시작궁 (연지 그룹 → 1세궁)
XIAOXIAN_AT = {(2, 6, 10): 4, (8, 0, 4): 10, (5, 9, 1): 7, (11, 3, 7): 1}
# 장생십이신 시작 위치 (국 → 장생궁)
CHANGSHENG_AT = {2: 8, 3: 11, 4: 5, 5: 8, 6: 2}
CHANGSHENG = ["장생", "목욕", "관대", "건록", "제왕", "쇠",
              "병", "사", "묘", "절", "태", "양"]
BOSHI = ["박사", "역사", "청룡", "소모", "장군", "주서",
         "비렴", "희신", "병부", "대모", "복병", "관부"]


def _trio_of(branch: int):
    for trio in TRIOS:
        if branch in trio:
            return trio
    raise RuntimeError("삼합 판정 실패")


def _guchen_of(yb: int) -> tuple[int, int]:
    if yb in (2, 3, 4):
        return (5, 1)
    if yb in (5, 6, 7):
        return (8, 4)
    if yb in (8, 9, 10):
        return (11, 7)
    return (2, 10)


def ziwei_position(lunar_day: int, guo: int) -> int:
    """자미성 자리 (지지 번호, 자=0).

    생일에 가장 작은 수 x 를 더해 국수로 나누어떨어지게 한다. 몫 q 만큼
    인궁에서 세어 간 자리에서, x 가 홀수면 x 칸 거꾸로, 짝수면 x 칸 앞으로 간다.
    예전엔 단순 나눗셈으로 정해서 국·생일 150가지 중 107가지가 틀렸다
    (자미가 틀리면 주성 14개가 전부 틀린다).
    """
    x = 0
    while (lunar_day + x) % guo:
        x += 1
    q = (lunar_day + x) // guo
    pos = 2 + q - 1
    pos = pos - x if x % 2 else pos + x
    return pos % 12


def ziwei_chart(birth: date, hour: int | None = 12, minute: int = 0,
                sex: str = "male", city: str = "서울",
                today: date | None = None) -> dict | None:
    """정통 자미두수 명반. hour None이면 시지 배치 불가라 None.

    today 는 소운·유년을 볼 기준일이다 (리포트 기준일을 넘긴다).
    """
    if hour is None:
        return None
    sex = normalize_sex(sex)
    today = today or date.today()
    bm = birth_moment(birth.year, birth.month, birth.day, hour, minute, city)
    true_dt, corr_min, city_ok = bm["true_solar"], bm["corr_min"], bm["city_ok"]
    eff_date = true_dt.date()
    night_zi = False
    if true_dt.hour >= 23:
        night_zi = True
        if ZI_MODE.get() != "split":     # 야자시면 음력 날짜는 그날 그대로 (iztro 의 늦은 자시와 같다)
            eff_date = eff_date + timedelta(days=1)
    hb = ((true_dt.hour + 1) // 2) % 12  # 자시=0

    ly, lm, ld, is_leap = solar_to_lunar(eff_date.year, eff_date.month, eff_date.day)
    chart = chart_from_lunar(ly, lm, ld, is_leap, hb, sex, today)
    chart.update({
        "true_solar": true_dt.strftime("%m-%d %H:%M"),
        "corr_min": round(corr_min, 1), "city_ok": city_ok,
        "night_zi": night_zi,
    })
    return chart


def chart_from_lunar(ly: int, lm: int, ld: int, is_leap: bool, hb: int,
                     sex: str = "male", today: date | None = None) -> dict:
    """음력 생년월일 + 시지(자=0)로 명반을 배치한다. 시각 보정은 부르는 쪽 몫이다."""
    sex = normalize_sex(sex)
    today = today or date.today()
    m_eff = lm + (1 if (is_leap and ld > 15) else 0)
    if m_eff == 13:
        m_eff = 1  # 윤십이월 하반은 다음달(정월) 관례

    ys, yb = (ly - 4) % 10, (ly - 4) % 12  # 음력 연간지

    # 명궁·신궁
    month_palace = (2 + (m_eff - 1)) % 12
    mingong = (month_palace - hb) % 12
    shengong = (month_palace + hb) % 12

    # 십이궁 + 궁간
    palaces: list[dict] = []
    first_stem = HU_DUN[ys]
    for i in range(12):
        b = (mingong - i) % 12
        palaces.append({
            "branch": b, "branch_kr": BRANCHES_KR[b],
            # 인궁부터 해궁까지 차례로 붙이고, 자궁·축궁은 해궁 다음으로 이어 센다.
            # 예전엔 자·축을 거꾸로 두 칸 앞 천간으로 붙여서, 명궁이 자·축이면
            # 오행국부터 주성까지 줄줄이 틀렸다.
            "stem": (first_stem + (b - 2) % 12) % 10,
            "name": PALACES[i], "stars": [], "hua": {},
            "daxian": None, "xiaoxian": False, "liunian": False,
        })
    for p in palaces:
        p["stem_kr"] = STEMS_KR[p["stem"]]

    # 오행국 (명궁 간지 수치로 정하기)
    ming_ganzhi_stem = next(p["stem"] for p in palaces if p["name"] == "명궁")
    total = STEM_NUM[ming_ganzhi_stem] + BRANCH_NUM[mingong]
    if total > 5:
        total -= 5
    guo = GUO_OF[total]

    # 자미성 정하기
    ziwei = ziwei_position(ld, guo)
    tianfu = ZIWEI_TO_TIANFU[ziwei]

    def at(base: int, off: int) -> int:
        return (base + off) % 12

    stars_at: dict[int, list[str]] = {i: [] for i in range(12)}
    SERIES_ZIWEI = {"자미": 0, "천기": -1, "태양": -3, "무곡": -4, "천동": -5, "염정": -8}
    for name, off in SERIES_ZIWEI.items():
        stars_at[at(ziwei, off)].append(name)
    SERIES_TIANFU = {"천부": 0, "태음": 1, "탐랑": 2, "거문": 3,
                     "천상": 4, "천량": 5, "칠살": 6, "파군": 10}
    for name, off in SERIES_TIANFU.items():
        stars_at[at(tianfu, off)].append(name)

    # 보조별 배치
    zuofu = (4 + (m_eff - 1)) % 12
    youbi = (10 - (m_eff - 1)) % 12
    stars_at[zuofu].append("좌보")
    stars_at[youbi].append("우필")
    wenqu = (4 + hb) % 12
    wenchang = (10 - hb) % 12
    stars_at[wenqu].append("문곡")
    stars_at[wenchang].append("문창")
    stars_at[(11 + hb) % 12].append("지겁")
    stars_at[(11 - hb) % 12].append("지공")
    kui, yue = KUI_YUE[ys]
    stars_at[kui].append("천괴")
    stars_at[yue].append("천월")
    lucun = LU_CUN[ys]
    stars_at[lucun].append("녹존")
    stars_at[(lucun + 1) % 12].append("경양")
    stars_at[(lucun - 1) % 12].append("타라")
    trio = _trio_of(yb)
    stars_at[MA_AT[trio]].append("천마")
    fire0, ling0 = HUOLING_AT[trio]
    stars_at[(fire0 + hb) % 12].append("화성")
    stars_at[(ling0 + hb) % 12].append("영성")
    hongluan = (3 - yb) % 12
    stars_at[hongluan].append("홍란")
    stars_at[(hongluan + 6) % 12].append("천희")
    stars_at[XIANCHI_AT[trio]].append("함지")
    stars_at[(1 + m_eff - 1) % 12].append("천요")
    stars_at[(9 + m_eff - 1) % 12].append("천형")
    stars_at[HUAGAI_AT[trio]].append("화개")
    guchen, guaxiu = _guchen_of(yb)
    stars_at[guchen].append("고진")
    stars_at[guaxiu].append("과숙")
    stars_at[(6 + hb) % 12].append("대보")
    stars_at[(2 + hb) % 12].append("봉고")   # 인궁에서 자시부터 앞으로 센다
    stars_at[(mingong + yb) % 12].append("천재")
    stars_at[(shengong + yb) % 12].append("천수")
    stars_at[(zuofu + ld - 1) % 12].append("삼태")
    stars_at[(youbi - (ld - 1)) % 12].append("팔좌")
    stars_at[(wenchang + ld - 2) % 12].append("은광")
    stars_at[(wenqu + ld - 2) % 12].append("천귀")
    stars_at[(yb + 1) % 12].append("천공")
    stars_at[(6 - yb) % 12].append("천곡")
    stars_at[(6 + yb) % 12].append("천허")
    stars_at[(4 + yb) % 12].append("용지")
    stars_at[(10 - yb) % 12].append("봉각")
    for jk in JIEKONG[ys]:
        stars_at[jk].append("절공")

    # 생년사화 붙이기
    hua_lu, hua_quan, hua_ke, hua_ji = SIHUA[ys]
    hua_map = {"록": hua_lu, "권": hua_quan, "과": hua_ke, "기": hua_ji}
    by_branch = {p["branch"]: p for p in palaces}
    for hua, star in hua_map.items():
        for b, names in stars_at.items():
            if star in names:
                by_branch[b]["hua"][star] = hua
                break

    for p in palaces:
        p["stars"] = stars_at[p["branch"]]

    # 대운 (국수 나이에 시작, 양남음녀 순행). 수2국이면 2~11세가 첫 대운이다.
    # 예전엔 국수+5 로 5년씩 밀려 있었다.
    yang_year = (ys % 2 == 0)
    forward = (yang_year and sex == "male") or (not yang_year and sex == "female")
    start_age = guo
    for k in range(12):
        b = (mingong + k) % 12 if forward else (mingong - k) % 12
        by_branch[b]["daxian"] = (start_age + 10 * k, start_age + 10 * k + 9)

    # 소운 (연지 그룹 시작궁, 남자는 순행·여자는 역행, 1세 시작)
    xiao_start = XIAOXIAN_AT[trio]
    # 기준일의 음력년과 세는나이. 자미두수는 한 해를 음력 설로 나눈다.
    t_ly = solar_to_lunar(today.year, today.month, today.day)[0]
    xusui = t_ly - ly + 1
    xiao_b = (xiao_start + (xusui - 1)) % 12 if sex == "male" \
        else (xiao_start - (xusui - 1)) % 12
    by_branch[xiao_b]["xiaoxian"] = True

    # 유년명궁 + 유년사화. 천간과 지지를 같은 해(기준일의 음력년)에서 뽑는다.
    # 예전엔 지지는 양력 연도, 천간은 입춘으로 따로 정해서 1월~입춘 사이에는
    # 있을 수 없는 간지 조합이 나왔다.
    ly_now_branch = (t_ly - 4) % 12
    liunian_stem = (t_ly - 4) % 10
    by_branch[ly_now_branch]["liunian"] = True
    ln_lu, ln_quan, ln_ke, ln_ji = SIHUA[liunian_stem]

    # 장생십이신
    cs_start = CHANGSHENG_AT[guo]
    changsheng_at = {}
    for k, name in enumerate(CHANGSHENG):
        b = (cs_start + k) % 12 if forward else (cs_start - k) % 12
        changsheng_at[b] = name
    # 박사십이신 (녹존궁 시작)
    boshi_at = {}
    for k, name in enumerate(BOSHI):
        b = (lucun + k) % 12 if forward else (lucun - k) % 12
        boshi_at[b] = name

    spouse_b = (mingong - 2) % 12
    spouse_stars = stars_at[spouse_b]
    spouse_main = next((s for s in spouse_stars if s in MAIN_STARS), "")
    spouse_borrowed = ""
    if not spouse_main:
        opp = (spouse_b + 6) % 12
        spouse_borrowed = next((s for s in stars_at[opp] if s in MAIN_STARS), "")
        spouse_main = spouse_borrowed
    ming_main = next((s for s in stars_at[mingong] if s in MAIN_STARS), "")
    ming_borrowed = ""
    if not ming_main:
        # 무주성이면 맞은편 궁(천이궁)의 주성을 빌려 읽는다 (차성안궁)
        ming_borrowed = next((s for s in stars_at[(mingong + 6) % 12] if s in MAIN_STARS), "")
        ming_main = ming_borrowed

    peach = sorted({s for s in spouse_stars + stars_at[mingong] if s in PEACH})

    return {
        "method": "자미두수 정통 명반(전통 배성 구결 그대로 계산)",
        "lunar": (ly, lm, ld, is_leap),
        "lunar_year_stem": ys, "lunar_year_branch": yb,
        "hour_branch": BRANCHES_KR[hb],
        "mingong": BRANCHES_KR[mingong], "shengong": BRANCHES_KR[shengong],
        "mingong_branch": mingong, "shengong_branch": shengong,
        "guo": guo, "ming_main": ming_main, "ming_borrowed": ming_borrowed,
        "spouse_branch": spouse_b, "spouse_stars": spouse_stars,
        "spouse_main": spouse_main, "spouse_borrowed": spouse_borrowed,
        "peach": peach,
        "palaces": palaces,
        "sihua": {"록": hua_lu, "권": hua_quan, "과": hua_ke, "기": hua_ji},
        "sihua_year_stem": STEMS_KR[ys],
        "liunian": {"branch": BRANCHES_KR[ly_now_branch],
                    "stem": STEMS_KR[liunian_stem],
                    "sihua": {"록": ln_lu, "권": ln_quan, "과": ln_ke, "기": ln_ji}},
        "mingzhu": MINGZHU[mingong], "shenzhu": SHENZHU[yb],
        "daxian_forward": forward, "daxian_start": start_age,
        "xusui": xusui, "xiao_branch": BRANCHES_KR[xiao_b],
        "changsheng_at": {BRANCHES_KR[b]: n for b, n in changsheng_at.items()},
        "boshi_at": {BRANCHES_KR[b]: n for b, n in boshi_at.items()},
        "year_animal": ["쥐", "소", "호랑이", "토끼", "용", "뱀",
                        "말", "양", "원숭이", "닭", "개", "돼지"][yb],
    }
