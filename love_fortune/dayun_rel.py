"""dayun_rel.py, 대운마다 원국 네 기둥과 손잡고(합) 부딪치는(충·형·파·해) 자리를 찾는다.

- 천간: 대운 하늘 글자와 원국 하늘 글자의 합(갑기·을경·병신·정임·무계)과 충(갑경·을신·병임·정계).
- 지지: 대운 땅 글자와 원국 땅 글자의 육합·삼합·충·형·파·해 (rules.branch_relation) + 같은 글자끼리의 자형(진·오·유·해).
어느 자리(해·달·날·시)에 걸리는지로 삶의 어느 쪽이 움직이기 쉬운지 풀어 준다. 단정하지 않고 '쉽다고 봐'로 말한다.
"""
from __future__ import annotations

from .josa import j
from .manseryuk import BRANCHES_KR, STEMS_KR
from .rules import branch_relation

STEM_HAP = [{0, 5}, {1, 6}, {2, 7}, {3, 8}, {4, 9}]
STEM_CHUNG = [{0, 6}, {1, 7}, {2, 8}, {3, 9}]
SELF_HYEONG = {4, 6, 9, 11}                     # 진·오·유·해는 같은 글자끼리 스스로 형(자형)

POS = ("year", "month", "day", "hour")
POS_PLAIN = {"year": "집안·윗사람 자리(태어난 해)", "month": "일터 자리(태어난 달)",
             "day": "나와 배우자 자리(태어난 날)", "hour": "자녀·앞날 자리(태어난 시)"}
AREA = {"year": "집안·윗사람", "month": "일·사회생활", "day": "나 자신과 배우자", "hour": "자녀·앞날 계획"}
NOUN = {"천간합": "하늘 글자 손잡음", "천간충": "하늘 글자 부딪침",
        "합": "손잡음(합)", "삼합": "한편 모임(삼합 짝)", "충": "부딪침(충)",
        "형": "조임(형)", "파": "틀어짐(파)", "해": "서운함(해)"}
MEANING = {
    "충": "그래서 {area} 쪽 일이 바뀌거나 옮겨 가기 쉬운 10년으로 봐.",
    "형": "그래서 {area} 쪽에서 조율할 일이 늘기 쉬운 10년으로 봐. 규칙·서류·몸 관리를 챙기면 좋아.",
    "천간충": "그래서 {area} 쪽에서 생각이 부딪치기 쉬운 10년으로 봐. 서두르지 않는 게 좋아.",
    "합": "그래서 {area} 쪽에 새 인연이나 협력이 엮이기 쉬운 10년으로 봐.",
    "삼합": "그래서 {area} 쪽으로 힘이 모이기 쉬운 10년으로 봐.",
    "천간합": "그래서 {area} 쪽 사람과 손발이 맞기 쉬운 10년으로 봐.",
    "파": "그래서 {area} 쪽 계획을 한 번씩 다시 짜게 되기 쉬운 10년으로 봐.",
    "해": "그래서 {area} 쪽 가까운 사이에서 말을 한 번 더 챙기면 좋은 10년이야.",
}
PRIORITY = ("충", "형", "천간충", "합", "삼합", "천간합", "파", "해")


def stem_kinds(a: int, b: int) -> list[str]:
    out = []
    if {a, b} in STEM_HAP:
        out.append("천간합")
    if {a, b} in STEM_CHUNG:
        out.append("천간충")
    return out


def branch_kinds(a: int, b: int) -> list[str]:
    out = []
    for r in branch_relation(a, b):
        k = ("합" if r.startswith("육합") else "삼합" if r.startswith("삼합") else "충" if r.startswith("육충")
             else "형" if "형" in r else "파" if r.startswith("파") else "해" if r.startswith("해") else None)
        if k and k not in out:
            out.append(k)
    if a == b and a in SELF_HYEONG and "형" not in out:
        out.append("형")
    return out


def step_relations(pillars: dict, s: int, b: int) -> dict:
    """대운 한 걸음(천간 s, 지지 b)과 원국 기둥별 관계. {자리: [관계, …]}"""
    cells = {}
    for pos in POS:
        ps, pb = pillars[pos]
        if ps is None:
            continue
        cells[pos] = stem_kinds(s, ps) + branch_kinds(b, pb)
    return cells


def build(pillars: dict, du: dict) -> list[dict]:
    """대운 여덟 걸음마다 원국과의 관계와 쉬운 말 풀이. 개인정보 없음(나이 구간만)."""
    cur = du.get("current", {}).get("ganzhi")
    out = []
    for st in du["steps"]:
        s, b = STEMS_KR.index(st["ganzhi"][0]), BRANCHES_KR.index(st["ganzhi"][1])
        cells = step_relations(pillars, s, b)
        out.append({"ganzhi": st["ganzhi"], "from": int(st["from"]), "to": int(st["to"]),
                    "now": st["ganzhi"] == cur, "cells": cells, "line": _line(st["ganzhi"], cells)})
    return out


def _line(gz: str, cells: dict) -> str:
    """같은 관계가 걸린 자리끼리 묶어 말하고, 가장 센 관계(충>형>…)의 자리로 뜻을 붙인다."""
    rank = {k: i for i, k in enumerate(PRIORITY)}
    groups: dict[tuple, list[str]] = {}
    for pos, kinds in cells.items():
        if kinds:
            groups.setdefault(tuple(sorted(kinds, key=rank.get)), []).append(pos)
    if not groups:
        return f"{gz}운은 원국과 크게 부딪치거나 손잡는 글자가 없어서 흐름이 비교적 잔잔한 10년이야."
    order = sorted(groups.items(), key=lambda kv: rank[kv[0][0]])
    parts = [f"{j('·'.join(POS_PLAIN[p] for p in pos), '과')}는 {j('·'.join(NOUN[k] for k in kinds), '이')} 걸려"
             for kinds, pos in order]
    top = order[0][0][0]
    area = "·".join(AREA[p] for p in POS if top in cells.get(p, []))
    return f"{gz}운은 " + ". ".join(parts) + ". " + MEANING[top].format(area=area)
