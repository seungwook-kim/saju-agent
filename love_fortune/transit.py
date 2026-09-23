"""transit.py, 오늘의 점성술: 오늘 하늘의 행성이 내 출생 행성과 이루는 각도(트랜짓).

- 오늘 위치는 기준일 정오(한국 표준시)로 잡는다. 같은 날이면 항상 같은 결과다.
- 허용 오차(orb)는 지나가는 행성 기준으로 달 5도, 태양·수성·금성·화성 3도, 목성·토성 2도
  (db/init.sql planet.orb). 여러 해설이 1~3도를 권하고, 가까울수록 영향이 크다고 본다.
  그래서 정확할수록 무게를 크게 준다 (무게 = 1 - 차이/허용 오차).
- 좋고 나쁨: 육합·삼합은 부드럽게, 형·충은 긴장으로 본다. 합은 행성 성격을 따른다
  (금성·목성은 길, 화성·토성은 긴장).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from . import astronomy as A
from . import store
from .astro import SIGNS, natal_chart

BODIES = ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn"]


def sky_on(d: date) -> dict[str, dict]:
    """기준일 정오(한국 표준시) 하늘의 행성 위치."""
    ut = datetime(d.year, d.month, d.day, 12) - timedelta(hours=9)
    dn = A.day_number(ut.year, ut.month, ut.day, ut.hour)
    out = {}
    for b in BODIES:
        if b == "sun":
            lon = A.sun_position(dn)[0]
        elif b == "moon":
            lon = A.moon_position(dn)[0]
        else:
            lon = A.planet_longitude(dn, b)
        retro = A.is_retrograde(d.year, d.month, d.day, b) if b not in ("sun", "moon") else False
        out[b] = {"lon": lon, "sign": SIGNS[int(lon // 30) % 12], "retro": retro}
    return out


def _sep(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def transits(birth: date, hour: int | None, minute: int, city: str, today: date) -> dict:
    """오늘 트랜짓 목록과 영역별 점수 가감."""
    planets = store.by_key("planet", "code")
    aspects = store.table("aspect")
    natal = natal_chart(birth, hour, minute, city)
    sky = sky_on(today)
    hits = []
    for tb in BODIES:
        orb = planets[tb]["orb"]
        for nb in BODIES:
            sep = _sep(sky[tb]["lon"], natal["positions"][nb]["lon"])
            for asp in aspects:
                diff = abs(sep - asp["angle"])
                if diff > orb:
                    continue
                if asp["harmony"] != 0:
                    tone = asp["harmony"]
                else:                                  # 합은 두 행성의 성격을 따른다
                    tone = planets[tb]["nature"] or planets[nb]["nature"]
                w = 1.0 - diff / orb
                hits.append({"transit": tb, "natal": nb, "aspect": asp["name"],
                             "talk": asp["talk"], "diff": round(diff, 2), "weight": round(w, 3),
                             "tone": tone})
                break
    hits.sort(key=lambda h: -h["weight"])

    def domain_points(key: str) -> float:
        total = 0.0
        for h in hits:
            wt = (planets[h["transit"]][key] + planets[h["natal"]][key]) / 2
            total += h["tone"] * h["weight"] * wt
        return total

    # 달 하우스 (태어난 시간을 알 때만): 오늘 달이 지나는 내 삶의 영역
    moon_house = None
    if hour is not None:
        asc_idx = SIGNS.index(natal["asc"]["sign"])
        moon_house = (SIGNS.index(sky["moon"]["sign"]) - asc_idx) % 12 + 1
    retro_today = [b for b in BODIES if sky[b]["retro"]]
    return {
        "hits": hits, "sky": sky, "moon_house": moon_house, "retro": retro_today,
        "points": {k: round(domain_points(f"w_{k}"), 2) for k in ("love", "career", "money")},
    }


def describe(tr: dict, limit: int = 4) -> list[str]:
    """오늘 트랜짓을 사람 말로 (가장 정확한 것부터)."""
    planets = store.by_key("planet", "code")
    houses = {r["num"]: r["area"] for r in store.table("house")}
    out = []
    moon = tr["sky"]["moon"]
    line = f"오늘 달은 {moon['sign']}를 지나"
    if tr["moon_house"]:
        line += f" 내 {tr['moon_house']}번 하우스({houses[tr['moon_house']]})를 비춰, 그쪽에 마음이 가기 쉬운 하루야."
    else:
        line += "는 중이야 (태어난 시간을 몰라 하우스는 제외)."
    out.append(line)
    for h in tr["hits"][:limit]:
        tp, np_ = planets[h["transit"]], planets[h["natal"]]
        mood = "기운이 잘 맞물리는" if h["tone"] > 0 else "긴장이 생기기 쉬운" if h["tone"] < 0 else "힘이 모이는"
        out.append(f"오늘 {tp['name']}({tp['keywords']})이 내 {np_['name']}({np_['keywords']})과 "
                   f"{h['aspect']}({h['talk']} 각도, 오차 {h['diff']}도)을 이뤄 {mood} 흐름이야.")
    if not tr["hits"]:
        out.append("오늘은 내 출생 행성과 딱 맞물리는 큰 각도가 없어 하늘이 조용한 날이야.")
    if tr["retro"]:
        names = ", ".join(planets[b]["name"] for b in tr["retro"])
        out.append(f"지금 {names}이 역행 중이라 그 행성이 맡은 일은 되짚어 보며 가면 좋은 때야.")
    return out
