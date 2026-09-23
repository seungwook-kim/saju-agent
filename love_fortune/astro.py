"""astro.py, 서양 점성술 실측 차트 (로컬·결정적).

위치는 astronomy.py(저정밀 천문 알고리즘, pymeeus 대조 검증:
태양 0.001°·달 0.12°·수성~화성 0.05° 이내·토성 0.6°·목성 2.2°)로 계산.
열대황도(Tropical), Whole Sign 하우스, 고전적 어스펙트 오브.
행성이 별자리 경계 3° 이내면 '경계 부근' 표시.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from . import astronomy as A
from .lunar import birth_moment

SIGNS = ["양자리", "황소자리", "쌍둥이자리", "게자리", "사자자리",
         "처녀자리", "천칭자리", "전갈자리", "사수자리", "염소자리",
         "물병자리", "물고기자리"]
SIGN_ELEMENT = {"양자리": "불", "사자자리": "불", "사수자리": "불",
                "황소자리": "흙", "처녀자리": "흙", "염소자리": "흙",
                "쌍둥이자리": "공기", "천칭자리": "공기", "물병자리": "공기",
                "게자리": "물", "전갈자리": "물", "물고기자리": "물"}
BODIES = ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn"]
BODY_KR = {"sun": "태양", "moon": "달", "mercury": "수성", "venus": "금성",
           "mars": "화성", "jupiter": "목성", "saturn": "토성"}
ASPECTS = [(0.0, "합", 8.0), (60.0, "육합", 4.0), (90.0, "형", 6.0),
           (120.0, "삼합", 8.0), (180.0, "충", 8.0)]


def sign_of(lon: float) -> tuple[str, float]:
    idx = int(lon // 30.0) % 12
    return SIGNS[idx], lon - idx * 30.0


def _ut_parts(ut: datetime):
    base = datetime(ut.year, ut.month, ut.day)
    return ut.year, ut.month, ut.day, (ut - base).total_seconds() / 3600.0


def natal_chart(d: date, hour: int | None = 12, minute: int = 0,
                city: str = "서울") -> dict:
    """hour None이면 정오 기준 위치만 계산, 하우스·상승궁은 쓰지 않는다."""
    _hh = 12 if hour is None else hour
    # 그때 그 지역의 표준시·서머타임을 반영한 세계시 (예전엔 늘 9시간을 뺐다)
    bm = birth_moment(d.year, d.month, d.day, _hh, minute, city)
    lon_e, lat_n, city_ok = bm["lon"], bm["lat"], bm["city_ok"]
    y, m, dd, ut = _ut_parts(bm["utc"])
    dn = A.day_number(y, m, dd, ut)
    pos = {}
    for b in BODIES:
        if b == "sun":
            lon = A.sun_position(dn)[0]
        elif b == "moon":
            lon = A.moon_position(dn)[0]
        else:
            lon = A.planet_longitude(dn, b)
        sign, deg = sign_of(lon)
        retro = A.is_retrograde(y, m, dd, b) if b not in ("sun", "moon") else False
        cusp = deg > 27.0
        pos[b] = {"lon": round(lon, 2), "sign": sign, "deg": round(deg, 2),
                  "retro": retro, "cusp": cusp}
    asc, mc = A.asc_mc(y, m, dd, ut, lon_e, lat_n)
    asc_sign, asc_deg = sign_of(asc)
    mc_sign, mc_deg = sign_of(mc)
    asc_idx = SIGNS.index(asc_sign)
    houses = {}
    for b, p in pos.items():
        houses[b] = ((SIGNS.index(p["sign"]) - asc_idx) % 12) + 1
    aspects = []
    keys = list(pos)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            diff = abs(pos[keys[i]]["lon"] - pos[keys[j]]["lon"])
            diff = min(diff, 360.0 - diff)
            for ang, name, orb in ASPECTS:
                if abs(diff - ang) <= orb:
                    aspects.append(
                        f"{BODY_KR[keys[i]]}–{BODY_KR[keys[j]]} {name}"
                        f"({diff:.1f}°)")
                    break
    return {"positions": pos, "houses": houses, "aspects": aspects,
            "asc": {"lon": round(asc, 2), "sign": asc_sign,
                    "deg": round(asc_deg, 2)},
            "mc": {"lon": round(mc, 2), "sign": mc_sign,
                   "deg": round(mc_deg, 2)},
            "city_ok": city_ok}


def moon_sign(birth: date, hour: int = 12, minute: int = 0,
              city: str = "서울") -> tuple[str, str]:
    from .advise import VENUS_VIBE_SHORT
    sign = natal_chart(birth, hour, minute, city)["positions"]["moon"]["sign"]
    return sign, "달은 감정·무의식, " + VENUS_VIBE_SHORT[SIGN_ELEMENT[sign]]


def venus_sign(birth: date, hour: int = 12, minute: int = 0,
               city: str = "서울") -> tuple[str, str]:
    from .advise import VENUS_VIBE_SHORT
    sign = natal_chart(birth, hour, minute, city)["positions"]["venus"]["sign"]
    return sign, "금성은 취향·애정운, " + VENUS_VIBE_SHORT[SIGN_ELEMENT[sign]]


def ascendant(birth: date, hour: int = 12, minute: int = 0,
              city: str = "서울") -> str:
    return natal_chart(birth, hour, minute, city)["asc"]["sign"]


def compat_line(natal_elem: str, today_elem_astro: str) -> str:
    from .advise import COMPAT
    key = tuple(sorted((natal_elem, today_elem_astro)))
    return COMPAT.get(key, "원소 궁합, 서로 다른 매력이 통하기 쉬운 흐름")


def astro_chart(birth: date, hour: int, target: date,
                minute: int = 0, city: str = "서울") -> dict:
    from .advise import zodiac_planet, VENUS_VIBE_SHORT
    natal = natal_chart(birth, hour, minute, city)
    sun = natal["positions"]["sun"]["sign"]
    planet = zodiac_planet(sun)
    moon = natal["positions"]["moon"]["sign"]
    venus = natal["positions"]["venus"]["sign"]
    asc = natal["asc"]["sign"]
    t_sun = natal_chart(target, 12, 0, city)["positions"]["sun"]["sign"]
    line = compat_line(SIGN_ELEMENT[venus], SIGN_ELEMENT[t_sun])
    cusp_notes = [f"{BODY_KR[b]}이 {p['sign']} 끝자락(경계 부근)"
                  for b, p in natal["positions"].items() if p["cusp"]]
    retro_notes = [f"{BODY_KR[b]} 역행" for b, p in natal["positions"].items()
                   if p["retro"]]
    return {
        "method": "서양 점성술 실측 차트(열대황도·Whole Sign 하우스)",
        "sun": {"sign": sun, "planet": planet,
                "vibe": VENUS_VIBE_SHORT[SIGN_ELEMENT[sun]]},
        "moon": {"sign": moon,
                 "vibe": "달은 감정·무의식, " + VENUS_VIBE_SHORT[SIGN_ELEMENT[moon]]},
        "venus": {"sign": venus,
                  "vibe": "금성은 취향·애정운, " + VENUS_VIBE_SHORT[SIGN_ELEMENT[venus]]},
        "ascendant": asc, "mc": natal["mc"]["sign"],
        "houses": {BODY_KR[b]: h for b, h in natal["houses"].items()},
        "aspects": natal["aspects"],
        "cusp_notes": cusp_notes, "retro_notes": retro_notes,
        "positions": natal["positions"],
        "today_sun": t_sun,
        "compat_line": (f"내 금성 {venus}와 오늘 태양 {t_sun}은 {line}"),
        "city_ok": natal["city_ok"],
    }
