"""insights.py, 여러 체계를 겹쳐 보는 계산: 세 체계 합의도, 연애 골든타임, 절기 기준 달의 날짜.

- 합의도: 앞으로 10년, 해마다 영역(연애·직장·금전)별로 사주·자미두수·점성술이 각각 좋은 쪽(+1)·조심(−1)·보통(0)
  중 어디를 가리키는지 적고, 몇 체계가 같은 쪽인지 센다.
  - 사주: 그해 세운의 영역 신호 점수 (signals.year_signals)
  - 자미두수: 그해 중심(유년 명궁)이 영역 궁이거나 그해 화록이 영역 궁에 붙으면 +1, 화기가 붙으면 −1
  - 점성술: 목성이 영역 하우스(연애 5·7, 직장 10, 금전 2)를 지나면 +1 (12년에 한 번 오는 확장의 때로 봄)
  태어난 시간을 모르면 자미두수·하우스를 세울 수 없어 사주만 본다.
- 골든타임: 앞으로 24개월 중 연애 신호가 가장 센 달 (월별 연애 점수 + 목성 연애·인연 칸 + 목성·금성 합 + 목성 하강점 통과).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from .astro import SIGNS
from .lunar import MAX_YEAR
from .signals import month_signals, year_signals
from .transit import sky_on

JIE = {315, 345, 15, 45, 75, 105, 135, 165, 195, 225, 255, 285}
DOMAINS = ("love", "career", "money")
DOMAIN_PALACE = {"love": "부처(배우자)", "career": "관록", "money": "재백"}
DOMAIN_HOUSES = {"love": (5, 7), "career": (10,), "money": (2,)}
HOUSE_WORD = {2: "돈 칸(2번)", 5: "연애 칸(5번)", 7: "인연 칸(7번)", 10: "일 칸(10번)"}
PALACE_WORD = {"부처(배우자)": "배우자 자리", "관록": "일 자리", "재백": "돈 자리"}
PALACE_PLAIN = {"명궁": "나 자신", "형제": "형제", "부처(배우자)": "배우자", "자녀": "자녀", "재백": "돈", "질액": "건강",
                "천이": "바깥 활동", "노복": "친구·동료", "관록": "일", "전택": "집", "복덕": "마음·취미", "부모": "부모"}


def jie_bounds(y: int, m: int) -> tuple[date, date] | None:
    """사주의 달(절기 기준)이 시작하는 날과 끝나는 날. y년 m월에 드는 절기부터 다음 절기 전날까지."""
    from .solar_terms_data import TERMS

    def start(yy: int, mm: int) -> date | None:
        for lon, iso in TERMS.get(yy, []):
            if int(lon) in JIE:
                t = datetime.fromisoformat(iso)
                if t.month == mm:
                    return t.date()
        return None

    s = start(y, m)
    e = start(y + (m == 12), m % 12 + 1)
    if s is None or e is None:
        return None
    return s, e - timedelta(days=1)


def plain_why(w: str) -> str:
    """월별 신호 문장을 짧은 말로 (공유 카드·캘린더용)."""
    if w.startswith("배우자를 뜻하는"):
        return "이성 인연 별이 들어옴"
    if w.startswith("도화"):
        return "끌림 별이 켜짐"
    if "손잡는" in w:
        return "배우자 자리랑 손잡음"
    if "부딪치는" in w:
        return "배우자 자리가 흔들림"
    return w


def _houses(sign_names: list[str], asc_sign: str) -> set[int]:
    a = SIGNS.index(asc_sign)
    return {(SIGNS.index(s) - a) % 12 + 1 for s in sign_names}


def _jupiter_signs(y: int) -> list[str]:
    out = []
    for d in (date(y, 1, 1), date(y, 7, 1), date(y, 12, 31)):
        s = sky_on(d)["jupiter"]["sign"]
        if s not in out:
            out.append(s)
    return out


def consensus(birth: date, hour: int | None, minute: int, sex: str, city: str,
              natal: dict, asc_sign: str | None, target: date, years: int = 10) -> list[dict]:
    from .ziwei import ziwei_chart
    rows = []
    sig = {r["year"]: r for r in year_signals(natal, sex, target.year, years)}
    for y in range(target.year, target.year + years):
        s = sig[y]
        # 음력표가 닿는 해(MAX_YEAR)까지만 자미두수를 본다. 그 뒤 해는 사주·점성술만 (예전엔 2040년 이후 기준일이면 오류)
        zw = (ziwei_chart(birth, hour, minute, sex, city, date(y, 7, 1))
              if hour is not None and y <= MAX_YEAR else None)
        ln_pal, hua_pal = None, {}
        if zw:
            ln_pal = next(p["name"] for p in zw["palaces"] if p["liunian"])
            star_pal = {st: p["name"] for p in zw["palaces"] for st in p["stars"]}
            hua_pal = {h: star_pal.get(zw["liunian"]["sihua"][h]) for h in ("록", "기")}
        jup = _jupiter_signs(y)
        jh = _houses(jup, asc_sign) if asc_sign else set()
        doms = {}
        for d in DOMAINS:
            sc = s["scores"][d]
            saju = 1 if sc > 0 else -1 if sc < 0 else 0
            saju_why = ", ".join(s["why"][d]) or "크게 걸리는 신호 없음"
            ziwei = ziwei_why = None
            if zw:
                pal = DOMAIN_PALACE[d]
                up = ln_pal == pal or hua_pal.get("록") == pal
                down = hua_pal.get("기") == pal
                ziwei = (1 if up else 0) - (1 if down else 0)
                parts = []
                if ln_pal == pal:
                    parts.append(f"그해 중심이 {PALACE_WORD[pal]}")
                if hua_pal.get("록") == pal:
                    parts.append(f"그해 복(화록)이 {PALACE_WORD[pal]}에")
                if down:
                    parts.append(f"그해 막힘(화기)이 {PALACE_WORD[pal]}에")
                plain = PALACE_PLAIN.get(ln_pal, ln_pal)
                ziwei_why = ", ".join(parts) or (f"그해 중심은 {plain} 자리" + (f"({ln_pal})" if plain != ln_pal else ""))
            astro = astro_why = None
            if asc_sign:
                hit = sorted(h for h in DOMAIN_HOUSES[d] if h in jh)
                astro = 1 if hit else 0
                astro_why = (f"목성이 {', '.join(HOUSE_WORD[h] for h in hit)}을 지남" if hit
                             else f"목성은 {'→'.join(jup)}")
            vals = [v for v in (saju, ziwei, astro) if v is not None]
            doms[d] = {"saju": saju, "ziwei": ziwei, "astro": astro,
                       "up": sum(v > 0 for v in vals), "down": sum(v < 0 for v in vals), "n": len(vals),
                       "why": {"saju": saju_why, "ziwei": ziwei_why, "astro": astro_why}}
        rows.append({"year": y, "age": y - birth.year - ((7, 1) < (birth.month, birth.day)),
                     "ganzhi": s["ganzhi"], "domains": doms})
    return rows


def golden(natal: dict, sex: str, target: date, asc_lon: float | None, venus_lon: float,
           consensus_rows: list[dict], months: int = 24) -> dict:
    """앞으로 months 개월 중 연애 신호가 가장 센 달과, 세 체계가 가장 많이 겹치는 해."""
    asc_sign = SIGNS[int(asc_lon // 30)] if asc_lon is not None else None
    dsc = (asc_lon + 180) % 360 if asc_lon is not None else None
    best_m = None
    for r in month_signals(natal, sex, date(target.year, target.month, 1), months):
        b = jie_bounds(r["year"], r["month"])
        if b is None:
            continue
        s, e = b
        if e < target:
            continue
        mid = s + (e - s) / 2
        jl = sky_on(mid)["jupiter"]["lon"]
        parts = [plain_why(w) for w in r["why"]["love"]]
        power = r["scores"]["love"]
        if asc_sign:
            h = _houses([SIGNS[int(jl // 30)]], asc_sign).pop()
            if h in (5, 7):
                power += 2
                parts.append("목성이 " + HOUSE_WORD[h])
        if abs((jl - venus_lon + 180) % 360 - 180) <= 8:
            power += 2
            parts.append("목성이 내 금성 위")
        if dsc is not None and abs((jl - dsc + 180) % 360 - 180) <= 5:
            power += 3
            parts.append("목성이 인연 문 통과")
        cand = {"ym": f"{r['year']}-{r['month']:02d}", "year": r["year"], "month": r["month"],
                "from": s.isoformat(), "to": e.isoformat(), "ganzhi": r["ganzhi"], "power": power,
                "parts": parts}
        if best_m is None or power > best_m["power"]:
            best_m = cand
    best_y = None
    for row in consensus_rows:
        c = row["domains"]["love"]
        key = (c["up"] - c["down"], -row["year"])
        if best_y is None or key > best_y[0]:
            best_y = (key, {"year": row["year"], "age": row["age"], "up": c["up"], "n": c["n"]})
    return {"month": best_m, "year": best_y[1] if best_y else None}
