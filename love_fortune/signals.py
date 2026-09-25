"""signals.py, 좋은 달·좋은 해 (월운·세운 시그널). 사주 명리의 전통 방향만 따른다.

- 연애: 배우자성(남 재성, 여 관성)이 드는 때, 내 도화가 드는 때, 배우자 자리(일지)와
        합(육합·삼합)하는 때는 +, 일지와 충하는 때는 -
- 직장: 관성·인성이 드는 때 +, 역마가 드는 때 + (움직임), 일지·월지와 충하면 -
- 금전: 재성이 드는 때 +, 식상(재물을 낳는 기운)이 드는 때 +, 겁재(나눠 가져가는 기운)가 드는 때 -
- 공통: 일주 공망에 드는 때는 결과가 비기 쉬워 -

천간과 지지(본기)를 함께 본다. 수치는 방향을 나타내는 자작 점수이며 확률이 아니다.
"""
from __future__ import annotations

from datetime import date, datetime

from .manseryuk import (BRANCHES_KR, KONGWANG, STEMS_KR, YIMA_AT, _trio_of, month_pillar,
                        year_pillar)
from .match import BRANCH_BONQI, DOHWA_MAP
from .rules import ten_god
from .today import GOD_GROUP

LABEL = [(4, "밀고 나갈 때"), (2, "좋은 흐름"), (-1, "무난한 흐름"), (-3, "다듬을 때"), (-99, "조심할 때")]


def _label(v: int) -> str:
    return next(name for th, name in LABEL if v >= th)


def _score(natal: dict, sex: str, stem: int, branch: int) -> dict:
    ds, db = natal["ilgan_stem"], natal["day_branch"]
    yb, mb = natal["pillars"]["year"][1], natal["pillars"]["month"][1]
    gods = [ten_god(ds, stem), ten_god(ds, BRANCH_BONQI[branch])]
    groups = [GOD_GROUP[g] for g in gods]
    spouse = "재성" if sex == "male" else "관성"
    why = {"love": [], "career": [], "money": []}
    sc = {"love": 0, "career": 0, "money": 0}
    if spouse in groups:
        sc["love"] += 2 * groups.count(spouse)
        why["love"].append(f"배우자성({spouse})이 드는 때")
    if branch in {d for base, d in DOHWA_MAP if yb in base or db in base}:
        sc["love"] += 2
        why["love"].append("도화(끌림의 별)가 드는 때")
    trio = _trio_of(db)
    if (db, branch) in {(0, 1), (1, 0), (2, 11), (11, 2), (3, 10), (10, 3), (4, 9), (9, 4),
                        (5, 8), (8, 5), (6, 7), (7, 6)} or (branch in trio and branch != db):
        sc["love"] += 1
        why["love"].append("배우자 자리(일지)와 손잡는 때")
    if (db + 6) % 12 == branch:
        sc["love"] -= 2
        sc["career"] -= 1
        why["love"].append("배우자 자리(일지)와 부딪치는 때")
    if "관성" in groups or "인성" in groups:
        sc["career"] += 2
        why["career"].append("관성·인성(자리와 뒷받침)이 드는 때")
    if branch in {YIMA_AT[_trio_of(db)], YIMA_AT[_trio_of(yb)]}:
        sc["career"] += 1
        why["career"].append("역마(움직임)가 드는 때")
    if (mb + 6) % 12 == branch:
        sc["career"] -= 1
        why["career"].append("월지(사회 자리)와 부딪치는 때")
    if "재성" in groups:
        sc["money"] += 2 * groups.count("재성")
        why["money"].append("재성(돈의 별)이 드는 때")
    if "식상" in groups:
        sc["money"] += 1
        why["money"].append("식상(돈을 낳는 재주)이 드는 때")
    if "겁재" in gods:
        sc["money"] -= 2
        why["money"].append("겁재(나눠 가져가는 기운)가 드는 때")
    idx60 = next(n for n in range(60) if n % 10 == ds and n % 12 == db)
    if branch in KONGWANG[idx60 // 10]:
        for k in sc:
            sc[k] -= 1
        why["career"].append("공망(비는 자리)에 드는 때")
    return {"ganzhi": STEMS_KR[stem] + BRANCHES_KR[branch], "god": gods[0],
            "scores": sc, "labels": {k: _label(v) for k, v in sc.items()}, "why": why}


def month_signals(natal: dict, sex: str, start: date, months: int = 12) -> list[dict]:
    """start 달부터 months 개월 (절기 기준 월운, 각 달 15일로 잡는다)."""
    out = []
    y, m = start.year, start.month
    for _ in range(months):
        s, b = month_pillar(datetime(y, m, 15, 12))
        row = _score(natal, sex, s, b)
        row.update({"year": y, "month": m})
        out.append(row)
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def year_signals(natal: dict, sex: str, start_year: int, years: int = 3) -> list[dict]:
    """세운 (입춘 기준 그해 간지, 7월 1일로 잡는다)."""
    out = []
    for y in range(start_year, start_year + years):
        s, b = year_pillar(datetime(y, 7, 1, 12))
        row = _score(natal, sex, s, b)
        row["year"] = y
        out.append(row)
    return out


def best(rows: list[dict], domain: str, n: int = 2) -> list[dict]:
    """영역별로 가장 좋은 때 (같으면 앞선 때)."""
    return sorted(rows, key=lambda r: -r["scores"][domain])[:n]


def love_year_line(natal: dict, sex: str, year: int) -> str:
    """올해 연애 한 줄. 세운 시그널(배우자성·도화·일지 합충·공망)을 그대로 따른다.

    예전엔 '올해 도화가 드나'만 보고 '도화운보다 내실을 다질 해'라고 적어서,
    배우자성이 들어 '밀고 나갈 때'로 나오는 해와 같은 화면에서 서로 엇갈렸다.
    """
    row = year_signals(natal, sex, year, 1)[0]
    tag, why = row["labels"]["love"], row["why"]["love"]
    reason = f" {', '.join(why)}라서 그래." if why else ""
    head = {"밀고 나갈 때": "올해는 연애에서 한 걸음 밀고 나가기 좋은 해야.",
            "좋은 흐름": "올해는 연애 흐름이 순하게 받쳐 주는 해야.",
            "무난한 흐름": "올해는 연애에서 크게 튀지 않는 무난한 해야.",
            "다듬을 때": "올해는 연애에서 서두르기보다 관계를 다듬기 좋은 해야.",
            "조심할 때": "올해는 연애에서 말과 속도를 조심하면 좋은 해야."}[tag]
    tail = ""
    if not any("도화" in w for w in why):
        tail = " 도화(끌림의 별)가 드는 해는 아니라서, 새 만남이 쏟아지기보다 가까운 자리에서 인연이 자라기 쉬운 흐름이야."
    return f"{head}{reason}{tail}"
