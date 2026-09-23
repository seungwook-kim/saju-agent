"""lunar.py, 음력 변환·출생 시각 보정 (내장 데이터, 무의존·오프라인).

- 음력표: 한국천문연구원 음력 자료 기준 (calendar_data.LUNAR, 1899~2049 음력년).
  예전 표는 중국 달력 기준이라 한국 음력과 2천여 일이 하루씩 어긋났다
  (예: 1997년 설날 한국 2월 8일, 중국 2월 7일).
- 출생 시각: 도시별 표준시·서머타임 이력(calendar_data.ZONES, IANA tz 기준)으로
  세계시를 구한 뒤, 경도와 균시차로 진태양시를 만든다.
  한국은 1908~1911년과 1954~1961년에 표준시가 UTC+8:30 이었고,
  1948~1951년·1955~1960년·1987~1988년에는 서머타임이 있었다.
"""
from __future__ import annotations

from bisect import bisect_right
from datetime import date, datetime, timedelta

from .astronomy import equation_of_time
from .calendar_data import LUNAR, ZONES

MIN_YEAR = 1900
MAX_YEAR = 2049


# ---------------------------------------------------------------- 음력


def _new_year(ly: int) -> date:
    mmdd = LUNAR[ly][0]
    return date(ly, mmdd // 100, mmdd % 100)


def _months(ly: int) -> list[tuple[int, bool, int]]:
    """음력 ly년의 달 목록 [(월, 윤달여부, 일수), ...] 순서대로."""
    _ny, leap, mask, leap_len = LUNAR[ly]
    out = []
    for m in range(1, 13):
        out.append((m, False, 30 if (mask >> (12 - m)) & 1 else 29))
        if m == leap:
            out.append((m, True, leap_len))
    return out


def solar_to_lunar(y: int, m: int, d: int) -> tuple[int, int, int, bool]:
    """양력 → 음력 (년, 월, 일, 윤달여부)."""
    if not (MIN_YEAR <= y <= MAX_YEAR):
        raise ValueError(f"지원 범위 초과: {MIN_YEAR}~{MAX_YEAR}년")
    dt = date(y, m, d)
    ly = y
    if dt < _new_year(ly):
        ly -= 1
    offset = (dt - _new_year(ly)).days
    for month, leap, days in _months(ly):
        if offset < days:
            return (ly, month, offset + 1, leap)
        offset -= days
    raise RuntimeError("음력 변환 실패")


def lunar_month_days(ly: int, lm: int, leap: bool = False) -> int:
    """음력 ly년 lm월(윤달이면 leap=True)의 날 수. 없는 달이면 ValueError."""
    if ly not in LUNAR:
        raise ValueError(f"지원 범위 초과: 음력 {MIN_YEAR}~{MAX_YEAR}년")
    for month, is_leap, days in _months(ly):
        if month == lm and is_leap == leap:
            return days
    if leap:
        real = LUNAR[ly][1]
        hint = f"그해 윤달은 {real}월이야" if real else "그해에는 윤달이 없어"
        raise ValueError(f"음력 {ly}년에는 윤{lm}월이 없어. {hint}")
    raise ValueError(f"음력 월은 1~12 사이여야 해 (입력 {lm})")


def lunar_to_solar(ly: int, lm: int, ld: int, leap: bool = False) -> date:
    """음력 → 양력. 잘못된 날짜면 이유를 담아 ValueError.

    음력 1899년 섣달(양력 1900년 1월)도 받는다. 결과가 양력 지원 범위를 벗어나면 거절한다.
    """
    if ly not in LUNAR:
        raise ValueError(f"지원 범위 초과: 음력 {MIN_YEAR}~{MAX_YEAR}년")
    days = lunar_month_days(ly, lm, leap)
    if not 1 <= ld <= days:
        raise ValueError(f"음력 {ly}년 {'윤' if leap else ''}{lm}월은 {days}일까지야 (입력 {ld}일)")
    offset = 0
    for month, is_leap, n in _months(ly):
        if month == lm and is_leap == leap:
            break
        offset += n
    out = _new_year(ly) + timedelta(days=offset + ld - 1)
    if not (MIN_YEAR <= out.year <= MAX_YEAR):
        raise ValueError(f"지원 범위 초과: 양력 {MIN_YEAR}~{MAX_YEAR}년")
    return out


def parse_birth_date(text: str, calendar: str = "solar", leap: bool = False) -> date:
    """'YYYY-MM-DD' 를 양력 날짜로. calendar 가 lunar(음력)이면 음력으로 읽어 바꾼다.

    잘못된 날짜(없는 윤달, 30일이 없는 달 등)는 이유를 담은 ValueError.
    """
    cal = (calendar or "solar").strip().lower()
    if cal in ("solar", "양력", "s"):
        cal = "solar"
    elif cal in ("lunar", "음력", "l"):
        cal = "lunar"
    else:
        raise ValueError(f"달력은 양력(solar) 또는 음력(lunar)이어야 해 (입력: {calendar!r})")
    try:
        y, m, d = (int(x) for x in str(text).strip().split("-"))
    except ValueError:
        raise ValueError("생년월일은 YYYY-MM-DD 형식으로 입력해 줘 (예: 1990-05-15)") from None
    if cal == "lunar":
        return lunar_to_solar(y, m, d, bool(leap))
    if leap:
        raise ValueError("윤달 표시는 음력으로 입력할 때만 쓸 수 있어")
    out = date(y, m, d)
    if not (MIN_YEAR <= y <= MAX_YEAR):
        raise ValueError(f"지원 범위 초과: {MIN_YEAR}~{MAX_YEAR}년")
    return out


# ---------------------------------------------------------------- 도시

# 이름: (경도, 위도, 표준시 지역). 경도·위도는 시청 부근 어림값이다.
# 경도 0.1도 차이는 진태양시로 24초라 사주 계산에는 영향이 없다.
_KR, _NK = "Asia/Seoul", "Asia/Pyongyang"
CITIES: dict[str, tuple[float, float, str]] = {
    # 특별시·광역시·특별자치시
    "서울": (126.98, 37.57, _KR), "부산": (129.08, 35.18, _KR),
    "대구": (128.60, 35.87, _KR), "인천": (126.70, 37.46, _KR),
    "광주": (126.85, 35.16, _KR), "대전": (127.38, 36.35, _KR),
    "울산": (129.31, 35.54, _KR), "세종": (127.29, 36.48, _KR),
    # 경기
    "수원": (127.03, 37.26, _KR), "성남": (127.13, 37.42, _KR),
    "고양": (126.83, 37.66, _KR), "용인": (127.18, 37.24, _KR),
    "부천": (126.78, 37.50, _KR), "안산": (126.83, 37.32, _KR),
    "안양": (126.93, 37.39, _KR), "남양주": (127.22, 37.64, _KR),
    "화성": (126.83, 37.20, _KR), "평택": (127.11, 36.99, _KR),
    "의정부": (127.03, 37.74, _KR), "파주": (126.78, 37.76, _KR),
    "시흥": (126.80, 37.38, _KR), "김포": (126.72, 37.62, _KR),
    "광명": (126.86, 37.48, _KR), "구리": (127.13, 37.59, _KR),
    "오산": (127.08, 37.15, _KR), "이천": (127.44, 37.27, _KR),
    "하남": (127.21, 37.54, _KR), "군포": (126.94, 37.36, _KR),
    "양주": (127.05, 37.79, _KR), "포천": (127.20, 37.89, _KR),
    # 강원
    "춘천": (127.73, 37.88, _KR), "원주": (127.92, 37.34, _KR),
    "강릉": (128.88, 37.75, _KR), "속초": (128.59, 38.21, _KR),
    "동해": (129.11, 37.52, _KR), "삼척": (129.17, 37.45, _KR),
    # 충청
    "청주": (127.49, 36.64, _KR), "충주": (127.93, 36.99, _KR),
    "제천": (128.19, 37.13, _KR), "천안": (127.15, 36.81, _KR),
    "아산": (127.00, 36.79, _KR), "공주": (127.12, 36.45, _KR),
    "서산": (126.45, 36.78, _KR), "논산": (127.10, 36.19, _KR),
    "보령": (126.61, 36.33, _KR), "당진": (126.63, 36.89, _KR),
    # 전라
    "전주": (127.15, 35.82, _KR), "익산": (126.96, 35.95, _KR),
    "군산": (126.74, 35.97, _KR), "정읍": (126.86, 35.57, _KR),
    "남원": (127.39, 35.42, _KR), "목포": (126.39, 34.81, _KR),
    "여수": (127.66, 34.76, _KR), "순천": (127.49, 34.95, _KR),
    "광양": (127.70, 34.94, _KR), "나주": (126.71, 35.02, _KR),
    # 경상
    "포항": (129.37, 36.02, _KR), "경주": (129.22, 35.86, _KR),
    "구미": (128.34, 36.12, _KR), "안동": (128.73, 36.57, _KR),
    "김천": (128.11, 36.14, _KR), "영주": (128.62, 36.81, _KR),
    "상주": (128.16, 36.41, _KR), "경산": (128.74, 35.83, _KR),
    "창원": (128.68, 35.23, _KR), "마산": (128.57, 35.21, _KR),
    "진주": (128.11, 35.18, _KR), "김해": (128.89, 35.23, _KR),
    "양산": (129.04, 35.34, _KR), "거제": (128.62, 34.88, _KR),
    "통영": (128.43, 34.85, _KR), "사천": (128.06, 35.00, _KR),
    "밀양": (128.75, 35.50, _KR),
    # 제주
    "제주": (126.53, 33.50, _KR), "서귀포": (126.56, 33.25, _KR),
    # 북한 (표준시 이력이 남한과 다르다)
    "평양": (125.75, 39.03, _NK), "개성": (126.55, 37.97, _NK),
    "함흥": (127.54, 39.92, _NK), "원산": (127.44, 39.15, _NK),
    "신의주": (124.40, 40.10, _NK), "청진": (129.78, 41.80, _NK),
    # 해외 (현지 시각 그대로 입력하면 된다. 현지 서머타임은 자동 반영)
    "도쿄": (139.69, 35.69, "Asia/Tokyo"), "오사카": (135.50, 34.69, "Asia/Tokyo"),
    "베이징": (116.40, 39.90, "Asia/Shanghai"), "상하이": (121.47, 31.23, "Asia/Shanghai"),
    "홍콩": (114.17, 22.32, "Asia/Hong_Kong"), "타이베이": (121.56, 25.03, "Asia/Taipei"),
    "싱가포르": (103.82, 1.35, "Asia/Singapore"), "방콕": (100.50, 13.75, "Asia/Bangkok"),
    "호치민": (106.63, 10.82, "Asia/Ho_Chi_Minh"), "하노이": (105.85, 21.03, "Asia/Bangkok"),
    "마닐라": (120.98, 14.60, "Asia/Manila"), "자카르타": (106.85, -6.21, "Asia/Jakarta"),
    "두바이": (55.27, 25.20, "Asia/Dubai"),
    "시드니": (151.21, -33.87, "Australia/Sydney"),
    "멜버른": (144.96, -37.81, "Australia/Melbourne"),
    "오클랜드": (174.76, -36.85, "Pacific/Auckland"),
    "뉴욕": (-74.01, 40.71, "America/New_York"), "워싱턴": (-77.04, 38.91, "America/New_York"),
    "보스턴": (-71.06, 42.36, "America/New_York"), "애틀랜타": (-84.39, 33.75, "America/New_York"),
    "시카고": (-87.63, 41.88, "America/Chicago"), "휴스턴": (-95.37, 29.76, "America/Chicago"),
    "댈러스": (-96.80, 32.78, "America/Chicago"), "덴버": (-104.99, 39.74, "America/Denver"),
    "로스앤젤레스": (-118.24, 34.05, "America/Los_Angeles"),
    "샌프란시스코": (-122.42, 37.77, "America/Los_Angeles"),
    "시애틀": (-122.33, 47.61, "America/Los_Angeles"),
    "호놀룰루": (-157.86, 21.31, "Pacific/Honolulu"),
    "토론토": (-79.38, 43.65, "America/Toronto"), "밴쿠버": (-123.12, 49.28, "America/Vancouver"),
    "상파울루": (-46.63, -23.55, "America/Sao_Paulo"),
    "런던": (-0.13, 51.51, "Europe/London"), "파리": (2.35, 48.86, "Europe/Paris"),
    "베를린": (13.40, 52.52, "Europe/Berlin"), "프랑크푸르트": (8.68, 50.11, "Europe/Berlin"),
    "모스크바": (37.62, 55.76, "Europe/Moscow"),
}
CITY_ALIASES = {
    "la": "로스앤젤레스", "엘에이": "로스앤젤레스", "los angeles": "로스앤젤레스",
    "nyc": "뉴욕", "new york": "뉴욕", "sf": "샌프란시스코",
    "san francisco": "샌프란시스코", "seattle": "시애틀", "chicago": "시카고",
    "tokyo": "도쿄", "동경": "도쿄", "osaka": "오사카", "beijing": "베이징",
    "북경": "베이징", "shanghai": "상하이", "hong kong": "홍콩", "taipei": "타이베이",
    "singapore": "싱가포르", "sydney": "시드니", "melbourne": "멜버른",
    "london": "런던", "paris": "파리", "berlin": "베를린", "toronto": "토론토",
    "vancouver": "밴쿠버", "seoul": "서울", "busan": "부산", "pusan": "부산",
    "호찌민": "호치민", "사이공": "호치민",
}
# 예전 이름 (다른 모듈·테스트 호환). (경도, 위도)만 담는다.
CITY_GEO = {k: (v[0], v[1]) for k, v in CITIES.items()}

# 도시를 못 찾았을 때 쓰는 값: 남한 중앙 부근 경도 + 한국 표준시
DEFAULT_GEO = (127.0, 36.4, _KR)


def _suffix_strip(name: str) -> str:
    for suf in ("특별자치시", "특별자치도", "특별시", "광역시", "시", "군"):
        if name.endswith(suf) and len(name) > len(suf) + 1:
            return name[: -len(suf)]
    return name


def city_info(city: str) -> dict:
    """도시 이름 → {name, lon, lat, zone, matched}. 못 찾으면 matched=False."""
    raw = (city or "").strip()
    key = raw.lower()
    name = CITY_ALIASES.get(key) or CITY_ALIASES.get(raw)
    if not name and raw in CITIES:
        name = raw
    if not name:
        stripped = _suffix_strip(raw)
        if stripped in CITIES:
            name = stripped
    if not name and raw:
        # "서울시 강남구", "경기도 수원시" 같은 입력. 긴 이름부터 찾아 짧은 이름 오인을 막는다.
        for cand in sorted(CITIES, key=len, reverse=True):
            if cand in raw:
                name = cand
                break
    if name:
        lon, lat, zone = CITIES[name]
        return {"name": name, "lon": lon, "lat": lat, "zone": zone, "matched": True}
    lon, lat, zone = DEFAULT_GEO
    return {"name": "", "lon": lon, "lat": lat, "zone": zone, "matched": False}


def lookup_city(city: str) -> tuple[float, float, bool]:
    """(경도, 위도, 매칭여부). 못 찾으면 남한 중앙 부근 경도로 어림한다."""
    c = city_info(city)
    return c["lon"], c["lat"], c["matched"]


# ---------------------------------------------------------------- 표준시


_EPOCH = datetime(1970, 1, 1)


def zone_offset(local: datetime, zone: str) -> tuple[int, bool]:
    """그 지역 벽시계 시각 local 의 (UTC 오프셋 초, 서머타임 여부).

    서머타임이 끝나며 같은 시각이 두 번 오는 경우에는 앞(서머타임) 쪽을,
    시작하며 건너뛴 시각에는 바뀌기 전 오프셋을 쓴다 (파이썬 fold=0 과 같다).
    """
    table = ZONES[zone]
    starts = [t for t, _o, _d in table]
    guess_utc = (local - _EPOCH).total_seconds()
    # 오프셋 후보를 앞 구간부터 확인해, 벽시계로 그 구간 안에 드는 첫 번째를 고른다
    i = max(0, bisect_right(starts, guess_utc - 16 * 3600) - 1)
    best = None
    while i < len(table):
        t0, off, dst = table[i]
        t1 = table[i + 1][0] if i + 1 < len(table) else float("inf")
        utc = guess_utc - off
        if t0 <= utc < t1:
            return off, bool(dst)
        if utc < t0:
            break
        best = (off, bool(dst))
        i += 1
    if best is None:
        _t0, off, dst = table[0]
        return off, bool(dst)
    return best


def birth_moment(y: int, m: int, d: int, hh: int, mm: int, city: str) -> dict:
    """출생 벽시계 시각 → 절대 시각과 진태양시.

    반환:
      utc        세계시 (naive)
      kst        같은 순간을 UTC+9 로 적은 값. 절기 시각(한국 표준시 기준)과 비교할 때 쓴다
      true_solar 진태양시 = 세계시 + 경도/15시간 + 균시차. 일주·시주 경계에 쓴다
      corr_min   진태양시 - 입력 시각 (분)
      offset_h   그때 그 지역의 UTC 오프셋 (시간), dst 서머타임 여부
    """
    info = city_info(city)
    local = datetime(y, m, d, hh, mm)
    off, dst = zone_offset(local, info["zone"])
    utc = local - timedelta(seconds=off)
    lmt = utc + timedelta(hours=info["lon"] / 15.0)
    tst = lmt + timedelta(minutes=equation_of_time(lmt.date()))
    return {
        "local": local, "utc": utc, "kst": utc + timedelta(hours=9),
        "true_solar": tst, "corr_min": (tst - local).total_seconds() / 60.0,
        "lon": info["lon"], "lat": info["lat"], "zone": info["zone"],
        "city_ok": info["matched"], "city_name": info["name"],
        "offset_h": off / 3600.0, "dst": dst,
    }


def true_solar_time(y: int, m: int, d: int, hh: int, mm: int,
                    city: str) -> tuple[datetime, float, float, bool]:
    """벽시계 입력 → 진태양시. (시각, 보정분, 사용경도, 도시매칭).

    표준시가 UTC+8:30 이던 시기와 서머타임도 반영한다 (birth_moment 참고).
    """
    b = birth_moment(y, m, d, hh, mm, city)
    return b["true_solar"], b["corr_min"], b["lon"], b["city_ok"]
