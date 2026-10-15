"""taekil.py, 길일 고르기 (로컬·결정적).

기간 내 매일 일진으로 영역 점수를 매겨 순위를 매긴다.
목적(total·love·career·money·study)별 정렬, 같은 점수는 빠른 날짜 우선.
총운은 연애·직장·금전·학업 네 영역 평균에서 출발한다 (2026-10-15 사용자 결정).
서술은 전통 해석에 근거한 경향·흐름체.
"""
from __future__ import annotations

from .josa import j

from datetime import date, datetime, timedelta

from .manseryuk import four_pillars, day_pillar, ganzhi_str, year_pillar
from .rules import ten_god, love_score
from .domains import career_score, money_score, study_score, total_score
from .narrate import GOD_SHORT

WEEKDAY = ["월", "화", "수", "목", "금", "토", "일"]
MAX_DAYS = 62


def pick_dates(birth: date, hour: int | None, minute: int, sex: str, city: str,
               start: date, end: date, domain: str = "total") -> dict:
    """기간 내 일자별 점수 + 순위. domain 중 하나 기준 정렬. 시간 미상도 받는다."""
    if domain not in ("total", "love", "career", "money", "study"):
        raise ValueError("domain은 total·love·career·money·study 중 하나")
    if end < start:
        raise ValueError("끝 날짜가 시작 날짜보다 빠르다")
    if (end - start).days + 1 > MAX_DAYS:
        raise ValueError(f"기간은 최대 {MAX_DAYS}일까지")
    natal = four_pillars(birth, hour, minute, city)
    ds = natal["ilgan_stem"]
    branches = [s for _, s in (natal["pillars"][k]
                               for k in ("year", "month", "day", "hour"))
                if s is not None]
    from .ziwei import ziwei_chart
    zw = ziwei_chart(birth, hour, minute, sex, city, start)
    cur_du_pal = next((p for p in zw["palaces"]
                       if p["daxian"] and p["daxian"][0] <= zw["xusui"] <= p["daxian"][1]),
                      None) if zw else None
    daxian_hua = list(cur_du_pal["hua"].values()) if cur_du_pal else []
    rows = []
    d = start
    while d <= end:
        ts, tb = day_pillar(d)
        seed = f"pick-{d.isoformat()}"
        ls, _, _ = love_score(ds, branches, ts, tb, seed, sex)
        cs, _, _ = career_score(ds, branches, ts, tb, seed)
        ns, _, _ = money_score(ds, branches, ts, tb, seed)
        ss, _, _ = study_score(ds, branches, ts, tb, seed)
        ln_branch = year_pillar(datetime(d.year, d.month, d.day, 12, 0))[1]
        tot, _, _, _ = total_score(ds, branches, ts, tb, ls, cs, ns,
                                  daxian_hua, ln_branch, seed, study=ss)
        god = ten_god(ds, ts)
        rows.append({
            "date": d.isoformat(),
            "label": f"{d.month}/{d.day}({WEEKDAY[d.weekday()]})",
            "ganzhi": ganzhi_str(ts, tb),
            "love": ls, "career": cs, "money": ns, "study": ss, "total": tot,
            "god": god, "god_mean": GOD_SHORT[god],
        })
        d += timedelta(days=1)
    key = domain
    # score: 순위를 매긴 바로 그 점수. 화면 막대·순위·이야기가 모두 이 값을 쓴다
    # (예전엔 총운일 때 화면이 연애·직장·금전 평균을 따로 셈해 1위 점수가 이야기와 달랐다)
    for r in rows:
        r["score"] = r[key]
    rows.sort(key=lambda r: (-r["score"], r["date"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    _dn = {"total": "총운", "love": "연애",
           "career": "직장", "money": "금전", "study": "학업"}[domain]
    _top1 = rows[0]
    _avg = sum(r["score"] for r in rows) // len(rows)
    _spread = rows[0]["score"] - rows[-1]["score"]
    story = [
        f"기간 {start.isoformat()}~{end.isoformat()} {len(rows)}일 중에서 "
        f"{_dn} 평균은 {_avg}점이야. "
        f"1위는 {_top1['label']}({_top1['ganzhi']}) {_top1['score']}점이야.",
        f"1위 날 들어오는 기운은 {j(_top1['god'], '이라')} {_top1['god_mean']} 흐름이야.",
        f"1위와 꼴찌 차이는 {_spread}점이야. " + (
            "차이가 커서 날짜를 가리면 좋은 기간이야." if _spread >= 15
            else "날짜별 차이가 작아서 편한 날을 고르면 돼."),
    ]
    return {"rows": rows, "domain": domain, "story": story,
            "start": start.isoformat(), "end": end.isoformat(),
            "count": len(rows)}
