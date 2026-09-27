"""lifetime.py, 평생 운세 타임라인 (로컬·결정적).

사주 대운(10년 단위) + 자미두수 대운궁 + 유년(매년) + 목성·토성 위치를 묶어
처음부터 끝까지의 흐름을 연대별·연도별로 정리한다.
서술은 전통 해석에 근거한 경향·흐름체.
"""
from __future__ import annotations

from datetime import date

from . import astronomy as A
from .astro import SIGNS, SIGN_ELEMENT
from .manseryuk import dayun, ganzhi_str, four_pillars, STEMS_KR, BRANCHES_KR
from .rules import ten_god, branch_relation
from .ziwei import ziwei_chart, SIHUA, XIAOXIAN_AT

from .narrate import (GOD_SHORT, STAR_TALK, JUP_TALK, SAT_TALK, _eun, _wa, _rel_text)

MAIN14 = ("자미", "천기", "태양", "무곡", "천동", "염정", "천부",
          "태음", "탐랑", "거문", "천상", "천량", "칠살", "파군")


def _sign(lon: float) -> str:
    return SIGNS[int(lon // 30) % 12]


def lifetime_reading(birth: date, hour: int, minute: int, sex: str,
                     city: str, today: date | None = None) -> dict:
    today = today or date.today()
    zw = ziwei_chart(birth, hour, minute, sex, city, today)
    du = dayun(birth, hour, minute, sex, city, today)
    pals = zw["palaces"] if zw else []

    def palace_at_xusui(x: int):
        return next((p for p in pals
                     if p["daxian"] and p["daxian"][0] <= x <= p["daxian"][1]), None)

    natal = four_pillars(birth, hour, minute, city)
    ds = natal["ilgan_stem"]
    db = natal["day_branch"]
    ilgan = natal["ilgan"]

    def palace_daxian(palace_name: str):
        if not pals:
            return None
        return next(p for p in pals if p["name"] == palace_name)["daxian"]

    spouse_dx = palace_daxian("부처(배우자)")
    guanlu_dx = palace_daxian("관록")
    caibo_dx = palace_daxian("재백")
    jilak_dx = palace_daxian("질액")

    def overlap(dx, lo: int, hi: int) -> bool:
        return dx is not None and not (dx[1] < lo or dx[0] > hi)

    # 연대별 (만 나이 10년 단위, 0세부터 89세까지)
    last = du["steps"][-1]
    decades = []
    a = 0
    while a <= 80:
        lo, hi = a, a + 9
        # 그 10년의 가운데 나이(lo+5)가 든 대운 = 그 연대를 가장 오래 덮는 대운.
        # 예전엔 시작 나이(lo)로 골라서, 대운이 30.0세에 바뀌면 30~39세를 끝나는 대운(20.1~30.0세)으로 적었다.
        mid_age = lo + 5
        step = next((s for s in du["steps"] if s["from"] <= mid_age <= s["to"] + 0.1), None)
        if step:
            saju = f"{step['ganzhi']}운({step['from']}~{step['to']}세)"
            dbranch = BRANCHES_KR.index(step["ganzhi"][1])
            dstem = STEMS_KR.index(step["ganzhi"][0])
            god = ten_god(ds, dstem)
            sstem, sbranch = step["ganzhi"][0], step["ganzhi"][1]
            saju_story = (f"사주로 풀어보면, 대운 천간 {sstem}{_eun(sstem)} 나({ilgan})에게 "
                          f"{GOD_SHORT[god]} 기운으로 다가와. "
                          f"대운 지지 {sbranch}{_eun(sbranch)} 내 일지 "
                          f"{BRANCHES_KR[db]}{_wa(BRANCHES_KR[db])} "
                          f"{_rel_text(branch_relation(db, dbranch))} 사이야.")
        elif mid_age >= last["to"]:
            saju = f"{last['ganzhi']}운 이후의 흐름"
            saju_story = "대운표 범위를 지난 시기로, 쌓은 것을 지키며 정리하는 때야."
        else:
            saju = (f"대운 시작 전, 월주 흐름"
                    f"({du['steps'][0]['from']}세부터 {du['steps'][0]['ganzhi']}운)")
            saju_story = "대운 시작 전이라 씨앗을 뿌리며 준비하는 때야."
        pal = palace_at_xusui(lo + 1)
        if pal:
            mains = [s for s in pal["stars"] if s in MAIN14]
            hua = ",".join(f"{s}화{h}" for s, h in pal["hua"].items())
            ziwei = (f"{pal['name']}({pal['stem_kr']}{pal['branch_kr']}, "
                     f"주성 {', '.join(mains) or '무주성'})"
                     + (f" [{hua}]" if hua else ""))
            pname = pal["name"]
            if mains:
                main_story = f"주성 {mains[0]}은 {STAR_TALK[mains[0]]}"
                if len(mains) > 1:
                    main_story += f" 같이 있는 {', '.join(mains[1:])}도 힘을 보태."
            else:
                opp = next(x for x in pals if x["branch"] == (pal["branch"] + 6) % 12)
                om = [s for s in opp["stars"] if s in MAIN14]
                main_story = (f"주성이 비어 있어 건너편 {opp['name']}궁의 "
                              f"{', '.join(om) or '기운'}을 빌려 쓰는 때야")
            mates = [next(x for x in pals if x["branch"] == (pal["branch"] + k) % 12)["name"]
                     for k in (4, 8, 6)]
            aux = [s for s in pal["stars"] if s not in MAIN14]
            aux_note = f" 작은 별 {len(aux)}개도 함께 거들어." if aux else ""
            seat = (f"여기엔 {', '.join(mains)}이 앉아 있고, " if mains
                    else "여기엔 주성이 비어 있고, ")
            ziwei_story = (f"자미로 풀어보면, 이 시기 중심은 {pal['name']} 자리야. "
                           f"{seat}{main_story}.{aux_note} "
                           f"같은 무리 자리로는 {', '.join(mates)} 궁이 딸려와.")
        else:
            if not pals:
                ziwei = "시간 미상이라 제외"
                pname = ""
                ziwei_story = "시간 미상이라 자미 궁 흐름은 제외, 사주 대운으로 봐."
            else:
                ziwei = "해당 궁 없음"
                pname = ""
                ziwei_story = "자미로 봐도 이 구간은 빈틈없이 잔잔한 때야."
        mid = lo + 5
        jl = A.planet_longitude(A.day_number(birth.year + mid, 7, 1, 12.0),
                                "jupiter")
        slon = A.planet_longitude(A.day_number(birth.year + mid, 7, 1, 12.0),
                                  "saturn")
        js, ss = _sign(jl), _sign(slon)
        astro_story = (f"하늘의 큰 별들로 보면 {mid}세 무렵 목성은 {js}, 토성은 {ss}에 머물러. "
                       f"목성이 {js}에 있다는 건 {JUP_TALK[SIGN_ELEMENT[js]]}, "
                       f"토성이 {ss}라는 건 {SAT_TALK[SIGN_ELEMENT[ss]]}")
        love = ("배우자궁 대운이 겹쳐 만남이 무르익기 쉬운 때야"
                if overlap(spouse_dx, lo + 1, hi + 1)
                else f"배우자궁 대운은 {spouse_dx[0]}~{spouse_dx[1]}세에 도래해서 그때가 무르익는 때야"
                if spouse_dx else "배우자궁 흐름은 잔잔한 때야")
        career = ("관록궁 대운이 겹쳐 일에서 치고 나가기 좋은 때야"
                  if overlap(guanlu_dx, lo + 1, hi + 1)
                  else f"관록궁 대운은 {guanlu_dx[0]}~{guanlu_dx[1]}세에 도래해서 그때가 뻗는 때야"
                  if guanlu_dx else "관록궁 흐름은 잔잔한 때야")
        money = ("재백궁 대운이 겹쳐 돈이 모이기 쉬운 때야"
                 if overlap(caibo_dx, lo + 1, hi + 1)
                 else f"재백궁 대운은 {caibo_dx[0]}~{caibo_dx[1]}세에 도래해서 그때가 모이는 때야"
                 if caibo_dx else "재백궁 흐름은 잔잔한 때야")
        health = ("질액궁 대운이 겹쳐 몸을 돌보기 좋은 때야"
                  if overlap(jilak_dx, lo + 1, hi + 1)
                  else f"질액궁 대운은 {jilak_dx[0]}~{jilak_dx[1]}세에 도래해서 그때 몸을 챙기면 좋아"
                  if jilak_dx else "질액궁 흐름은 잔잔한 때야")
        if not pals:
            love = "배우자궁 흐름은 시간 미상이라 제외"
            career = "관록궁 흐름은 시간 미상이라 제외"
            money = "재백궁 흐름은 시간 미상이라 제외"
            health = "질액궁 흐름은 시간 미상이라 제외"
        parts = [f"{lo}~{hi}세 이야기: {saju} 시기와 {ziwei} 시기가 겹치는 때야.",
                 saju_story, ziwei_story, astro_story,
                 f"그래서 이 시기 연애는 {love}. 일은 {career}. 돈은 {money}. 몸은 {health}."]
        # 자미 궁이 없으면(시간 미상 등) '시기와  시기' 처럼 빈칸이 생겨서 나눠 쓴다
        short = ((f"지금 {lo}~{hi}세는 {saju} 시기와 {pname} 시기가 겹치는 때야. " if pname
                  else f"지금 {lo}~{hi}세는 {saju} 시기야. ")
                 + "아래 연대별 토글을 펼치면 점술가 풀이가 나와.")
        decades.append({"range": (lo, hi), "saju": saju, "ziwei": ziwei,
                        "palace": pname, "parts": parts, "short": short,
                        "line": " / ".join(parts)})
        a += 10

    # 시기별 요약 (초년·중년·말년)
    phases = []
    for name, plo, phi in (("초년", 0, 29), ("중년", 30, 59), ("말년", 60, 89)):
        if not pals:
            phases.append({"name": name,
                           "line": f"{name}({plo}~{phi}세): 시간 미상이라 자미 궁 흐름은 제외, 사주 대운으로 봐"})
            continue
        pls = [p for p in pals if p["daxian"]
               and not (p["daxian"][1] < plo + 1 or p["daxian"][0] > phi + 1)]
        lu = sum(1 for p in pls for h in p["hua"].values() if h == "록")
        quan = sum(1 for p in pls for h in p["hua"].values() if h == "권")
        ji = sum(1 for p in pls for h in p["hua"].values() if h == "기")
        bits = []
        if lu or quan:
            bits.append(f"복과 힘의 기운이 {lu + quan}곳에 머물러 펼치기 좋은 때야")
        if ji:
            bits.append(f"막힘과 과제가 {ji}곳에 있어 정리하고 내실을 다지기 좋은 때야")
        if not bits:
            bits.append("큰 변화 없이 잔잔하게 가는 때야")
        areas = sorted({p["name"] for p in pls
                        if p["name"] in ("관록", "재백", "부처(배우자)", "명궁", "질액")})
        if areas:
            bits.append(f"{', '.join(areas)} 궁이 움직이는 시기")
        phases.append({"name": name,
                       "line": f"{name}({plo}~{phi}세): " + ", ".join(bits)})

    # 연도별 (올해 기준 2년 전부터 8년 뒤까지)
    years = []
    y0 = today.year
    _lyb0 = zw["lunar_year_branch"] if zw else (y0 - 4) % 12
    _xtrio = next(t for t in ((8, 0, 4), (2, 6, 10), (5, 9, 1), (11, 3, 7))
                  if _lyb0 in t)
    _xstart = XIAOXIAN_AT[_xtrio]
    prev_j = prev_s = None
    for y in range(y0 - 2, y0 + 9):
        age = y - birth.year
        ys, yb = (y - 4) % 10, (y - 4) % 12
        pal = next((p for p in pals if p["branch"] == yb), None)
        sihua = SIHUA[ys]
        jlon = A.planet_longitude(A.day_number(y, 7, 1, 12.0), "jupiter")
        slon = A.planet_longitude(A.day_number(y, 7, 1, 12.0), "saturn")
        js, ss = _sign(jlon), _sign(slon)
        notes = []
        ygod = ten_god(ds, ys)
        yrels = branch_relation(db, yb)
        notes.append(f"풀이: {STEMS_KR[ys]}년 기운은 나에게 {GOD_SHORT[ygod]}, "
                     f"{BRANCHES_KR[yb]}지는 일지와 {_rel_text(yrels)}")
        if pal is not None and pal["name"] in ("명궁", "관록", "재백", "부처(배우자)"):
            notes.append(f"{pal['name']}에 유년이 겹치는 해")
        if prev_j is not None and js != prev_j:
            notes.append("목성이 별자리를 옮기는 해")
        if prev_s is not None and ss != prev_s:
            notes.append("토성이 별자리를 옮기는 해")
        prev_j, prev_s = js, ss
        _xu = y - birth.year + 1
        _xb = (_xstart + (_xu - 1)) % 12 if sex == "male" else (_xstart - (_xu - 1)) % 12
        _xp = next((p for p in pals if p["branch"] == _xb), None)
        line = (f"{y}년 | 그해 만 {age}세 | {ganzhi_str(ys, yb)} | "
                f"유년 {pal['name'] if pal else '제외(시간 미상)'} | "
                f"사화 록{sihua[0]} 권{sihua[1]} 과{sihua[2]} 기{sihua[3]} | "
                f"목성 {js} | 토성 {ss} | 소운 {_xp['name'] if _xp else '제외(시간 미상)'}"
                + (f" | {'; '.join(notes)}" if notes else ""))
        years.append({"year": y, "age": age, "line": line})

    # 연대 표(0~89세) 밖이면 가장 가까운 연대로 본다. 예전엔 90세 이상이면
    # StopIteration 으로 리포트 전체가 죽었다.
    age_now = min(max(y0 - birth.year, decades[0]["range"][0]), decades[-1]["range"][1])
    cur_dec = next(d for d in decades if d["range"][0] <= age_now <= d["range"][1])
    return {"decades": decades, "years": years, "phases": phases,
            "current": cur_dec}
