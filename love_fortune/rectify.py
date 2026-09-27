"""rectify.py, 태어난 시간 추정 (재미·참고용).

인생 사건 몇 개를 받아, 12개 시진(2시간 단위) 후보마다 그 사건들이 해당 시간의 명반·차트와 얼마나 맞는지 점수를 매긴다.
점성술의 출생시간 보정(rectification) 방법을 따른다: 사건마다 삶의 영역(관계·집·일·몸)을 정하고,
후보 시간의 하우스·각(상승점·천정·하강점·천저)에 그해 느린 행성이 닿았는지 본다. 각은 시간에 가장 민감한 점이라
1.5배로 센다 (kerykeion 출생시간 보정 안내). 자미두수는 시진이 바뀌면 명궁이 옮겨 가서 그해 중심 궁(유년)과
10년 궁(대한)의 이름이 달라지는 점을 쓴다. 사주 시주는 이 결과로 정해지는 값이라 점수에는 넣지 않는다.
사건이 적으면 후보끼리 점수 차가 작아서 '판단 보류'로 알린다. 사건 다섯 개 이상을 권한다.
"""
from __future__ import annotations

from datetime import date

from .lunar import birth_moment
from .manseryuk import BRANCHES_KR, four_pillars
from .astro import SIGNS, natal_chart
from .transit import sky_on

# 사건 종류: (이름, 자미두수 궁, 점성 하우스, 점성 각)
KINDS = {
    "love": ("연애 시작·결혼", ("부처(배우자)",), (5, 7), ("dsc",)),
    "breakup": ("이별·이혼", ("부처(배우자)",), (7, 8), ("dsc",)),
    "move": ("이사·이민", ("천이", "전택"), (4, 9), ("ic",)),
    "job": ("취업·이직·승진", ("관록",), (10, 6), ("mc",)),
    "health": ("큰 병·사고·수술", ("질액",), (6, 12), ("asc",)),
    "child": ("아이 출생", ("자녀",), (5,), ("ic",)),
    "money": ("큰돈이 들어오거나 나감", ("재백",), (2, 8), ()),
    "family": ("가족을 떠나보냄", ("부모", "형제"), (4, 8), ("ic",)),
}
ANGLE_WORD = {"asc": "상승점(나)", "mc": "천정(일)", "dsc": "하강점(관계)", "ic": "천저(집)"}
MAX_EVENTS = 10


def _sky_year(y: int, cache: dict) -> list[dict]:
    if y not in cache:
        cache[y] = [sky_on(date(y, m, 15)) for m in range(1, 13)]
    return cache[y]


def _near(a: float, b: float, orb: float = 3.0) -> bool:
    return abs((a - b + 180) % 360 - 180) <= orb


def candidates(birth: date, city: str) -> list[dict]:
    """12시진 후보와 그 시진의 가운데 시각(시계 시각). 진태양시 보정량은 그날 정오 기준."""
    corr = birth_moment(birth.year, birth.month, birth.day, 12, 0, city)["corr_min"]
    out = []
    for k in range(12):
        mid = (k * 120) % 1440                      # 자시 가운데 = 진태양시 0시
        clock = round(mid - corr) % 1440
        start, end = round(mid - 60 - corr) % 1440, round(mid + 59 - corr) % 1440
        out.append({"branch": BRANCHES_KR[k], "label": BRANCHES_KR[k] + "시", "hour": clock // 60, "minute": clock % 60,
                    "clock": f"{start // 60:02d}:{start % 60:02d}~{end // 60:02d}:{end % 60:02d}"})
    return out


def rectify(birth: date, sex: str, city: str, events: list[dict]) -> dict:
    from .ziwei import ziwei_chart
    evs = []
    for e in events[:MAX_EVENTS]:
        y, kind = int(e["year"]), str(e["kind"])
        if kind not in KINDS or not (birth.year <= y <= date.today().year):
            raise ValueError("사건 연도나 종류를 확인해 줘")
        evs.append((y, kind))
    if not evs:
        raise ValueError("사건을 하나 이상 넣어 줘")
    sky_cache: dict = {}
    rows = []
    for c in candidates(birth, city):
        h, m = c["hour"], c["minute"]
        nc = natal_chart(birth, h, m, city)
        asc, mc = nc["asc"]["lon"], nc["mc"]["lon"]
        angles = {"asc": asc, "mc": mc, "dsc": (asc + 180) % 360, "ic": (mc + 180) % 360}
        asc_i = SIGNS.index(nc["asc"]["sign"])
        score, hits = 0.0, []
        for y, kind in evs:
            name, palaces, houses, angs = KINDS[kind]
            why = []
            zw = ziwei_chart(birth, h, m, sex, city, date(y, 7, 1))
            if zw:
                xusui = y - birth.year + 1
                ln = next(p["name"] for p in zw["palaces"] if p["liunian"])
                dx = next((p["name"] for p in zw["palaces"] if p["daxian"] and p["daxian"][0] <= xusui <= p["daxian"][1]), None)
                if ln in palaces:
                    score += 1
                    why.append(f"자미두수 그해 중심이 {ln}")
                if dx in palaces:
                    score += 1
                    why.append(f"자미두수 10년 궁이 {dx}")
            months = _sky_year(y, sky_cache)
            for planet, pname in (("jupiter", "목성"), ("saturn", "토성")):
                hs = {(int(s[planet]["lon"] // 30) - asc_i) % 12 + 1 for s in months}
                hit = sorted(set(houses) & hs)
                if hit:
                    score += 1
                    why.append(f"{pname}이 {'·'.join(str(x) for x in hit)}번 하우스")
                for a in angs:
                    if any(_near(s[planet]["lon"], angles[a]) for s in months):
                        score += 1.5
                        why.append(f"{pname}이 {ANGLE_WORD[a]}에 닿음")
            hits.append({"year": y, "kind": name, "why": why})
        fp = four_pillars(birth, h, m, city)
        rows.append({**c, "score": round(score, 1), "hits": hits,
                     "hour_pillar": fp["strings"].get("hour"), "asc": nc["asc"]["sign"]})
    rows.sort(key=lambda r: -r["score"])
    gap = rows[0]["score"] - rows[1]["score"]
    confident = len(evs) >= 3 and gap >= 1.5
    note = ("1등과 2등 차이가 뚜렷해서 1등 시간대를 유력 후보로 볼 만해." if confident else
            "후보끼리 점수 차가 작아서 아직 판단을 보류하는 게 맞아. 사건을 더 넣으면 좁혀져 (다섯 개 이상 권해).")
    return {"events": len(evs), "candidates": rows, "confident": confident, "gap": round(gap, 1), "note": note}
