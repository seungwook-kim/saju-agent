"""manseryuk.py, 사주 4기둥 정통 계산 (외부 의존성 없음).

- 년주: 입춘(태양황경 315도, 실측) 경계
- 월주: 12절 실측 + 오호둔(연간으로 인월 천간 정하기)
  년주·월주는 출생 '순간'(세계시)을 절입 순간과 비교한다. 절기는 온 세상에서
  같은 순간에 들어오기 때문이다. 예전엔 진태양시를 한국 표준시처럼 비교해서
  절입 직후 30분 안팎에 태어난 사람의 년주·월주가 바뀌었다.
- 일주: 기준일 1900-01-01 = 갑술일, 날짜 경계는 진태양시
- 시주: 진태양시 + 오서둔, 밤자시(23시 이후)는 다음날 자시
- 출생 시각은 그때 그 지역의 표준시·서머타임을 반영해 세계시로 바꾼다 (lunar.birth_moment)
- 대운: 양남음녀 순행/음남양녀 역행, 절기까지 일수/3 = 대운 시작 나이
- 신살: 천을귀인, 역마, 화개, 공망, 장성, 괴강, 고진과숙
"""
from __future__ import annotations

import contextvars
from contextlib import contextmanager
from datetime import date, datetime, timedelta

from .astronomy import solar_term_moment, month_branch_exact, JIE_LON
from .lunar import birth_moment

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


# 밤 11시~12시(진태양시) 출생을 어떻게 볼지. 명리학계에서도 결론이 나지 않은 문제라
# 전문 사이트마다 다르다 (2026-09 조사: 사주만세는 야자시, 정해 만세력은 23시에 다음날).
#   "next"  : 23시부터 다음날로 본다 (정자시설, 기본)
#   "split" : 일주는 그날 그대로, 시주만 다음날 자시로 본다 (야자시설)
# 요청마다 부르는 쪽(cli·web)이 zi_mode() 로 정한다. 스레드·요청끼리 섞이지 않는다.
ZI_MODE: contextvars.ContextVar[str] = contextvars.ContextVar("zi_mode", default="next")
ZI_MODES = {"next": "밤 11시부터 다음날로 보기 (정자시)",
            "split": "일주는 그날 두고 시주만 다음날 자시로 보기 (야자시)"}


@contextmanager
def zi_mode(mode: str | None):
    mode = mode if mode in ZI_MODES else "next"
    token = ZI_MODE.set(mode)
    try:
        yield mode
    finally:
        ZI_MODE.reset(token)


def normalize_sex(sex: str | None) -> str:
    """성별 입력을 'male'/'female' 로. 알아볼 수 없으면 ValueError.

    예전엔 검사가 없어서 '여' 라고 넣으면 남자로 계산됐다 (대운 방향이 뒤집힌다).
    """
    v = str(sex or "").strip().lower()
    if v in ("male", "m", "man", "남", "남자", "남성"):
        return "male"
    if v in ("female", "f", "woman", "여", "여자", "여성"):
        return "female"
    raise ValueError(f"성별은 남/여(male/female)로 입력해 줘 (입력: {sex!r})")


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
    # 인월부터 차례로 붙이고, 자월·축월은 해월 다음으로 이어 센다 (갑년이면 병자·정축).
    # 예전엔 자·축을 거꾸로 두 칸 앞 천간으로 붙여서, 12월 초~2월 초 출생자(약 16%)의
    # 월주 천간이 틀렸다 (lunar-python 대조로 확인).
    return ((first_stem + (branch - 2) % 12) % 10, branch)


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
    bm = birth_moment(birth.year, birth.month, birth.day, _hh, minute, city)
    true_dt, corr = bm["true_solar"], bm["corr_min"]
    eff = true_dt.date()
    night_zi = False
    split = False
    if true_dt.hour >= 23 and hour is not None:
        night_zi = True
        if ZI_MODE.get() == "split":
            split = True                 # 야자시: 일주는 그날 그대로
        else:
            eff = eff + timedelta(days=1)
    ys, yb = year_pillar(bm["kst"])
    ms, mb = month_pillar(bm["kst"])
    ds, db = day_pillar(eff)
    if hour is None:
        hs = hb = None
    else:
        # 야자시면 시주 천간은 다음날 일간 기준의 자시로 붙인다
        base = day_pillar(eff + timedelta(days=1))[0] if split else ds
        hs, hb = hour_pillar(base, true_dt.hour)
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
        "city_ok": bm["city_ok"],
        "city_name": bm["city_name"],
        "dst": bm["dst"],
        "offset_h": bm["offset_h"],
        "zone": bm["zone"],
        "night_zi": night_zi,
        "zi_mode": ZI_MODE.get(),
    }


def _fmt_offset(h: float) -> str:
    sign = "+" if h >= 0 else "-"
    m = round(abs(h) * 60)
    return f"UTC{sign}{m // 60}" + (f":{m % 60:02d}" if m % 60 else "")


def time_notes(natal: dict) -> list[str]:
    """출생 시각을 어떻게 보정했는지 사람 말로. 도시 이름·날짜는 넣지 않는다."""
    if natal.get("hour_unknown"):
        return []
    notes = []
    zone, off = natal.get("zone", "Asia/Seoul"), natal.get("offset_h", 9.0)
    if natal.get("dst"):
        notes.append(f"태어난 때가 서머타임 기간이라 시계를 한 시간 되돌려 계산했어 ({_fmt_offset(off)})")
    elif zone in ("Asia/Seoul", "Asia/Pyongyang") and abs(off - 9.0) > 1e-9:
        notes.append(f"그때 한국 표준시는 {_fmt_offset(off)} 였어서 그 기준으로 계산했어")
    elif zone not in ("Asia/Seoul", "Asia/Pyongyang"):
        notes.append(f"현지 표준시 {_fmt_offset(off)} 기준으로 계산했어")
    if natal.get("night_zi"):
        notes.append("밤 11시대 출생이라 "
                     + ("일주는 그날로 두고 시주만 다음날 자시로 봤어 (야자시 기준)"
                        if natal.get("zi_mode") == "split"
                        else "다음날 일주로 봤어 (정자시 기준). 야자시로 보려면 기준을 바꿔 봐"))
    if not natal.get("city_ok", True):
        notes.append("태어난 도시를 목록에서 찾지 못해 남한 중앙 경도로 어림했어. "
                     "가까운 큰 도시 이름을 넣으면 시주가 더 정확해져")
    return notes


def dayun(birth: date, hour: int | None, minute: int, sex: str,
          city: str = "서울", today: date | None = None) -> dict:
    """대운: 대운 시작 나이 + 8스텝 간지 + 현재 대운. hour None이면 정오 기준 어림.

    today 는 '현재 대운' 을 고르는 기준일이다 (리포트 기준일을 넘긴다).
    """
    sex = normalize_sex(sex)
    today = today or date.today()
    natal = four_pillars(birth, hour, minute, city)
    ys = natal["pillars"]["year"][0]
    ms, mb = natal["pillars"]["month"]
    _hh = 12 if hour is None else hour
    # 절입 시각(한국 표준시 기준)과 같은 잣대로 비교한다
    true_dt = birth_moment(birth.year, birth.month, birth.day, _hh, minute, city)["kst"]
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
    age_now = (today - birth).days / 365.25
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
