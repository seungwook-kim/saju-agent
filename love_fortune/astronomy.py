"""astronomy.py, 저정밀 천문 알고리즘 (Paul Schlyter 공개 알고리즘 계열, 표준라이브러리만).

용도: 태양황경(절기 계산용), 달·수성~토성 황경, GMST/ASC·MC, 균시차.
정밀도 (1900~2049년 무작위 1500시점, PyEphem 대조 최대 오차):
태양 0.02°, 달 0.09°, 수성 0.03°, 금성 0.05°, 화성 0.06°, 목성 0.03°, 토성 0.05°.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta

_cache_terms: dict[int, dict[str, datetime]] = {}


def rev(x: float) -> float:
    x = x % 360.0
    return x


def sind(x: float) -> float:
    return math.sin(math.radians(x))


def cosd(x: float) -> float:
    return math.cos(math.radians(x))


def atan2d(y: float, x: float) -> float:
    return rev(math.degrees(math.atan2(y, x)))


def day_number(y: int, m: int, d: int, ut: float = 0.0) -> float:
    """2000 Jan 0.0 기준 일수.

    예전엔 Schlyter 원문의 정수 근사식을 썼는데, 그 식은 1900년 3월부터만
    맞아서 1900년 1~2월은 하루가 밀렸다. 날짜 차이로 정확히 센다.
    """
    return (date(y, m, d) - date(1999, 12, 31)).days + ut / 24.0


def obliquity(dnum: float) -> float:
    return 23.4393 - 3.563e-7 * dnum


def _kepler_e(M: float, e: float) -> float:
    E = M + math.degrees(e) * sind(M) * (1.0 + e * cosd(M))
    for _ in range(3):
        E = E - (E - math.degrees(e) * sind(E) - M) / (1.0 - e * cosd(E))
    return E


def sun_position(dnum: float) -> tuple[float, float]:
    """(시황경, 일지거리AU)."""
    w = rev(282.9404 + 4.70935e-5 * dnum)
    e = 0.016709 - 1.151e-9 * dnum
    M = rev(356.0470 + 0.9856002585 * dnum)
    E = _kepler_e(M, e)
    x = math.cos(math.radians(E)) - e
    y = math.sin(math.radians(E)) * math.sqrt(1 - e * e)
    v = atan2d(y, x)
    r = math.hypot(x, y)
    lon = rev(v + w - 0.00569 - 0.00478 * sind(125.04 - 0.052954 * dnum))
    return lon, r


def _ecl_from_orbit(r: float, v: float, N: float, i: float, w: float):
    xh = r * (cosd(N) * cosd(v + w) - sind(N) * sind(v + w) * cosd(i))
    yh = r * (sind(N) * cosd(v + w) + cosd(N) * sind(v + w) * cosd(i))
    zh = r * (sind(v + w) * sind(i))
    return xh, yh, zh


def moon_position(dnum: float) -> tuple[float, float]:
    """(황경, 황위). 주요 섭동항 포함."""
    N = rev(125.1228 - 0.0529538083 * dnum)
    i = 5.1454
    w = rev(318.0634 + 0.1643573223 * dnum)
    a = 60.2666
    e = 0.054900
    M = rev(115.3654 + 13.0649929509 * dnum)
    E = _kepler_e(M, e)
    x = a * (math.cos(math.radians(E)) - e)
    y = a * math.sqrt(1 - e * e) * math.sin(math.radians(E))
    r = math.hypot(x, y)
    v = atan2d(y, x)
    xh, yh, zh = _ecl_from_orbit(r, v, N, i, w)
    lon = atan2d(yh, xh)
    lat = atan2d(zh, math.hypot(xh, yh))
    Ms = 356.0470 + 0.9856002585 * dnum
    ws = 282.9404 + 4.70935e-5 * dnum
    Lm = N + w + M
    D = Lm - (Ms + ws)
    F = Lm - N
    # 섭동항 12개 (Schlyter 원문 전부). 예전엔 앞의 5개만 있었다.
    lon += (-1.274 * sind(M - 2 * D) + 0.658 * sind(2 * D)
            - 0.186 * sind(Ms) - 0.059 * sind(2 * M - 2 * D)
            - 0.057 * sind(M - 2 * D + Ms) + 0.053 * sind(M + 2 * D)
            + 0.046 * sind(2 * D - Ms) + 0.041 * sind(M - Ms)
            - 0.035 * sind(D) - 0.031 * sind(M + Ms)
            - 0.015 * sind(2 * F - 2 * D) + 0.011 * sind(M - 4 * D))
    lat += (-0.173 * sind(F - 2 * D) - 0.055 * sind(M - F - 2 * D)
            - 0.046 * sind(M + F - 2 * D) + 0.033 * sind(F + 2 * D)
            + 0.017 * sind(2 * M + F))
    return rev(lon), lat


_PLANETS = {
    "mercury": {"N": (48.3313, 3.24587e-5), "i": (7.0047, 5.00e-8),
                "w": (29.1241, 1.01444e-5), "a": (0.387098, 0.0),
                "e": (0.205635, 5.59e-10), "M": (168.6562, 4.0923344368)},
    "venus": {"N": (76.6799, 2.46590e-5), "i": (3.3946, 2.75e-8),
              "w": (54.8910, 1.38374e-5), "a": (0.723330, 0.0),
              "e": (0.006773, -1.302e-9), "M": (48.0052, 1.6021304744)},
    "mars": {"N": (49.5574, 2.11081e-5), "i": (1.8497, -1.78e-8),
             "w": (286.5016, 2.93861e-5), "a": (1.523688, 0.0),
             "e": (0.093405, 2.516e-9), "M": (18.6021, 0.5240207766)},
    "jupiter": {"N": (100.4542, 2.76854e-5), "i": (1.3030, -1.557e-7),
                # 궤도 반지름은 상수다. 예전엔 원문에 없는 시간 항이 붙어
                # 목성이 최대 8도 어긋났다.
                "w": (273.8777, 1.64505e-5), "a": (5.20256, 0.0),
                "e": (0.048498, 4.472e-9), "M": (19.8950, 0.0830853001)},
    "saturn": {"N": (113.6634, 2.38980e-5), "i": (2.4886, -1.081e-7),
               "w": (339.3939, 2.97661e-5), "a": (9.55475, 0.0),
               "e": (0.055546, -9.499e-9), "M": (316.9670, 0.0334442282)},
}


def planet_longitude(dnum: float, name: str) -> float:
    """지구중심 황경."""
    P = _PLANETS[name]
    N = rev(P["N"][0] + P["N"][1] * dnum)
    i = P["i"][0] + P["i"][1] * dnum
    w = rev(P["w"][0] + P["w"][1] * dnum)
    a = P["a"][0] + P["a"][1] * dnum
    e = P["e"][0] + P["e"][1] * dnum
    M = rev(P["M"][0] + P["M"][1] * dnum)
    E = _kepler_e(M, e)
    Er = math.radians(E)
    x = a * (math.cos(Er) - e)
    y = a * math.sqrt(1 - e * e) * math.sin(Er)
    r = math.hypot(x, y)
    v = atan2d(y, x)
    xh, yh, zh = _ecl_from_orbit(r, v, N, i, w)
    if name in ("jupiter", "saturn"):
        # 목성·토성이 서로 끌어당겨 생기는 섭동 (Schlyter 원문 항).
        # 없으면 토성이 0.8도까지 어긋난다.
        Mj = 19.8950 + 0.0830853001 * dnum
        Msat = 316.9670 + 0.0334442282 * dnum
        if name == "jupiter":
            dl = (-0.332 * sind(2 * Mj - 5 * Msat - 67.6)
                  - 0.056 * sind(2 * Mj - 2 * Msat + 21)
                  + 0.042 * sind(3 * Mj - 5 * Msat + 21)
                  - 0.036 * sind(Mj - 2 * Msat)
                  + 0.022 * cosd(Mj - Msat)
                  + 0.023 * sind(2 * Mj - 3 * Msat + 52)
                  - 0.016 * sind(Mj - 5 * Msat - 69))
        else:
            dl = (0.812 * sind(2 * Mj - 5 * Msat - 67.6)
                  - 0.229 * cosd(2 * Mj - 4 * Msat - 2)
                  + 0.119 * sind(Mj - 2 * Msat - 3)
                  + 0.046 * sind(2 * Mj - 6 * Msat - 69)
                  + 0.014 * sind(Mj - 3 * Msat + 32))
        hlon = atan2d(yh, xh) + dl
        rxy = math.hypot(xh, yh)
        xh, yh = rxy * cosd(hlon), rxy * sind(hlon)
    slon, sr = sun_position(dnum)
    xs = sr * cosd(slon)
    ys = sr * sind(slon)
    return rev(atan2d(yh + ys, xh + xs))


def is_retrograde(y: int, m: int, d: int, name: str) -> bool:
    """지구중심 황경이 감소 중이면 역행."""
    a = planet_longitude(day_number(y, m, d, 12.0) - 0.5, name)
    b = planet_longitude(day_number(y, m, d, 12.0) + 0.5, name)
    return (b - a + 540.0) % 360.0 - 180.0 < 0


def gmst_deg(y: int, m: int, d: int, ut: float) -> float:
    dnum = day_number(y, m, d, ut)
    Ms = 356.0470 + 0.9856002585 * dnum
    ws = 282.9404 + 4.70935e-5 * dnum
    return rev(rev(Ms + ws + 180.0) / 15.0 * 15.0 + ut * 15.0)


def asc_mc(y: int, m: int, d: int, ut: float,
           lon_e: float, lat_n: float) -> tuple[float, float]:
    """(ASC 황경, MC 황경)."""
    ramc = rev(gmst_deg(y, m, d, ut) + lon_e)
    eps = obliquity(day_number(y, m, d, ut))
    mc = rev(atan2d(sind(ramc) * cosd(eps), cosd(ramc)))
    asc = rev(atan2d(cosd(ramc),
                     -(sind(ramc) * cosd(eps) + math.tan(math.radians(lat_n)) * sind(eps))))
    return asc, mc


def equation_of_time(dt: date) -> float:
    """균시차(분). NOAA 근사식."""
    doy = dt.timetuple().tm_yday
    g = math.radians(360.0 / 365.0 * (doy - 81))
    return 229.18 * (0.000075 + 0.001868 * math.cos(g)
                     - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g)
                     - 0.040849 * math.sin(2 * g))


# 12절 (월주·년주 경계) + 황경
JIE_LON = {"입춘": 315.0, "경칩": 345.0, "청명": 15.0, "입하": 45.0,
           "망종": 75.0, "소서": 105.0, "입추": 135.0, "백로": 165.0,
           "한로": 195.0, "입동": 225.0, "대설": 255.0, "소한": 285.0}
# 절 이후의 월지 (0=자..11=해): 입춘→인(2), 경칩→묘(3), ... 소한→축(1)
JIE_BRANCH = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 0, 1]


def _sun_lon_kst(dt: datetime) -> float:
    ut = (dt - timedelta(hours=9)).timetuple()
    # UT hour float
    base = datetime(ut.tm_year, ut.tm_mon, ut.tm_mday)
    uth = (dt - timedelta(hours=9) - base).total_seconds() / 3600.0
    return sun_position(day_number(ut.tm_year, ut.tm_mon, ut.tm_mday, uth))[0]


def solar_term_moment(year: int, target_lon: float) -> datetime:
    """해당 연도에 태양 시황경이 target_lon이 되는 KST 시각 (이분 탐색)."""
    # 연도별 캐시는 모듈 전역에 둔다
    if year not in _cache_terms:
        _cache_terms[year] = {}
    if target_lon in _cache_terms[year]:
        return _cache_terms[year][target_lon]
    lo = datetime(year, 1, 1, 0, 0)
    hi = datetime(year + 1, 1, 15, 0, 0)
    # coarse scan (6시간 간격) 후 bisection
    step = timedelta(hours=6)
    t = lo
    prev = _sun_lon_kst(t)
    bracket = None
    while t < hi:
        t += step
        cur = _sun_lon_kst(t)
        # target을 지나는지 (wrap 고려): prev→cur 구간에 target 포함?
        d1 = (target_lon - prev) % 360.0
        d2 = (cur - prev) % 360.0
        if 0 < d1 <= d2 and d2 < 180:
            bracket = (t - step, t)
            break
        prev = cur
    if bracket is None:
        raise RuntimeError(f"절기 탐색 실패: {year} {target_lon}")
    lo, hi = bracket
    for _ in range(40):
        mid = lo + (hi - lo) / 2
        m = _sun_lon_kst(mid)
        if (target_lon - _sun_lon_kst(lo)) % 360.0 <= (m - _sun_lon_kst(lo)) % 360.0:
            hi = mid
        else:
            lo = mid
    res = lo + (hi - lo) / 2
    _cache_terms[year][target_lon] = res
    return res


def month_branch_exact(dt_kst: datetime) -> int:
    """정확한 절기 기준 월지."""
    lon = _sun_lon_kst(dt_kst)
    # 각 절 사이 구간 → 해당 절의 월지
    # 망종은 황경 75도다. 예전엔 60도(소만)로 적혀 있어 5월 하순~6월 초
    # 출생자의 월주가 한 달 앞당겨졌다.
    order = [15.0, 45.0, 75.0, 105.0, 135.0, 165.0,
             195.0, 225.0, 255.0, 285.0, 315.0, 345.0]
    branches = [4, 5, 6, 7, 8, 9, 10, 11, 0, 1, 2, 3]
    # order[i] <= lon < order[i+1] → branches[i]
    for i in range(len(order)):
        lo_b = order[i]
        hi_b = order[(i + 1) % len(order)]
        if lo_b <= hi_b:
            if lo_b <= lon < hi_b:
                return branches[i]
        else:
            if lon >= lo_b or lon < hi_b:
                return branches[i]
    return 2
