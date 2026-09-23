"""manseryuk.py, 사주 4기둥 정통 계산 (외부 의존성 없음).

- 년주: 입춘(태양황경 315도, 실측) 경계
- 월주: 12절 실측 + 오호둔(연간으로 인월 천간 정하기)
- 일주: 기준일 1900-01-01 = 갑술일
- 시주: 진태양시 + 오서둔, 밤자시(23시 이후)는 다음날 자시
- 대운: 양남음녀 순행/음남양녀 역행, 절기까지 일수/3 = 대운 시작 나이
- 신살: 천을귀인, 역마, 화개, 공망, 장성, 괴강, 고진과숙
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from .astronomy import solar_term_moment, month_branch_exact, JIE_LON
from .lunar import true_solar_time

STEMS_KR = ["갑", "을", "병", "정", "무", "기", "경", "신", "임", "계"]
BRANCHES_KR = ["자", "축", "인", "묘", "진", "사", "오", "미", "신", "유", "술", "해"]

STEM_ELEMENT = {
    0: "목", 1: "목", 2: "화", 3: "화", 4: "토",
    5: "토", 6: "금", 7: "금", 8: "수", 9: "수",
}
BRANCH_ELEMENT = {
    0: "수", 1: "토", 2: "목", 3: "목", 4: "토", 5: "화",
    6: "화", 7: "토", 8: "금", 9: "금", 10: "토", 11: "수",
}
ZODIAC_ANIMALS = ["쥐", "소", "호랑이", "토끼", "용", "뱀",
                  "말", "양", "원숭이", "닭", "개", "돼지"]

_ANCHOR = date(1900, 1, 1)
_ANCHOR_STEM = 0
_ANCHOR_BRANCH = 10

# 천을귀인 (일간 → (밝을 때 귀인, 밤 귀인))
TIANYI = {0: (1, 7), 4: (1, 7), 6: (1, 7), 1: (0, 8), 5: (0, 8),
          2: (11, 9), 3: (11, 9), 7: (6, 2), 8: (3, 5), 9: (3, 5)}
# 역마·화개·장성 (일지 삼합 그룹)
TRIOS = [(8, 0, 4), (2, 6, 10), (5, 9, 1), (11, 3, 7)]
YIMA_AT = {(8, 0, 4): 2, (2, 6, 10): 8, (5, 9, 1): 11, (11, 3, 7): 5}
HUAGAI_AT = {(8, 0, 4): 4, (2, 6, 10): 10, (5, 9, 1): 1, (11, 3, 7): 7}
JIANGXING_AT = {(8, 0, 4): 0, (2, 6, 10): 6, (5, 9, 1): 9, (11, 3, 7): 3}
KONGWANG = [(10, 11), (8, 9), (6, 7), (4, 5), (2, 3), (0, 1)]
KUIGANG = {(6, 4), (6, 10), (8, 4), (4, 10)}  # 경진·경술·임진·무술일
GUCHEN_AT = {(2, 3, 4): (5, 1), (5, 6, 7): (8, 4),
             (8, 9, 10): (11, 7), (11, 0, 1): (2, 10)}


def ganzhi_str(stem: int, branch: int) -> str:
    return f"{STEMS_KR[stem]}{BRANCHES_KR[branch]}"


def _trio_of(b: int):
    for t in TRIOS:
        if b in t:
            return t
    raise RuntimeError("삼합 판정 실패")


def year_pillar(dt: datetime) -> tuple[int, int]:
    """입춘 실측 경계."""
    lichun = solar_term_moment(dt.year, 315.0)
    y = dt.year if dt >= lichun else dt.year - 1
    return ((y - 4) % 10, (y - 4) % 12)


def month_pillar(dt: datetime) -> tuple[int, int]:
    """실측 절기 월지 + 오호둔."""
    branch = month_branch_exact(dt)
    ys, _ = year_pillar(dt)
    first_map = {0: 2, 5: 2, 1: 4, 6: 4, 2: 6, 7: 6, 3: 8, 8: 8, 4: 0, 9: 0}
    first_stem = first_map[ys]
    return ((first_stem + (branch - 2)) % 10, branch)


def day_pillar(d: date) -> tuple[int, int]:
    offset = (d - _ANCHOR).days
    return ((_ANCHOR_STEM + offset) % 10, (_ANCHOR_BRANCH + offset) % 12)


def hour_pillar(day_stem: int, hour: int) -> tuple[int, int]:
    branch = ((hour + 1) // 2) % 12
    base_map = {0: 0, 5: 0, 1: 2, 6: 2, 2: 4, 7: 4, 3: 6, 8: 6, 4: 8, 9: 8}
    return ((base_map[day_stem] + branch) % 10, branch)


def four_pillars(birth: date, hour: int | None = 12, minute: int = 0,
                 city: str = "서울") -> dict:
    """사주 4기둥. 진태양시 보정, 밤자시는 다음날로. hour None이면 시주 제외."""
    _hh = 12 if hour is None else hour
    true_dt, corr, _lon, city_ok = true_solar_time(
        birth.year, birth.month, birth.day, _hh, minute, city)
    eff = true_dt.date()
    night_zi = False
    if true_dt.hour >= 23:
        eff = eff + timedelta(days=1)
        night_zi = True
    ys, yb = year_pillar(true_dt)
    ms, mb = month_pillar(true_dt)
    ds, db = day_pillar(eff)
    if hour is None:
        hs = hb = None
    else:
        hs, hb = hour_pillar(ds, true_dt.hour)
    pillars = {"year": (ys, yb), "month": (ms, mb),
               "day": (ds, db), "hour": (hs, hb)}
    strings = {k: ganzhi_str(s, b) for k, (s, b) in pillars.items()
               if s is not None and b is not None}
    if hour is None:
        strings["hour"] = "시간 미상"
    return {
        "pillars": pillars,
        "strings": strings,
        "hour_unknown": hour is None,
        "ilgan": STEMS_KR[ds],
        "ilgan_stem": ds,
        "ilgan_element": STEM_ELEMENT[ds],
        "day_branch": db,
        "year_animal": ZODIAC_ANIMALS[yb],
        "true_solar": true_dt.strftime("%m-%d %H:%M"),
        "corr_min": round(corr, 1),
        "city_ok": city_ok,
        "night_zi": night_zi,
    }


def dayun(birth: date, hour: int | None, minute: int, sex: str,
          city: str = "서울") -> dict:
    """대운: 대운 시작 나이 + 8스텝 간지 + 현재 대운. hour None이면 정오 기준 어림."""
    natal = four_pillars(birth, hour, minute, city)
    ys = natal["pillars"]["year"][0]
    ms, mb = natal["pillars"]["month"]
    _hh = 12 if hour is None else hour
    true_dt = datetime(birth.year, birth.month, birth.day, _hh, minute)
    yang_year = (ys % 2 == 0)
    shun = (yang_year and sex == "male") or (not yang_year and sex == "female")
    # 가장 가까운 절기 탐색
    cands = []
    for yy in (birth.year - 1, birth.year, birth.year + 1):
        for lon in JIE_LON.values():
            try:
                cands.append(solar_term_moment(yy, lon))
            except RuntimeError:
                pass
    past = [c for c in cands if c <= true_dt]
    future = [c for c in cands if c > true_dt]
    if shun:
        ref = min(future)
        days = (ref - true_dt).total_seconds() / 86400.0
    else:
        ref = max(past)
        days = (true_dt - ref).total_seconds() / 86400.0
    start_age = round(days / 3.0, 1)
    steps = []
    for k in range(1, 9):
        if shun:
            s = (ms + k) % 10
            b = (mb + k) % 12
        else:
            s = (ms - k) % 10
            b = (mb - k) % 12
        steps.append({"ganzhi": ganzhi_str(s, b),
                      "from": round(start_age + 10 * (k - 1), 1),
                      "to": round(start_age + 10 * k - 0.1, 1)})
    age_now = (date.today() - birth).days / 365.25
    cur = next((st for st in steps
                if st["from"] <= age_now <= st["to"] + 0.1), steps[-1])
    return {"direction": "순행" if shun else "역행",
            "start_age": start_age, "steps": steps, "current": cur,
            "age_now": round(age_now, 1)}


def shensha(birth: date, hour: int = 12, minute: int = 0,
            city: str = "서울") -> dict:
    """주요 신살."""
    natal = four_pillars(birth, hour, minute, city)
    (ys, yb), (_ms, _mb), (ds, db), (_hs, hb) = (
        natal["pillars"][k] for k in ("year", "month", "day", "hour"))
    branches = [yb, _mb, db, hb]
    out: dict[str, str] = {}
    yg, yg2 = TIANYI[ds]
    at = [n for n, b in zip(("년지", "월지", "일지", "시지"), branches)
          if b in (yg, yg2)]
    out["천을귀인"] = (f"{BRANCHES_KR[yg]}·{BRANCHES_KR[yg2]}, "
                       + (f"{', '.join(at)}에 있어 도움·귀인이 따르기 쉬운 구조" if at
                          else "원국에 없어 운에서 들어올 때 도움받는 흐름"))
    trio = _trio_of(db)
    ym = YIMA_AT[trio]
    out["역마"] = (f"{BRANCHES_KR[ym]}, " +
                   ("사주에 있어 이동·변동이 많은 흐름" if ym in branches
                    else "원국에 없어 운에서 들어올 때 이동수가 있는 흐름"))
    hg = HUAGAI_AT[trio]
    out["화개"] = (f"{BRANCHES_KR[hg]}, " +
                   ("사주에 있어 예술·학문·고독한 멋이 있는 흐름" if hg in branches
                    else "내면에 고요한 멋이 있는 흐름"))
    idx60 = next(n for n in range(60) if n % 10 == ds and n % 12 == db)
    kw1, kw2 = KONGWANG[idx60 // 10]
    out["공망"] = f"{BRANCHES_KR[kw1]}·{BRANCHES_KR[kw2]}, 비워둘수록 채워지는 자리"
    jx = JIANGXING_AT[trio]
    out["장성"] = (f"{BRANCHES_KR[jx]}, " +
                   ("사주에 있어 이끄는 힘이 있는 흐름" if jx in branches
                    else "리더십은 운에서 발휘되는 흐름"))
    out["괴강"] = ("일주가 괴강(경진·경술·임진·무술)으로 결단력이 강한 흐름"
                   if (ds, db) in KUIGANG else "괴강 아님, 부드럽게 밀어붙이는 흐름")
    for grp, (gc, gx) in GUCHEN_AT.items():
        if yb in grp:
            out["고진과숙"] = (f"고진 {BRANCHES_KR[gc]}·과숙 {BRANCHES_KR[gx]}, "
                               "혼자만의 시간이 필요한 흐름")
            break
    return out
