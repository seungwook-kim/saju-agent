"""synthesis.py, 정통 계산 종합 엔진 (로컬·결정적).

사주(진태양시·실측절기·대운·신살) + 자미두수(정통 명반·사화·대운소운·유년)
+ 점성술(실측 차트·하우스·어스펙트)을 묶어 인연 아키타입 상세 리딩을 만든다.
서술은 전통 해석에 근거한 경향·흐름체.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime

from .manseryuk import (four_pillars, dayun, shensha, year_pillar, day_pillar,
                        STEMS_KR, BRANCHES_KR, STEM_ELEMENT, BRANCH_ELEMENT,
                        ganzhi_str)
from .rules import ten_god, love_score, headline, branch_relation
from .narrate import _rel_text, GOD_SHORT
from .match import (SPOUSE_GOD, TWELVE_STAGES, STAGE_NAMES, STAGE_LOVE,
                    DOHWA_CHARM, HONGYEOM, JINDOHWA_DAY, SPOUSE_STAR,
                    VENUS_DETAIL, MOON_NEED, BRANCH_BONQI, dohwa_info)
from .ziwei import ziwei_chart
from .astro import astro_chart, SIGN_ELEMENT
from .lifetime import lifetime_reading
from .story import build_stories
from .domains import (career_score, money_score, total_score, band_headline,
                      CAREER_TIPS, CAREER_AVOID, MONEY_TIPS, MONEY_AVOID,
                      CAREER_STAR, MONEY_STAR, _pick, _element_reasons)


def _stage(day_stem: int, day_branch: int) -> str:
    return STAGE_NAMES[TWELVE_STAGES[day_stem].index(day_branch)]


def detailed_reading(birth: date, hour: int | None, minute: int, sex: str,
                     city: str, today: date) -> dict:
    _unknown = hour is None
    _notice = ("시간 미상이라 시주는 제외하고 3기둥으로 봐. "
               "자미두수 명반·하우스·상승궁은 제외하고, "
               "대운 시작나이와 달은 정오 기준 어림이야.")
    natal = four_pillars(birth, hour, minute, city)
    ds = natal["ilgan_stem"]
    yb, mb, db = (natal["pillars"][k][1]
                  for k in ("year", "month", "day"))
    _hb = natal["pillars"]["hour"][1]
    branches = [b for b in (yb, mb, db, _hb) if b is not None]
    _stems3 = [natal["pillars"][k][0] for k in ("year", "month", "day")]
    _hs = natal["pillars"]["hour"][0]
    stems = [s for s in (_stems3 + [_hs]) if s is not None]

    # 1. 배우자궁 십성
    god = ten_god(ds, BRANCH_BONQI[db])
    sg = SPOUSE_GOD[god]
    side = sg["m"] if sex == "male" else sg["f"]

    # 2. 배우자성
    want = {"정재", "편재"} if sex == "male" else {"정관", "편관"}
    spots: list[str] = []
    for nm, s in zip(("년", "월", "일", "시"), stems):
        if ten_god(ds, s) in want:
            spots.append(f"{nm}간")
    for nm, b in zip(("년", "월", "일", "시"), branches):
        if ten_god(ds, BRANCH_BONQI[b]) in want:
            spots.append(f"{nm}지")
    if spots:
        star_line = (f"배우자성({'재성' if sex == 'male' else '관성'})이 "
                     f"{', '.join(spots)}에 보여 인연의 기회가 엮이기 쉬운 구조")
    else:
        star_line = (f"배우자성({'재성' if sex == 'male' else '관성'})이 원국에 숨어 있어 "
                     "대운·세운에서 들어올 때 인연이 움직이기 쉬운 구조")

    # 3. 십이운성
    stage = _stage(ds, db)

    # 4. 도화·홍염
    dh = dohwa_info(branches)
    dh_lines: list[str] = []
    for ch, at in dh["chars"].items():
        inner = "장내도화(사회적 인기)" if any(a in ("년지", "월지") for a in at) else ""
        outer = "장외도화(사적 매력)" if any(a in ("일지", "시지") for a in at) else ""
        dh_lines.append(f"도화({BRANCHES_KR[ch]})가 {', '.join(at)}에, "
                        + "·".join(x for x in (inner, outer) if x) + f" / {DOHWA_CHARM[ch]}")
    if not dh_lines:
        dh_lines.append("원국 도화(인연을 끌어당기는 별)는 비어 있어. "
                        "대신 홍염살과 올해 도화운, 만날 자리 TOP3으로 인연의 문을 봐.")
    hong = HONGYEOM[ds]
    hong_at = [nm for nm, b in zip(("년지", "월지", "일지", "시지"), branches) if b == hong]
    hong_line = (f"홍염살({BRANCHES_KR[hong]})이 {', '.join(hong_at)}에 있어 가까워질수록 끌리는 흐름"
                 if hong_at else f"홍염살({BRANCHES_KR[hong]})은 원국에 없어 은근한 끌림은 운에서 들어오는 흐름")
    jindo = (ds, db) in JINDOHWA_DAY

    # 올해(세운) 도화
    tyb = year_pillar(datetime(today.year, today.month, today.day, 12, 0))[1]
    from .match import DOHWA_MAP
    my_dh_chars = {d for base, d in DOHWA_MAP if (yb in base or db in base)}
    timing = ("올해는 도화운의 해, 평소보다 만남·소개가 늘어나기 쉬운 흐름"
              if tyb in my_dh_chars else
              "올해는 도화운보다 내실을 다지기 좋은 흐름, 매력은 일상의 자리에서 쌓이는 흐름")

    # 5. 자미두수 정통 (시간 미상이면 명반 배치 불가)
    zw = ziwei_chart(birth, hour, minute, sex, city)
    if zw is None:
        from .lunar import solar_to_lunar as _s2l
        _ly, _lm, _ld, _lp = _s2l(birth.year, birth.month, birth.day)
        lunar_line = (f"음력 {_ly}년 {_lm}월 {_ld}일{' (윤달)' if _lp else ''} · "
                      "시간 미상이라 진태양시 미표기")
        lunar_line_safe = "시간 미상이라 진태양시 미표기"
        guo_line = "시간 미상이라 자미두수 명반 배치 불가"
        sihua_lines = ["시간 미상이라 생년사화 제외"]
        daxian_line = "시간 미상이라 자미 대운 제외, 사주 대운으로 봐"
        liunian_line = "시간 미상이라 유년 제외"
        st = {"look": "시간 미상이라 제외", "mind": "시간 미상이라 제외",
              "job": "시간 미상이라 제외", "meet": "시간 미상이라 제외",
              "tip": "시간 미상이라 제외"}
        _zw_main, _zw_borrowed, _zw_peach, _zw_ming = (
            "시간 미상이라 제외", False, [], "시간 미상이라 제외")
    else:
        st = SPOUSE_STAR.get(zw["spouse_main"], SPOUSE_STAR["천동"])
        ly, lm, ld, lp = zw["lunar"]
        lunar_line = (f"음력 {ly}년 {lm}월 {ld}일{' (윤달)' if lp else ''} · "
                      f"진태양시 {zw['true_solar']} (보정 {zw['corr_min']}분)"
                      + (" · 야자시로 다음날 자시 적용" if zw["night_zi"] else ""))
        lunar_line_safe = (f"진태양시 보정 {zw['corr_min']}분 적용"
                           + (" · 야자시로 다음날 자시 적용" if zw["night_zi"] else ""))
        guo_name = {2: "수이국", 3: "목삼국", 4: "금사국", 5: "토오국", 6: "화육국"}[zw["guo"]]
        guo_line = (f"오행국 {guo_name} · 명궁 주성 {zw['ming_main']} · "
                    f"신궁 {zw['shengong']} · 명주 {zw['mingzhu']} · 신주 {zw['shenzhu']}")
        sihua_lines = []
        for hua, star in zw["sihua"].items():
            pal = next(p["name"] for p in zw["palaces"] if star in p["stars"])
            sihua_lines.append(f"생년 화{hua}({star}) → {pal}")
        cur_du = next((p for p in zw["palaces"]
                       if p["daxian"] and p["daxian"][0] <= zw["xusui"] <= p["daxian"][1]),
                      None)
        daxian_line = ""
        if cur_du:
            mains = [s for s in cur_du["stars"]
                     if s in ("자미", "천기", "태양", "무곡", "천동", "염정",
                              "천부", "태음", "탐랑", "거문", "천상", "천량", "칠살", "파군")]
            daxian_line = (f"현재 대운(세는나이 {zw['xusui']}세) {cur_du['name']}"
                           f"({cur_du['daxian'][0]}~{cur_du['daxian'][1]}세, 주성 {', '.join(mains) or '무주성'})")
        ln = zw["liunian"]
        liunian_pal = next(p["name"] for p in zw["palaces"] if p["liunian"])
        liunian_line = (f"올해 유년명궁 {ln['branch']}({liunian_pal}) · "
                        f"유년사화 록{ln['sihua']['록']} 권{ln['sihua']['권']} "
                        f"과{ln['sihua']['과']} 기{ln['sihua']['기']}")
        _zw_main, _zw_borrowed, _zw_peach, _zw_ming = (
            zw["spouse_main"], zw["spouse_borrowed"], zw["peach"], zw["ming_main"])

    # 6. 점성술 실측 (시간 미상이면 정오 기준 위치만, 하우스·상승궁 제외)
    ast = astro_chart(birth, hour, today, minute, city)
    venus = ast["venus"]["sign"]
    moon = ast["moon"]["sign"]
    vd = VENUS_DETAIL[venus]
    if _unknown:
        houses_line = "시간 미상이라 하우스 제외, 행성 자리만 봐"
        aspects_line = "; ".join(ast["aspects"]) or "주요 어스펙트 없음"
        asc_line = ("상승궁·MC 제외 (시간 미상)"
                    + (" · " + " / ".join(ast["cusp_notes"]) if ast["cusp_notes"] else "")
                    + (" · " + " / ".join(ast["retro_notes"]) if ast["retro_notes"] else ""))
    else:
        houses_line = " · ".join(f"{k} {v}하우스"
                                 for k, v in ast["houses"].items())
        aspects_line = "; ".join(ast["aspects"]) or "주요 어스펙트 없음"
        asc_line = (f"상승궁 {ast['ascendant']} · MC {ast['mc']}"
                    + (" · " + " / ".join(ast["cusp_notes"]) if ast["cusp_notes"] else "")
                    + (" · " + " / ".join(ast["retro_notes"]) if ast["retro_notes"] else ""))

    # 7. 사주 대운·신살
    du = dayun(birth, hour, minute, sex, city)
    dayun_line = (f"사주 대운 {du['direction']} · {du['start_age']}세에 대운 시작 · "
                  f"현재 {du['current']['ganzhi']}운({du['current']['from']}~{du['current']['to']}세)"
                  + (" (시간 미상이라 정오 기준 어림)" if _unknown else ""))
    sh = shensha(birth, hour, minute, city)
    shensha_lines = [f"{k}: {v}" for k, v in sh.items()]

    # 8. 만남 TOP3
    VENUS_MEET = {"양자리": "액티비티·스포츠 모임", "사자자리": "액티비티·스포츠 모임",
                  "사수자리": "액티비티·스포츠 모임", "황소자리": "맛집·취미 클래스",
                  "처녀자리": "맛집·취미 클래스", "염소자리": "맛집·취미 클래스",
                  "쌍둥이자리": "토크 모임·스터디", "천칭자리": "토크 모임·스터디",
                  "물병자리": "토크 모임·스터디", "게자리": "감성 모임·전시",
                  "전갈자리": "감성 모임·전시", "물고기자리": "감성 모임·전시"}
    cands = [sg["meet"]] if _unknown else [sg["meet"], st["meet"]]
    cands += [f"{DOHWA_CHARM[next(iter(dh['chars']))].split(', ')[0]}이 통하는 자리"
              if dh["chars"] else "지인의 소개 자리",
              VENUS_MEET[venus],
              f"{sg['job'].split(' 등')[0]} 관련 모임"]
    seed = f"{birth.isoformat()}|match"
    order = sorted(range(len(cands)),
                   key=lambda i: hashlib.sha256(f"{seed}|{i}".encode()).hexdigest())
    meet_top3 = [cands[i] for i in order[:3]]

    # 9. 영역별 오늘 운세 (연애·직장·금전·총운)
    ts, tb = day_pillar(today)
    love_sc, love_reasons, _elem = love_score(ds, branches, ts, tb, today.isoformat())
    love_head = headline(love_sc)
    career_sc, career_reasons, _e2 = career_score(ds, branches, ts, tb, today.isoformat())
    money_sc, money_reasons, _e3 = money_score(ds, branches, ts, tb, today.isoformat())

    def _palace_slice(palace_name: str) -> list[str]:
        if zw is None:
            return ["시간 미상이라 삼방사정 제외"]
        target = next(p for p in zw["palaces"] if p["name"] == palace_name)
        b = target["branch"]
        out = []
        for tag, pb in (("본궁", b), ("삼방", (b + 4) % 12),
                        ("삼방", (b + 8) % 12), ("대궁", (b + 6) % 12)):
            p = next(x for x in zw["palaces"] if x["branch"] == pb)
            hua = ",".join(f"{s}화{h}" for s, h in p["hua"].items())
            out.append(f"{tag} {p['name']}({p['stem_kr']}{p['branch_kr']}): "
                       f"{','.join(p['stars'])}" + (f" [{hua}]" if hua else ""))
        return out

    career_palaces = _palace_slice("관록")
    money_palaces = _palace_slice("재백")

    def _palace_main(palace_name: str) -> str:
        if zw is None:
            return "시간 미상이라 제외"
        stars = next(p["stars"] for p in zw["palaces"] if p["name"] == palace_name)
        mains = [s for s in stars if s in CAREER_STAR]
        return mains[0] if mains else "무주성"

    guanlu_main = _palace_main("관록")
    caibo_main = _palace_main("재백")

    def _spots(want: set[str]) -> list[str]:
        out: list[str] = []
        for nm, s in zip(("년", "월", "일", "시"), stems):
            if ten_god(ds, s) in want:
                out.append(f"{nm}간")
        for nm, b in zip(("년", "월", "일", "시"), branches):
            if ten_god(ds, BRANCH_BONQI[b]) in want:
                out.append(f"{nm}지")
        return out

    guan_spots = _spots({"정관", "편관"})
    cai_spots = _spots({"정재", "편재"})
    guanlu_line = ("시간 미상이라 관록궁 주성 제외" if _unknown else
                   f"관록궁 주성 {guanlu_main}, "
                   + (CAREER_STAR.get(guanlu_main, "자기 역할을 찾기 좋은 흐름")))
    caibo_line = ("시간 미상이라 재백궁 주성 제외" if _unknown else
                  f"재백궁 주성 {caibo_main}, "
                  + (MONEY_STAR.get(caibo_main, "돈의 리듬을 살피기 좋은 흐름")))
    guan_line2 = ("원국 관성(직장 기운)이 " + (", ".join(guan_spots) + "에 보여 일의 기회가 엮이기 쉬운 구조"
                  if guan_spots else "숨어 있어 운에서 들어올 때 일이 움직이기 쉬운 구조"))
    cai_line2 = ("원국 재성(돈 기운)이 " + (", ".join(cai_spots) + "에 보여 돈의 기회가 엮이기 쉬운 구조"
                 if cai_spots else "숨어 있어 운에서 들어올 때 돈이 움직이기 쉬운 구조"))

    if zw is None:
        cur_du_pal = None
        liunian_branch = tyb
    else:
        cur_du_pal = next((p for p in zw["palaces"]
                           if p["daxian"] and p["daxian"][0] <= zw["xusui"] <= p["daxian"][1]),
                          None)
        liunian_branch = BRANCHES_KR.index(zw["liunian"]["branch"])
    daxian_hua = list(cur_du_pal["hua"].values()) if cur_du_pal else []
    total_sc, total_reasons, _e4, keywords = total_score(
        ds, branches, ts, tb, love_sc, career_sc, money_sc,
        daxian_hua, liunian_branch, today.isoformat())

    career = {"score": career_sc, "head": band_headline(career_sc, "career"),
              "reasons": career_reasons,
              "tips": _pick(seed + "|career", CAREER_TIPS, 3),
              "avoid": _pick(seed + "|career-avoid", CAREER_AVOID, 1)[0],
              "guanlu_main": guanlu_main, "guanlu_line": guanlu_line,
              "guan_line": guan_line2, "palaces": career_palaces}
    money = {"score": money_sc, "head": band_headline(money_sc, "money"),
             "reasons": money_reasons,
             "tips": _pick(seed + "|money", MONEY_TIPS, 3),
             "avoid": _pick(seed + "|money-avoid", MONEY_AVOID, 1)[0],
             "caibo_main": caibo_main, "caibo_line": caibo_line,
             "cai_line": cai_line2, "palaces": money_palaces}
    total = {"score": total_sc, "head": band_headline(total_sc, "total"),
             "reasons": total_reasons, "keywords": keywords,
             "love": love_sc, "career": career_sc, "money": money_sc}

    # 10. 영역별 심화 (원국 분포·대운 테마·유년 관계·행성)
    dist_elements = {"목": 0, "화": 0, "토": 0, "금": 0, "수": 0}
    for _s in stems:
        dist_elements[STEM_ELEMENT[_s]] += 1
    for _b in branches:
        dist_elements[BRANCH_ELEMENT[_b]] += 1
    _top = max(dist_elements, key=lambda e: dist_elements[e])
    dist_lines = [
        "원국 분포: " + ", ".join(f"{e} {dist_elements[e]}개" for e in ("목", "화", "토", "금", "수")),
        "원국 십신: " + ", ".join(
            [f"{nm}간 {ten_god(ds, s)}" for nm, s in zip(("년", "월", "일", "시"), stems)] +
            [f"{nm}지 {ten_god(ds, BRANCH_BONQI[b])}" for nm, b in zip(("년", "월", "일", "시"), branches)]),
        f"{len(stems) + len(branches)}자리 중 {_top} 기운이 {dist_elements[_top]}개로 가장 많아. "
        f"사주에서는 이렇게 기운의 치우침과 균형을 함께 본다.",
    ]
    _cur = du["current"]
    _du_stem = STEMS_KR.index(_cur["ganzhi"][0])
    _du_god = ten_god(ds, _du_stem)
    _pos = ast["positions"]
    _hou = ast["houses"] if not _unknown else {}
    _dub = BRANCHES_KR.index(_cur["ganzhi"][1])
    _du_line_c = (f"지금 대운({_cur['ganzhi']}운)은 천간 {_cur['ganzhi'][0]}이 나에게 "
                  f"{GOD_SHORT[_du_god]} 기운이야. 10년 테마로 일의 흐름이 이렇게 흘러.")
    _du_line_n = (f"지금 대운({_cur['ganzhi']}운)은 천간 {_cur['ganzhi'][0]}이 나에게 "
                  f"{GOD_SHORT[_du_god]} 기운이야. 10년 돈의 테마로 이렇게 흘러.")
    _du_land_c = (f"지금 대운 지지 {_cur['ganzhi'][1]}와 일지는 "
                  f"{_rel_text(branch_relation(_dub, db))} 사이야. 10년 일의 터가 이렇게 놓여 있어.")
    if _unknown:
        _lyb = tyb
        career_extra = [
            _du_line_c,
            _du_land_c,
            "시간 미상이라 관록궁 위치 관계는 제외.",
            f"토성(책임과 과제)은 {_pos['saturn']['sign']}에 머물러 있어. "
            "시간 미상이라 하우스 칸은 제외.",
        ]
        money_extra = [
            _du_line_n,
            "시간 미상이라 재백궁 위치 관계는 제외.",
            f"금성(취향과 돈감각)은 {_pos['venus']['sign']}에 머물러 있어. "
            "시간 미상이라 하우스 칸은 제외.",
            f"목성(확장과 기회)은 {_pos['jupiter']['sign']}에 머물러 넓히는 중이야.",
        ]
        love_extra = ["시간 미상이라 유년궁 관계는 제외."]
    else:
        _lyb = BRANCHES_KR.index(zw["liunian"]["branch"])
        _guanlu_b = next(p["branch"] for p in zw["palaces"] if p["name"] == "관록")
        _caibo_b = next(p["branch"] for p in zw["palaces"] if p["name"] == "재백")
        _spouse_b = next(p["branch"] for p in zw["palaces"] if p["name"] == "부처(배우자)")
        career_extra = [
            _du_line_c,
            _du_land_c,
            f"올해 유년 {BRANCHES_KR[_lyb]}와 관록궁은 "
            f"{_rel_text(branch_relation(_lyb, _guanlu_b))} 사이야.",
            f"토성(책임과 과제)은 {_pos['saturn']['sign']}에 머물러 "
            f"{_hou['토성']}번 하우스 칸에서 다잡아주는 중이야.",
            f"수성(말과 실무)은 {_pos['mercury']['sign']} {_hou['수성']}번 하우스 칸에서 오가고 있어.",
        ]
        money_extra = [
            _du_line_n,
            f"올해 유년 {BRANCHES_KR[_lyb]}와 재백궁은 "
            f"{_rel_text(branch_relation(_lyb, _caibo_b))} 사이야.",
            f"지금 대운 지지 {_cur['ganzhi'][1]}와 재백궁은 "
            f"{_rel_text(branch_relation(_dub, _caibo_b))} 사이야. 10년 돈의 그릇이 이렇게 놓여 있어.",
            f"금성(취향과 돈감각)은 {_pos['venus']['sign']} {_hou['금성']}번 하우스 칸에서 가꾸는 중이야.",
            f"목성(확장과 기회)은 {_pos['jupiter']['sign']} {_hou['목성']}번 하우스 칸에서 넓히는 중이야.",
        ]
        love_extra = [
            f"올해 유년 {BRANCHES_KR[_lyb]}와 부처궁은 "
            f"{_rel_text(branch_relation(_lyb, _spouse_b))} 사이야.",
        ]

    # 10b. 사주 대운 전체표 (8스텝, 각 대운의 천간 관계 풀이)
    dayun_full = []
    for _st in du["steps"]:
        _ds2 = STEMS_KR.index(_st["ganzhi"][0])
        _db2 = BRANCHES_KR.index(_st["ganzhi"][1])
        _g2 = ten_god(ds, _ds2)
        dayun_full.append(
            f"{_st['ganzhi']}운({_st['from']}~{_st['to']}세): 천간 {_st['ganzhi'][0]}은 나에게 "
            f"{GOD_SHORT[_g2]} 기운, 지지 {_st['ganzhi'][1]}은 일지와 "
            f"{_rel_text(branch_relation(db, _db2))} 사이야.")

    # 11. 월별 12개월 영역 운세 (월운, 해당 연도 1~12월)
    from datetime import datetime as _dt
    from .manseryuk import month_pillar as _mp, ganzhi_str as _gz
    from .domains import CAREER_GOD_LINE as _CGL, MONEY_GOD_LINE as _MGL
    monthly = []
    for _m in range(1, 13):
        _ms, _mb = _mp(_dt(today.year, _m, 15, 12, 0))
        _seedm = f"{today.year}-{_m:02d}"
        _ls, _, _ = love_score(ds, branches, _ms, _mb, _seedm)
        _cs, _, _ = career_score(ds, branches, _ms, _mb, _seedm)
        _ns, _, _ = money_score(ds, branches, _ms, _mb, _seedm)
        _godm = ten_god(ds, _ms)
        _eline_c = _element_reasons(STEM_ELEMENT[ds], STEM_ELEMENT[_ms], "일")[1][0]
        _eline_n = _element_reasons(STEM_ELEMENT[ds], STEM_ELEMENT[_ms], "돈")[1][0]
        _best = max((("연애", _ls), ("직장", _cs), ("금전", _ns)),
                    key=lambda t: t[1])[0]
        monthly.append({
            "month": _m, "ganzhi": _gz(_ms, _mb).split(" ")[0],
            "love": _ls, "career": _cs, "money": _ns, "god": _godm,
            "line": f"{_m}월 {_gz(_ms, _mb).split(' ')[0]}: "
                    f"연애 {_ls}점·직장 {_cs}점·금전 {_ns}점, 으뜸은 {_best}",
            "career_line": f"{_m}월 {_gz(_ms, _mb).split(' ')[0]}({_godm}): "
                           f"{_CGL[_godm]} ({_cs}점). {_eline_c}",
            "money_line": f"{_m}월 {_gz(_ms, _mb).split(' ')[0]}({_godm}): "
                          f"{_MGL[_godm]} ({_ns}점). {_eline_n}",
        })

    from .advise import build_advice
    from .manseryuk import STEMS_KR as _SK, STEM_ELEMENT as _SE
    from .yongsin import analyze as _analyze_yongsin, ILGAN_CHARACTER as _ILGAN_C
    from .yongsin import narrate_dayun_steps as _narrate_dayun
    from datetime import timedelta as _td
    adv_in = build_advice(_SK[ds], _elem, today, birth)
    natal_min = {"ilgan": _SK[ds], "ilgan_element": _SE[ds]}
    _du_full = dayun(birth, hour, minute, sex, city)
    _ys = {
        "ilgang": _ILGAN_C[_SK[ds]],
        "analysis": _analyze_yongsin(ds, stems, branches, [BRANCH_BONQI[b] for b in branches], mb),
        "dayun_narr": _narrate_dayun(_du_full["steps"], ds, db),
    }
    ilun = []
    for _i in range(30):
        _d = today + _td(days=_i)
        _dss, _dbb = day_pillar(_d)
        _seedi = f"ilun-{_d.isoformat()}"
        _l1, _, _ = love_score(ds, branches, _dss, _dbb, _seedi)
        _c1, _, _ = career_score(ds, branches, _dss, _dbb, _seedi)
        _n1, _, _ = money_score(ds, branches, _dss, _dbb, _seedi)
        _g1 = ten_god(ds, _dss)
        _best1 = max((("연애", _l1), ("직장", _c1), ("금전", _n1)),
                     key=lambda t: t[1])[0]
        ilun.append({
            "date": _d.isoformat(), "ganzhi": ganzhi_str(_dss, _dbb),
            "line": f"{_d.month}/{_d.day} | {ganzhi_str(_dss, _dbb)} | "
                    f"연애 {_l1} | 직장 {_c1} | 금전 {_n1} | {_g1} | 으뜸 {_best1}",
        })

    import re as _re_m
    _mk = today.strftime("%Y-%m")
    _mrows = [r for r in ilun if r["date"].startswith(_mk)]

    def _mnums(r):
        _mm = _re_m.search(r"연애 (\d+) \| 직장 (\d+) \| 금전 (\d+)", r["line"])
        return tuple(map(int, _mm.groups())) if _mm else (0, 0, 0)

    if _mrows:
        _mtot = [sum(_mnums(r)) for r in _mrows]
        _mbi = max(range(len(_mrows)), key=lambda i: _mtot[i])
        _mbest = _mrows[_mbi]
        _mn = len(_mrows)
        _mal = sum(_mnums(r)[0] for r in _mrows) // _mn
        _mac = sum(_mnums(r)[1] for r in _mrows) // _mn
        _man = sum(_mnums(r)[2] for r in _mrows) // _mn
        _mue = {d: sum(f"으뜸 {d}" in r["line"] for r in _mrows)
                for d in ("연애", "직장", "금전")}
        _mued = max(_mue, key=lambda d: _mue[d])
        month_line = (
            f"이번 달({today.month}월) {len(_mrows)}일 평균은 "
            f"연애 {_mal}·직장 {_mac}·금전 {_man}점이야. "
            f"가장 좋은 날은 {_mbest['line'].split(' | ')[0]}({_mbest['ganzhi']})이야. "
            f"으뜸이 가장 많은 건 {_mued}({_mue[_mued]}일)이라 "
            f"이 달은 {_mued} 쪽에 힘이 실리는 흐름이야.")
    else:
        month_line = "이번 달 표가 비어 있어."

    result = {
        "god": god, "god_rel": sg["rel"], "side": side,
        "god_vibe": sg["vibe"], "god_tip": sg["tip"], "god_job": sg["job"],
        "star_line": star_line,
        "stage": stage, "stage_love": STAGE_LOVE[stage],
        "dohwa_lines": dh_lines, "hong_line": hong_line,
        "jindohwa": jindo, "timing": timing,
        "lunar_line": lunar_line, "lunar_line_safe": lunar_line_safe,
        "guo_line": guo_line,
        "ziwei_main": _zw_main, "ziwei_detail": st,
        "ziwei_borrowed": _zw_borrowed, "peach": _zw_peach,
        "sihua_lines": sihua_lines, "daxian_line": daxian_line,
        "liunian_line": liunian_line, "ming_main": _zw_ming,
        "hour_unknown": _unknown, "time_notice": _notice,
        "venus": venus, "venus_detail": vd,
        "moon": moon, "moon_need": MOON_NEED[moon],
        "asc_line": asc_line, "houses_line": houses_line,
        "aspects_line": aspects_line,
        "dayun_line": dayun_line, "shensha_lines": shensha_lines,
        "meet_top3": meet_top3, "astro": ast, "ziwei": zw,
        "career": career, "money": money, "total": total,
        "dist": dist_lines,
        "career_extra": career_extra, "money_extra": money_extra,
        "love_extra": love_extra, "monthly": monthly,
        "dayun_full": dayun_full, "yongsin": _ys, "ilun": ilun,
        "month_line": month_line,
        "lifetime": lifetime_reading(birth, hour, minute, sex, city, today),
    }
    result["stories"] = build_stories(natal_min, result, adv_in, today)
    return result
