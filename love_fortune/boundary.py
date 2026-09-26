"""boundary.py, 경계 출생 알림. 출생 시각이 조금만 달라도 기둥이 바뀌는 경우를 먼저 알려 준다.

- 절입 경계: 월주(입춘이면 년주도)는 절기가 드는 순간(절입)에 바뀐다. 출생이 절입과 3시간 안이면
  출생 기록·시계 오차만으로 월주가 달라질 수 있어 두 기둥을 함께 보여 준다.
  태어난 시간을 모르면, 태어난 날 안에 절입이 들어 있을 때 알려 준다.
- 시 경계: 시주는 진태양시로 두 시간마다(홀수 시 정각) 바뀐다. 보정한 시각이 경계와 10분 안이면 알려 준다.
  밤 11시 경계는 일주도 바뀔 수 있다 (정자시 기준).
절기 시각은 JPL 천체력으로 계산한 표(solar_terms_data)를 쓴다.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .josa import j
from .lunar import birth_moment
from .manseryuk import ganzhi_str, month_pillar, year_pillar

JIE_NAME = {315: "입춘", 345: "경칩", 15: "청명", 45: "입하", 75: "망종", 105: "소서",
            135: "입추", 165: "백로", 195: "한로", 225: "입동", 255: "대설", 285: "소한"}
TERM_WINDOW = timedelta(hours=3)
HOUR_WINDOW_MIN = 10


def _jie_moments(year: int) -> list[tuple[str, datetime]]:
    from .solar_terms_data import TERMS
    out = []
    for y in (year - 1, year, year + 1):
        for lon, iso in TERMS.get(y, []):
            if int(lon) in JIE_NAME:
                out.append((JIE_NAME[int(lon)], datetime.fromisoformat(iso)))
    return out


def _fmt_gap(td: timedelta) -> str:
    m = int(abs(td.total_seconds()) // 60)
    return f"{m // 60}시간 {m % 60}분" if m >= 60 else f"{m}분"


def check(birth, hour: int | None, minute: int, city: str) -> dict:
    """{"items": [{kind, text, current, alt}], "note"} 경계가 없으면 items 가 빈 목록."""
    from .manseryuk import four_pillars
    items = []
    if hour is not None:
        bm = birth_moment(birth.year, birth.month, birth.day, hour, minute, city)
        kst = bm["kst"]
        name, t = min(_jie_moments(kst.year), key=lambda x: abs(x[1] - kst))
        if abs(t - kst) <= TERM_WINDOW:
            before, after = t - timedelta(minutes=1), t + timedelta(minutes=1)
            cur_m = ganzhi_str(*month_pillar(kst))
            alt_m = ganzhi_str(*month_pillar(after if kst < t else before))
            side = "직전" if kst < t else "직후"
            items.append({"kind": "month", "current": cur_m, "alt": alt_m,
                          "text": (f"{name} 절입(한국 시각 {t:%Y-%m-%d %H:%M}) {side} {_fmt_gap(t - kst)} 사이에 태어났어. "
                                   f"출생 기록이 이만큼만 달라도 월주가 {cur_m}에서 {j(alt_m, '로')} 바뀔 수 있어.")})
            if name == "입춘":
                cur_y = ganzhi_str(*year_pillar(kst))
                alt_y = ganzhi_str(*year_pillar(after if kst < t else before))
                items.append({"kind": "year", "current": cur_y, "alt": alt_y,
                              "text": f"입춘은 해가 바뀌는 절기라 년주(띠)도 {cur_y}에서 {j(alt_y, '로')} 바뀔 수 있어."})
        # 시 경계 (진태양시 홀수 시 정각)
        ts = bm["true_solar"]
        mins = ts.hour * 60 + ts.minute
        edges = range(-60, 24 * 60 + 61, 120)          # 전날 23:00, 01:00, 03:00 … 23:00, 다음날 01:00
        edge = min(edges, key=lambda e: abs(e - mins))
        gap = edge - mins
        if abs(gap) <= HOUR_WINDOW_MIN:
            shift = gap + (1 if gap >= 0 else -1)
            local = datetime(birth.year, birth.month, birth.day, hour, minute) + timedelta(minutes=shift)
            cur = four_pillars(birth, hour, minute, city)
            alt = four_pillars(local.date(), local.hour, local.minute, city)
            ch = cur["strings"]
            ah = alt["strings"]
            changed = [k for k in ("hour", "day") if ch.get(k) != ah.get(k)]
            if changed:
                label = {"hour": "시주", "day": "일주"}
                parts = ", ".join(f"{label[k]}가 {ch[k]}에서 {ah[k]}" for k in changed)
                items.append({"kind": "hour", "current": ch.get("hour"), "alt": ah.get("hour"),
                              "text": (f"진태양시(보정 {bm['corr_min']:+.0f}분)로 {ts:%H:%M}에 태어나 시가 바뀌는 경계와 "
                                       f"{abs(gap)}분 차이야. 출생 기록이 조금만 달라도 {j(parts, '로')} 바뀔 수 있어.")})
    else:
        day0 = birth_moment(birth.year, birth.month, birth.day, 0, 0, city)["kst"]
        day1 = day0 + timedelta(days=1)
        for name, t in _jie_moments(birth.year):
            if day0 <= t < day1:
                m0 = ganzhi_str(*month_pillar(t - timedelta(minutes=1)))
                m1 = ganzhi_str(*month_pillar(t + timedelta(minutes=1)))
                items.append({"kind": "month", "current": ganzhi_str(*month_pillar(day0 + timedelta(hours=12))),
                              "alt": m1 if m0 == ganzhi_str(*month_pillar(day0 + timedelta(hours=12))) else m0,
                              "text": (f"태어난 날이 {name} 절입일(한국 시각 {t:%H:%M})이라, 태어난 시간에 따라 월주가 "
                                       f"{m0} 또는 {j(m1, '이야')}. 지금은 정오 기준으로 봤어.")})
    note = ("출생 시각이 경계 가까이 있어서, 기록된 시각이 정확한지(병원 기록 등) 한 번 확인해 보면 좋아."
            if items else "")
    return {"items": items, "note": note}
