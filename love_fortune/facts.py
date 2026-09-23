"""facts.py, 탭별 '사실표'. 계산된 값만 담는다 (개인정보 없음).

챕터 풀이를 쓰는 AI 는 이 사실표에 있는 것만 근거로 쓸 수 있다. 화면의 표·캘린더·카드도
이 사실표로 그린다. 생년월일·태어난 시간·도시·이름은 넣지 않는다 (나이·성별 정도만).
"""
from __future__ import annotations

from datetime import date

from .manseryuk import BRANCHES_KR, STEMS_KR, four_pillars
from .natal_extra import animal_compat, natal_sinsal, pillars_detail
from .signals import best, month_signals, year_signals
from .synthesis import detailed_reading

ELEMENT_OF_STEM = {"갑": "목", "을": "목", "병": "화", "정": "화", "무": "토",
                   "기": "토", "경": "금", "신": "금", "임": "수", "계": "수"}


def build(birth: date, hour: int | None, minute: int, sex: str, city: str, target: date) -> dict:
    natal = four_pillars(birth, hour, minute, city)
    ma = detailed_reading(birth, hour, minute, sex, city, target)
    zw = ma["ziwei"]
    extra = natal_sinsal(natal)
    months = month_signals(natal, sex, target, 12)
    years = year_signals(natal, sex, target.year, 3)
    age = target.year - birth.year + 1
    ya = ma["yongsin"]["analysis"]
    dist_counts = {}
    for s in [p["stem"] for p in pillars_detail(natal)]:
        dist_counts[ELEMENT_OF_STEM[s]] = dist_counts.get(ELEMENT_OF_STEM[s], 0) + 1
    from .manseryuk import BRANCH_ELEMENT
    for key in ("year", "month", "day", "hour"):
        b = natal["pillars"][key][1]
        if b is not None:
            e = BRANCH_ELEMENT[b]
            dist_counts[e] = dist_counts.get(e, 0) + 1
    ast = ma["astro"]

    def mrows(domain: str) -> list[dict]:
        return [{"ym": f"{r['year']}-{r['month']:02d}", "label": f"{r['month']}월",
                 "ganzhi": r["ganzhi"], "god": r["god"], "score": r["scores"][domain],
                 "tag": r["labels"][domain], "why": r["why"][domain]} for r in months]

    def yrows(domain: str) -> list[dict]:
        return [{"year": r["year"], "ganzhi": r["ganzhi"], "score": r["scores"][domain],
                 "tag": r["labels"][domain], "why": r["why"][domain]} for r in years]

    palaces = []
    if zw:
        for p in zw["palaces"]:
            palaces.append({"name": p["name"], "ganzhi": p["stem_kr"] + p["branch_kr"],
                            "stars": list(p["stars"]), "daxian": list(p["daxian"]) if p["daxian"] else None})
    base = {
        "meta": {"target": target.isoformat(), "sex": "남성" if sex == "male" else "여성",
                 "age": age, "hour_known": hour is not None},
        "natal": {
            "ilgan": natal["ilgan"], "ilgan_element": natal["ilgan_element"],
            "character": ma["yongsin"]["ilgang"],
            "pillars": pillars_detail(natal),
            "elements": {e: dist_counts.get(e, 0) for e in ("목", "화", "토", "금", "수")},
            "ten_gods": ma["dist"][1] if len(ma["dist"]) > 1 else "",
            "strength": ya["strong_label"], "geguk": ya["geguk"], "geguk_mean": ya["geguk_mean"],
            "yongsin": ya["yongsin"],
            "sinsal": [f"{x['base']} 기준 {x['at']} {x['name']}({x['talk']})" for x in extra["sinsal"]
                       if x["name"] not in ("지살", "장성살")],
            "guiin": [f"{g['name']}({g['talk']}) {', '.join(g['at'])}" for g in extra["guiin"]],
            "pairs": extra["pairs"],
            "classic_sinsal": list(ma["shensha_lines"]),
            "dayun": ma["dayun_line"], "dayun_steps": list(ma["dayun_full"]),
            "ziwei": ({"guo": ma["guo_line"], "sihua": list(ma["sihua_lines"]),
                       "daxian": ma["daxian_line"], "liunian": ma["liunian_line"],
                       "palaces": palaces} if zw else None),
            "astro": {"sun": ast["sun"]["sign"], "moon": ast["moon"]["sign"], "venus": ast["venus"]["sign"],
                      "asc": ast["ascendant"] if hour is not None else None,
                      "mc": ast["mc"] if hour is not None else None,
                      "aspects": list(ast["aspects"])[:8]},
        },
        "today": {
            "agreement": ma["today"]["agreement"], "focus": ma["today"]["focus"],
            "systems": [{"name": s["name"], "signal": s["signal"], "lines": list(s["lines"])}
                        for s in ma["today"]["systems"]],
            "almanac": list(ma["today"]["almanac"]["lines"]),
            "scores": {"total": ma["total"]["score"], "love": ma["love"]["score"],
                       "career": ma["career"]["score"], "money": ma["money"]["score"]},
            "heads": {"total": ma["total"]["head"], "love": ma["love"]["head"],
                      "career": ma["career"]["head"], "money": ma["money"]["head"]},
            "keywords": list(ma["total"]["keywords"]),
            "element": ma["today_elem"],
        },
        "love": {
            "spouse_star": ma["star_line"],
            "spouse_seat": f"배우자궁 십성 {ma['god']}: {ma['side']}. 관계 {ma['god_vibe']}. 팁 {ma['god_tip']}",
            "day_stage": f"일주 십이운성 {ma['stage']}: {ma['stage_love']}",
            "dohwa": list(ma["dohwa_lines"]), "hongyeom": ma["hong_line"],
            "ziwei_spouse": ({"star": ma["ziwei_main"], **{k: v for k, v in ma["ziwei_detail"].items()}}
                             if zw else None),
            "venus": {"sign": ma["venus"], **ma["venus_detail"]},
            "moon": {"sign": ma["moon"], "need": ma["moon_need"]},
            "meet_paths": list(ma["meet_top3"]),
            "this_year": ma["timing"], "extra": list(ma["love_extra"]),
            "animals": animal_compat(natal["pillars"]["year"][1]),
            "months": mrows("love"), "years": yrows("love"),
            "best": [f"{r['year']}년 {r['month']}월({r['ganzhi']})" for r in best(months, "love")],
        },
        "career": {
            "guanlu": ma["career"]["guanlu_line"], "guan": ma["career"]["guan_line"],
            "palaces": list(ma["career"]["palaces"]), "extra": list(ma["career_extra"]),
            "tips": list(ma["career"]["tips"]), "avoid": ma["career"]["avoid"],
            "fit_jobs": ma["god_job"],
            "months": mrows("career"), "years": yrows("career"),
            "best": [f"{r['year']}년 {r['month']}월({r['ganzhi']})" for r in best(months, "career")],
        },
        "money": {
            "caibo": ma["money"]["caibo_line"], "cai": ma["money"]["cai_line"],
            "palaces": list(ma["money"]["palaces"]), "extra": list(ma["money_extra"]),
            "tips": list(ma["money"]["tips"]), "avoid": ma["money"]["avoid"],
            "months": mrows("money"), "years": yrows("money"),
            "best": [f"{r['year']}년 {r['month']}월({r['ganzhi']})" for r in best(months, "money")],
        },
        "life": {
            "phases": [p["line"] for p in ma["lifetime"]["phases"]],
            "current": ma["lifetime"]["current"]["short"],
            "decades": [{"range": list(d["range"]), "parts": list(d["parts"])} for d in ma["lifetime"]["decades"]],
            "dayun_narr": list(ma["yongsin"]["dayun_narr"]),
            "years": [y["line"] for y in ma["lifetime"]["years"]],
        },
    }
    base["natal"]["day_pillar"] = STEMS_KR[natal["ilgan_stem"]] + BRANCHES_KR[natal["day_branch"]]
    return base
