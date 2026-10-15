"""almanac.py, 한국 택일 달력 (오늘이 어떤 날인지). 규칙 계산, 무의존·결정적.

넣은 것 (출처를 둘 이상 대조해 맞는 것만):
- 손 없는 날: 음력 날짜 끝자리 9·0 (한국 관행, 손없는날 달력 여러 곳과 같다)
- 월기일: 음력 5·14·23일 (한국 이사·결혼 택일에서 꺼리는 날)
- 건제12신: 월건(절기 기준 월지)과 일지의 차이로 정한다. 길흉 분류는 한국 자료 기준
  (길: 제·위·정·집·성·개 / 흉: 건·파·평·수·만·폐). lunar-python 표 144칸과 전부 일치
- 황도·흑도 12신: 월지에 따라 청룡이 서는 자리부터 차례로. lunar-python 표 144칸과 전부 일치
- 28수: 날마다 하나씩 도는 이름만 보여 준다. 한국 기준 길흉 자료를 확인하지 못해
  길흉 판단에는 쓰지 않는다
- 생기복덕(천기대요): 세는나이·성별로 정한 궁에서 괘를 바꿔 가며 여덟 가지 날을 정한다.
  궁합닷컴 조견표 128칸과 전부 일치
- 올해 삼살·대장군 방위: 연지 삼합·방합 기준 (이사 방위)

뺀 것: lunar-python 의 날짜별 '좋은 일/피할 일' 목록은 중국 통서 방식이라 한국
택일(천기대요) 관행과 달라서 쓰지 않는다.
"""
from __future__ import annotations

from .josa import j

from datetime import date, datetime

from .astronomy import JIE_BRANCH, JIE_LON, solar_term_moment
from .lunar import solar_to_lunar
from .manseryuk import BRANCHES_KR, ZODIAC_ANIMALS, day_pillar, year_pillar, ganzhi_str

OFFICERS = ["건", "제", "만", "평", "정", "집", "파", "위", "성", "수", "개", "폐"]
OFFICER_GOOD = {"제", "위", "정", "집", "성", "개"}
SPIRITS = ["청룡", "명당", "천형", "주작", "금궤", "천덕", "백호", "옥당", "천뢰", "현무", "사명", "구진"]
SPIRIT_YELLOW = {"청룡", "명당", "금궤", "천덕", "옥당", "사명"}          # 황도
# 월지별 청룡이 서는 일지 (자·오월은 신일부터 ...)
_QINGLONG_AT = {0: 8, 6: 8, 1: 10, 7: 10, 2: 0, 8: 0, 3: 2, 9: 2, 4: 4, 10: 4, 5: 6, 11: 6}
MANSIONS = ["각", "항", "저", "방", "심", "미", "기", "두", "우", "녀", "허", "위", "실", "벽",
            "규", "루", "위", "묘", "필", "자", "삼", "정", "귀", "류", "성", "장", "익", "진"]
_MANSION_ANCHOR = date(2000, 1, 13)         # 이 날이 각수 (목요일, lunar-python 과 같다)

# 생기복덕 팔괘. 효는 (위, 가운데, 아래) 순서로 양=1
_GUA = {"건": (1, 1, 1), "태": (0, 1, 1), "리": (1, 0, 1), "진": (0, 0, 1),
        "손": (1, 1, 0), "감": (0, 1, 0), "간": (1, 0, 0), "곤": (0, 0, 0)}
_GUA_OF = {v: k for k, v in _GUA.items()}
_GUA_BRANCHES = {"건": (10, 11), "감": (0,), "간": (1, 2), "진": (3,),
                 "손": (4, 5), "리": (6,), "곤": (7, 8), "태": (9,)}
# 괘를 바꾸는 순서: 상·중·하·중·상·중·하·중 → 생기·천의·절체·유혼·화해·복덕·절명·귀혼
_CHANGES = [0, 1, 2, 1, 0, 1, 2, 1]
SAENGGI_NAMES = ["생기", "천의", "절체", "유혼", "화해", "복덕", "절명", "귀혼"]
SAENGGI_GOOD = {"생기", "천의", "복덕"}
SAENGGI_BAD = {"화해", "절명"}
# 8세부터 도는 궁 순서. 남자는 1세 리궁, 2~7세는 곤궁을 건너뛴다.
# 여자는 1~7세가 8~14세와 같고 간궁은 15세에 처음 나온다.
_MALE_CYCLE = ["리", "곤", "태", "건", "감", "간", "진", "손"]
_FEMALE_CYCLE = ["감", "건", "태", "곤", "리", "손", "진", "간"]


def month_branch_of_day(d: date) -> int:
    """택일에서 쓰는 그날의 월건. 절기가 든 날(한국 표준시)부터 그 달로 본다."""
    last = None
    for y in (d.year - 1, d.year):
        for lon in JIE_LON.values():
            t = solar_term_moment(y, lon)
            if t.date() <= d and (last is None or t > last[0]):
                last = (t, lon)
    return JIE_BRANCH[list(JIE_LON.values()).index(last[1])]


def officer(d: date) -> str:
    """건제12신."""
    return OFFICERS[(day_pillar(d)[1] - month_branch_of_day(d)) % 12]


def heaven_spirit(d: date) -> str:
    """황도·흑도 12신."""
    return SPIRITS[(day_pillar(d)[1] - _QINGLONG_AT[month_branch_of_day(d)]) % 12]


def mansion(d: date) -> str:
    """28수 (이름만)."""
    return MANSIONS[(d - _MANSION_ANCHOR).days % 28]


def saenggi_palace(age: int, sex: str) -> str:
    """세는나이·성별로 생기복덕을 볼 궁."""
    if sex == "male":
        return "리" if age == 1 else _MALE_CYCLE[age % 8] if age < 8 else _MALE_CYCLE[(age - 8) % 8]
    return _FEMALE_CYCLE[(age - 1) % 8] if age < 8 else _FEMALE_CYCLE[(age - 8) % 8]


def saenggi_table(age: int, sex: str) -> dict[str, tuple[int, ...]]:
    """{생기: (지지들), 천의: ..., ...}."""
    lines = list(_GUA[saenggi_palace(age, sex)])
    out = {}
    for name, pos in zip(SAENGGI_NAMES, _CHANGES):
        lines[pos] ^= 1
        out[name] = _GUA_BRANCHES[_GUA_OF[tuple(lines)]]
    return out


def saenggi_of_day(d: date, age: int, sex: str) -> str:
    db = day_pillar(d)[1]
    return next(n for n, bs in saenggi_table(age, sex).items() if db in bs)


def year_directions(d: date) -> dict[str, str]:
    """올해 이사·공사에서 꺼리는 방위 (삼살·대장군). 해는 입춘으로 가른다."""
    yb = year_pillar(datetime(d.year, d.month, d.day, 12))[1]
    samsal = {8: "남", 0: "남", 4: "남", 2: "북", 6: "북", 10: "북",
              5: "동", 9: "동", 1: "동", 11: "서", 3: "서", 7: "서"}[yb]
    daejang = {11: "서", 0: "서", 1: "서", 2: "북", 3: "북", 4: "북",
               5: "동", 6: "동", 7: "동", 8: "남", 9: "남", 10: "남"}[yb]
    return {"삼살": samsal, "대장군": daejang}


def day_info(d: date, birth: date | None = None, sex: str | None = None,
             birth_branches: list[int] | None = None) -> dict:
    """그날의 택일 정보. birth·sex 가 있으면 생기복덕과 띠 충까지 본다."""
    ly, lm, ld, leap = solar_to_lunar(d.year, d.month, d.day)
    ds, db = day_pillar(d)
    info = {
        "date": d.isoformat(), "iljin": ganzhi_str(ds, db),
        "lunar": (ly, lm, ld, leap),
        "son_eomneun": ld % 10 in (9, 0),
        "wolgi": ld in (5, 14, 23),
        "officer": officer(d), "spirit": heaven_spirit(d), "mansion": mansion(d),
        "clash_animal": ZODIAC_ANIMALS[(db + 6) % 12],
        "directions": year_directions(d),
    }
    info["officer_good"] = info["officer"] in OFFICER_GOOD
    info["spirit_yellow"] = info["spirit"] in SPIRIT_YELLOW
    if birth is not None and sex in ("male", "female"):
        age = d.year - birth.year + 1
        info["age"] = age
        info["saenggi"] = saenggi_of_day(d, age, sex)
    if birth_branches:
        info["clash_me"] = [BRANCHES_KR[b] for b in birth_branches if (b + 6) % 12 == db]
    return info


def day_luck_points(info: dict) -> tuple[int, list[str]]:
    """택일 정보를 점수 가감과 근거 문장으로. 점수 폭은 작게 둔다 (보조 지표)."""
    pts, why = 0, []
    if "saenggi" in info:
        s = info["saenggi"]
        if s in SAENGGI_GOOD:
            pts += 4
            why.append(f"오늘은 나에게 {s}일(생기복덕으로 본 좋은 날)이라 일을 벌이기 좋은 흐름")
        elif s in SAENGGI_BAD:
            pts -= 4
            why.append(f"오늘은 나에게 {s}일(생기복덕으로 본 꺼리는 날)이라 큰 결정은 미루는 게 좋은 흐름")
    if info["spirit_yellow"]:
        pts += 2
        why.append(f"{info['spirit']} 황도일(하늘이 돕는다고 보는 날)")
    else:
        pts -= 1
        why.append(f"{info['spirit']} 흑도일(조심해서 움직이면 좋은 날)")
    if info["officer_good"]:
        pts += 1
    else:
        pts -= 1
    if info.get("clash_me"):
        pts -= 2
        why.append(f"오늘 일진이 내 사주의 {j(', '.join(info['clash_me']), '와')} 정면으로 부딪쳐(충) 확인을 한 번 더 하면 좋은 날")
    return pts, why


def age_on(d: date, birth: date) -> int:
    """세는나이 (그해 연도 기준)."""
    return d.year - birth.year + 1


__all__ = ["day_info", "day_luck_points", "officer", "heaven_spirit", "mansion",
           "saenggi_table", "saenggi_of_day", "month_branch_of_day", "year_directions", "age_on"]
