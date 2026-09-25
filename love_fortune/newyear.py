"""newyear.py, 신년운세 (다가올 한 해를 계산으로 미리 본다). 개인정보 없이 계산 결과만.

한 해를 네 층으로 본다.
- 사주 세운: 그해 간지가 나(일간)에게 어떤 십신인지, 배우자 자리(일지)와 어떤 사이인지,
  연애·일·돈 세운 시그널, 달마다(월운) 시그널
- 교운기: 그해나 앞뒤 해에 대운이 바뀌는지
- 자미두수 유년: 그해 유년 명궁이 내 명반의 어느 자리에 걸리는지, 그해 사화(록권과기)가 붙는 자리
- 점성술: 그해 목성(기회)·토성(과제)이 지나는 별자리와 내 하우스 (1월 1일·12월 31일 실제 위치),
  그해 목성·토성 회귀가 있는지
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from .astro import SIGN_ELEMENT, SIGNS
from .josa import j
from .manseryuk import BRANCHES_KR, STEMS_KR, year_pillar
from .narrate import GOD_SHORT, HOUSE_TALK, JUP_TALK, PALACE_TALK, SAT_TALK, _rel_text
from .rules import branch_relation, ten_god
from .signals import best, month_signals, year_signals

DOMAINS = ("love", "career", "money")
HUA_TALK = {"록": "복이 붙는", "권": "힘이 실리는", "과": "이름이 나는", "기": "막힘이 걸리는"}


def target_year(today: date) -> int:
    """9월부터는 다음 해를, 그 전에는 올해를 본다 (신년운세를 찾는 때에 맞춘다)."""
    return today.year + (1 if today.month >= 9 else 0)


def _sky(d: date) -> dict:
    from .transit import sky_on
    return sky_on(d)


def build(birth: date, hour: int | None, minute: int, sex: str, city: str, today: date,
          natal: dict, dayun: dict, natal_asc_sign: str | None, natal_lon: dict) -> dict:
    from .past import planet_returns
    from .ziwei import ziwei_chart

    y = target_year(today)
    ys, yb = year_pillar(datetime(y, 7, 1, 12))
    ds, db = natal["ilgan_stem"], natal["day_branch"]
    god = ten_god(ds, ys)
    rel = _rel_text(branch_relation(db, yb))
    sig = year_signals(natal, sex, y, 1)[0]
    months = month_signals(natal, sex, date(y, 1, 1), 12)
    age_end = y - birth.year - ((12, 31) < (birth.month, birth.day))

    # 교운기: 대운 시작일이 그해 앞뒤 1년 안에 있나
    dayun_note = ""
    for st in dayun["steps"]:
        when = birth + timedelta(days=round(st["from"] * 365.2425))
        if abs(when.year - y) <= 1:
            dayun_note = (f"{y}년은 {st['ganzhi']} 대운이 시작되는 해야 (만 {st['from']}세). 대운이 바뀌는 해라 "
                          "일·관계·사는 곳 같은 삶의 판이 새로 짜이기 쉬운 교운기로 봐." if when.year == y else
                          f"{y}년은 {st['ganzhi']} 대운이 바뀌는 앞뒤 해(교운기)에 걸려, 흐름이 바뀌는 기운이 느껴지기 쉬운 해야.")
            break

    # 자미두수 유년
    zw_part = None
    zw = ziwei_chart(birth, hour, minute, sex, city, date(y, 7, 1)) if hour is not None else None
    if zw:
        ln = zw["liunian"]
        pal = next(p["name"] for p in zw["palaces"] if p["liunian"])
        star_pal = {s: p["name"] for p in zw["palaces"] for s in p["stars"]}
        hua = []
        for h in ("록", "권", "과", "기"):
            star = ln["sihua"][h]
            where = star_pal.get(star)
            if where:
                hua.append(f"{y}년 {j(f'화{h}({HUA_TALK[h]} 기운)', '은')} {star}에 붙어 내 {where} 쪽에 걸려 "
                           f"({PALACE_TALK.get(where, '')}).")
        zw_part = {"palace": pal, "palace_talk": PALACE_TALK.get(pal, ""),
                   "line": f"{y}년 유년 명궁(그해의 중심 자리)은 내 {pal} 자리야. {PALACE_TALK.get(pal, '')}에 한 해의 무게가 실리기 쉬워.",
                   "hua": hua}

    # 목성·토성
    asc_idx = SIGNS.index(natal_asc_sign) if natal_asc_sign else None
    sky_lines = []
    a, b = _sky(date(y, 1, 1)), _sky(date(y, 12, 31))
    for key, name, talk in (("jupiter", "목성", JUP_TALK), ("saturn", "토성", SAT_TALK)):
        s0, s1 = a[key]["sign"], b[key]["sign"]
        signs = s0 if s0 == s1 else f"{s0}에서 {s1}"
        line = f"{y}년 {j(name, '은')} {j(signs, '을')} 지나. {talk[SIGN_ELEMENT[s1]]}로 보는 흐름이야."
        if asc_idx is not None:
            houses = sorted({(SIGNS.index(s) - asc_idx) % 12 + 1 for s in (s0, s1)})
            line += " 내 차트로는 " + ", ".join(f"{h}번 하우스({HOUSE_TALK[h]})" for h in houses) + " 칸을 지나가."
        rt = [r for r in planet_returns(natal_lon[key], key, date(y - 1, 1, 1), date(y + 1, 1, 1))
              if r["start"][:4] == str(y) or r["end"][:4] == str(y)]
        if rt:
            line += (f" 그리고 {y}년에는 {name} 회귀({rt[0]['start'][:7]}~{rt[-1]['end'][:7]})가 있어, "
                     + ("삶의 틀을 다시 짜는 때로 봐." if key == "saturn" else "넓히고 새 기회를 여는 때로 봐."))
        sky_lines.append(line)

    def mrows(dom: str) -> list[dict]:
        return [{"ym": f"{r['year']}-{r['month']:02d}", "label": f"{r['month']}월", "ganzhi": r["ganzhi"],
                 "tag": r["labels"][dom], "score": r["scores"][dom], "why": r["why"][dom]} for r in months]

    return {
        "year": y, "ganzhi": STEMS_KR[ys] + BRANCHES_KR[yb], "age": age_end,
        "god": f"{god}({GOD_SHORT[god]})",
        "rel": f"그해 지지 {j(BRANCHES_KR[yb], '은')} 내 일지(배우자 자리)와 {rel if rel.endswith('사이') else rel + ' 사이'}야.",
        "signals": {d: {"tag": sig["labels"][d], "why": list(sig["why"][d])} for d in DOMAINS},
        "months": {d: mrows(d) for d in DOMAINS},
        "best": {d: [f"{r['month']}월({r['ganzhi']})" for r in best(months, d)] for d in DOMAINS},
        "dayun_note": dayun_note,
        "ziwei": zw_part,
        "sky": sky_lines,
    }
