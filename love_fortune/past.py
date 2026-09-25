"""past.py, 지나온 해 되짚기. 이미 지난 해들에 계산이 무엇을 가리켰는지 펼쳐 놓는다.

사용자가 자기 기억과 맞춰 보며 '맞았어·아니야'를 직접 고른다. 결과를 지어내지 않고
계산이 가리킨 신호만 보여 주는 것이 원칙이다.

- 세운 시그널: 해마다 연애·일·돈에 '밀고 나갈 때'와 '다듬을·조심할 때' (signals.year_signals)
- 교운기: 사주 대운이 바뀐 해와 그 앞뒤 1년. 대운이 바뀌는 전후 1~2년에 직장·관계·거주 같은
  삶의 맥락이 재편되기 쉽다고 보는 해석 (사주하루·사자사주·데이사주 등 여러 곳이 같은 설명, 2026-09 조사)
- 자미두수 대한이 바뀐 해 (세는나이 기준 대한 시작 나이)
- 토성 회귀: 지나가는 토성이 태어날 때 토성 자리로 돌아오는 때 (약 29세·58세). 점성술에서
  삶의 구조를 다시 짜는 때로 본다. 날짜는 실제 행성 위치로 찾는다 (역행 때문에 한 해에 여러 번 지날 수 있다)
- 목성 회귀: 약 12년마다 목성이 태어날 때 자리로 돌아오는 때. 확장·기회의 때로 본다
"""
from __future__ import annotations

from datetime import date, timedelta

from . import astronomy as A
from .signals import year_signals

STRONG = {"밀고 나갈 때": "up", "좋은 흐름": "up", "다듬을 때": "down", "조심할 때": "down"}
DOMAIN_KR = {"love": "연애", "career": "일", "money": "돈"}
SCAN_DAYS = 4


def _lon(d: date, planet: str) -> float:
    return A.planet_longitude(A.day_number(d.year, d.month, d.day, 12.0), planet)


def planet_returns(natal_lon: float, planet: str, birth: date, until: date) -> list[dict]:
    """지나가는 행성이 태어날 때 황경을 다시 지나는 구간들 [{start, end}] (날짜 문자열).

    역행으로 여러 번 지나면 400일 안의 것은 한 구간으로 묶는다.
    """
    hits: list[date] = []
    d = birth + timedelta(days=300)          # 태어난 직후 겹침은 빼고 본다
    prev = ((_lon(d, planet) - natal_lon + 540) % 360) - 180
    while d < until:
        n = d + timedelta(days=SCAN_DAYS)
        cur = ((_lon(n, planet) - natal_lon + 540) % 360) - 180
        if (prev < 0 <= cur or prev > 0 >= cur) and abs(cur - prev) < 20:
            hits.append(n)
        prev, d = cur, n
    groups: list[list[date]] = []
    for h in hits:
        if groups and (h - groups[-1][-1]).days < 400:
            groups[-1].append(h)
        else:
            groups.append([h])
    return [{"start": g[0].isoformat(), "end": g[-1].isoformat()} for g in groups]


def _age(birth: date, on: date) -> int:
    return on.year - birth.year - ((on.month, on.day) < (birth.month, birth.day))


def look_back(birth: date, natal: dict, sex: str, dayun: dict, ziwei: dict | None,
              saturn_lon: float, jupiter_lon: float, target: date, span: int = 20) -> dict:
    first = max(birth.year + 12, target.year - span)
    years = list(range(first, target.year))
    marks: dict[int, list[dict]] = {y: [] for y in years}

    # 사주 대운이 바뀐 해 (만 나이 소수점 → 날짜)
    for st in dayun["steps"]:
        when = birth + timedelta(days=round(st["from"] * 365.2425))
        for y in (when.year - 1, when.year, when.year + 1):
            if y in marks:
                marks[y].append({"kind": "gyowun", "exact": y == when.year,
                                 "text": (f"{st['ganzhi']} 대운이 시작된 해 (만 {st['from']}세)" if y == when.year
                                          else f"대운이 바뀌는 앞뒤 해 (교운기, {st['ganzhi']} 대운)")})
    # 자미두수 대한이 바뀐 해 (세는나이 x 는 태어난 해 + x - 1 년)
    if ziwei:
        for p in ziwei["palaces"]:
            if p["daxian"]:
                y = birth.year + p["daxian"][0] - 1
                if y in marks:
                    marks[y].append({"kind": "daxian", "exact": True,
                                     "text": f"자미두수 10년 흐름이 {p['name']} 자리로 옮긴 해"})
    # 토성·목성 회귀
    until = date(target.year, 1, 1)
    returns = {"saturn": planet_returns(saturn_lon, "saturn", birth, until),
               "jupiter": planet_returns(jupiter_lon, "jupiter", birth, until)}
    names = {"saturn": ("토성 회귀", "삶의 틀을 다시 짜는 때로 보는 시기"),
             "jupiter": ("목성 회귀", "넓히고 새 기회를 여는 때로 보는 시기")}
    for planet, spans in returns.items():
        for sp in spans:
            y0, y1 = int(sp["start"][:4]), int(sp["end"][:4])
            for y in range(y0, y1 + 1):
                if y in marks:
                    name, talk = names[planet]
                    marks[y].append({"kind": planet, "exact": True,
                                     "text": f"{name} ({sp['start'][:7]}~{sp['end'][:7]}): {talk}"})

    rows = []
    for r in year_signals(natal, sex, first, len(years)):
        y = r["year"]
        signals = []
        for dom in ("love", "career", "money"):
            tag = r["labels"][dom]
            if tag in STRONG:
                signals.append({"domain": dom, "word": DOMAIN_KR[dom], "tag": tag, "dir": STRONG[tag],
                                "why": list(r["why"][dom])})
        rows.append({"year": y, "age": _age(birth, date(y, 12, 31)), "ganzhi": r["ganzhi"],
                     "signals": signals, "marks": marks[y]})
    return {"rows": rows, "returns": returns,
            "note": "계산이 그해에 가리킨 신호야. 맞았는지는 네 기억으로 골라 봐."}
