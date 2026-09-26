"""rule_chapters.py, 계산 결과만으로 쓰는 챕터 풀이 (바로 보여 주는 기본 풀이).

AI 풀이는 챕터마다 1분 가까이 걸려서, 화면은 이 풀이를 먼저 보여 주고
AI 풀이가 준비되면 바꿔 끼운다. AI 를 못 쓸 때도 이 풀이가 그대로 남는다.

- 문장은 사실표(facts.py)에 이미 계산·서술된 문장을 챕터 흐름에 맞게 엮은 것이다.
  사실표에 없는 해석·숫자·날짜는 만들지 않는다.
- 모양은 AI 풀이와 같다: {headline, lead, blocks, closing}.
"""
from __future__ import annotations

from .josa import j

PUSH, GOOD = "밀고 나갈 때", "좋은 흐름"
CARE = ("다듬을 때", "조심할 때")
DOMAIN_WORD = {"love": "연애", "career": "일", "money": "돈"}


# ---------------------------------------------------------------- 블록 도우미

def _end(s: str) -> str:
    """이어 붙일 때 문장이 섞이지 않게 끝에 마침표를 붙인다."""
    s = str(s).strip()
    return s if not s or s[-1] in ".!?" else s + "."


def text(title: str, *parts) -> dict | None:
    body = " ".join(_end(p) for p in parts if p and str(p).strip())
    return {"type": "text", "title": title, "body": body} if body else None


def quote(body) -> dict | None:
    return {"type": "quote", "title": "", "body": str(body).strip()} if body else None


def callout(body) -> dict | None:
    return {"type": "callout", "title": "", "body": str(body).strip()} if body else None


def checklist(title: str, items) -> dict | None:
    items = [str(x).strip() for x in items if x and str(x).strip()]
    return {"type": "checklist", "title": title, "items": items[:8]} if items else None


def steps(title: str, items) -> dict | None:
    items = [{"title": t, "body": str(b).strip()} for t, b in items if b and str(b).strip()]
    return {"type": "steps", "title": title, "items": items[:6]} if items else None


def cards(title: str, items) -> dict | None:
    items = [{"title": t, "body": str(b).strip()} for t, b in items if b and str(b).strip()]
    return {"type": "cards", "title": title, "items": items[:6]} if items else None


def chapter(headline, lead, blocks, closing="") -> dict:
    blocks = [b for b in blocks if b]
    return {"headline": str(headline or "").strip()[:60], "lead": _end(lead or ""),
            "blocks": blocks[:8], "closing": str(closing or "").strip()}


# ---------------------------------------------------------------- 문장 도우미

def _ym(row: dict) -> str:
    return f"{row['ym'][:4]}년 {row['label']}({row['ganzhi']})"


def _why(row: dict) -> str:
    return ", ".join(row["why"])


def months_blocks(rows: list[dict], dom: str) -> list:
    word = DOMAIN_WORD[dom]
    push = [r for r in rows if r["tag"] == PUSH]
    good = [r for r in rows if r["tag"] == GOOD]
    care = [r for r in rows if r["tag"] in CARE]
    out = []
    if push:
        out.append(text("밀고 나가기 좋은 달", " ".join(
            f"{_ym(r)}은 {_why(r) or '여러 기운이 함께 받쳐 주는 때'}라 {word}에서 한 걸음 내딛기 좋은 흐름이야."
            for r in push)))
    if good:
        out.append(cards("흐름이 좋은 달", [(_ym(r), _why(r) or "무리 없이 순하게 흐르는 때") for r in good]))
    if care:
        out.append(text("다듬고 조심할 달", " ".join(
            f"{_ym(r)}은 {_why(r) or '기운이 엇갈리는 때'}라 {r['tag'].replace(' 때', '')} 때야. "
            f"큰 결정보다 점검에 힘을 쓰면 좋아." for r in care)))
    if not (push or good or care):
        out.append(text("", f"앞으로 열두 달은 {word}에서 특별히 튀는 달 없이 잔잔한 흐름이야."))
    return out


def years_blocks(rows: list[dict], dom: str) -> list:
    word = DOMAIN_WORD[dom]
    return [cards(f"앞으로 3년 {word}의 흐름",
                  [(f"{r['year']}년 {r['ganzhi']}", f"{r['tag']}. {_why(r) or '특별히 걸리는 신호 없이 잔잔한 해'}")
                   for r in rows])]


def best_line(best: list[str], dom: str) -> str:
    if not best:
        return ""
    return f"앞으로 열두 달 중 {DOMAIN_WORD[dom]}에 가장 힘이 실리는 때는 {', '.join(best)}이야."


PILLAR_PLAIN = {"년지": "태어난 해", "월지": "태어난 달", "일지": "태어난 날", "시지": "태어난 시"}


def sinsal_cards(lines: list[str]) -> dict | None:
    """'천을귀인: 축·미, 시지에 있어 …' → 글자 목록은 빼고 자리를 쉬운 말로. '아님'인 줄은 뺀다."""
    import re
    items = []
    for x in lines:
        name, _, body = x.partition(":")
        body = body.strip()
        if "아님" in body.split(",")[0]:
            continue
        body = re.sub(r"^[가-힣](·[가-힣])*,\s*", "", body)          # 앞의 지지 글자 목록
        body = re.sub(r"^[가-힣]+ [가-힣](·[가-힣]+ [가-힣])*,\s*", "", body)   # '고진 신·과숙 진,' 같은 목록
        for k, v in PILLAR_PLAIN.items():
            body = body.replace(k, v)
        items.append((name.strip(), body))
    return cards("원국에 든 별과 살", items)


GROUP_PLAIN = {"비겁": "나와 같은 편 기운", "인성": "나를 받쳐 주는 기운", "식상": "표현하고 만드는 기운",
               "재성": "돈과 결과의 기운", "관성": "나를 다듬는 규율의 기운"}
GOD_GROUP = {"비견": "비겁", "겁재": "비겁", "정인": "인성", "편인": "인성", "식신": "식상", "상관": "식상",
             "정재": "재성", "편재": "재성", "정관": "관성", "편관": "관성"}


def _yongsin_plain(y: str) -> str:
    """'관성·식상·재성 기운 (힘을 빼고 다스리는 쪽)' → 뜻을 풀어 쓴 말."""
    head, _, tail = y.partition(" (")
    groups = [g for g in head.replace(" 기운", "").split("·") if g in GROUP_PLAIN]
    plain = ", ".join(f"{GROUP_PLAIN[g]}({g})" for g in groups)
    return f"{plain}처럼 {tail.rstrip(')')}" if plain else y


def strength_line(n: dict) -> str:
    strong = "센 편(신강)" if "신강" in n["strength"] else "약한 편(신약)"
    return (f"내 사주는 나를 이루는 기운이 {strong}이야. 타고난 그릇의 모양(격국)은 {n['geguk']}인데, "
            f"{n['geguk_mean']} 그래서 균형을 잡아 주는 기운(용신)은 {_yongsin_plain(n['yongsin'])}이야.")


def ten_gods_plain(n: dict) -> str:
    """여덟 글자를 나와의 관계 다섯 무리로 세어 말로 푼다."""
    count = {g: 0 for g in GROUP_PLAIN}
    for p in n["pillars"]:
        for god in (p["stem_god"], p["branch_god"]):
            if god in GOD_GROUP:
                count[GOD_GROUP[god]] += 1
    parts = [f"{GROUP_PLAIN[g]}({g}) {c}개" for g, c in count.items() if c]
    none = [f"{GROUP_PLAIN[g]}" for g, c in count.items() if not c]
    out = "나(태어난 날의 하늘 글자)를 빼고 나머지 글자들을 나와의 관계로 나누면 " + ", ".join(parts) + "야."
    if none:
        out += " " + "·".join(none) + " 쪽은 원국에 없어서, 운에서 들어올 때 그쪽 일이 움직이기 쉬워."
    return out


def ziwei_plain(zw: dict) -> str:
    """자미두수 명반 요약을 말로 푼다."""
    from .narrate import PALACE_TALK
    talk = {"록": "복이 붙는 기운(화록)", "권": "힘이 실리는 기운(화권)", "과": "이름이 나는 기운(화과)", "기": "막힘이 걸리는 기운(화기)"}
    ming = next((p for p in zw["palaces"] if p["name"] == "명궁"), None)
    mains = [s for s in (ming["stars"] if ming else []) if s in STAR14]
    out = []
    if ming:
        out.append(f"자미두수 명반에서 나를 보는 자리(명궁)의 주인 별은 {j('·'.join(mains) or '빈자리', '이야')}.")
    for h in ("록", "권", "과", "기"):
        for p in zw["palaces"]:
            star = next((s for s, v in (p.get("hua") or {}).items() if v == h), None)
            if star:
                out.append(f"태어난 해의 {j(talk[h], '은')} {star} 별에 붙어 {p['name'].replace('(배우자)', '')} 자리"
                           f"({PALACE_TALK.get(p['name'], '')})에 들어가.")
    return " ".join(out)


STAR14 = ("자미", "천기", "태양", "무곡", "천동", "염정", "천부", "태음", "탐랑", "거문", "천상", "천량", "칠살", "파군")


def dayun_plain(s: str) -> str:
    """'천간 기는 나에게 …, 지지 묘는 일지와 …' → 하늘 글자·땅 글자로 풀어 쓴다."""
    return (s.replace("천간 ", "이 10년의 하늘 글자 ", 1)
             .replace("지지 ", "땅 글자 ", 1)
             .replace("일지와", "내 배우자 자리(태어난 날의 땅 글자)와"))


def house_plain(s: str) -> str:
    import re
    from .narrate import HOUSE_TALK
    return re.sub(r"(\d+)번 하우스 칸", lambda m: f"{m.group(1)}번 하우스({HOUSE_TALK[int(m.group(1))]} 영역) 칸", s)


def dayun_now(n: dict) -> str:
    """지금 대운(10년 단위 큰 흐름)을 말로 푼다. dayun 문장의 '현재 ○○운' 단계를 찾는다."""
    head = n.get("dayun") or ""
    cur = head.split("현재 ")[-1].split("(")[0] if "현재 " in head else ""
    step = next((s for s in n.get("dayun_steps") or [] if cur and s.startswith(cur)), "")
    if not step:
        return _end(head) if head else ""
    name, _, rest = step.partition(": ")
    return f"지금은 대운(10년 단위 큰 흐름) {j(name, '을')} 지나는 중이야. {dayun_plain(rest)}"


def ziwei_now(n: dict) -> str:
    """자미두수 대한·유년을 말로 푼다 ('현재 대운(세는나이 37세) 자녀(35~44세, 주성 천기)')."""
    zw = n.get("ziwei")
    if not zw:
        return ""
    out = []
    dx = zw.get("daxian") or ""
    if ") " in dx:
        seat = dx.split(") ", 1)[1]                        # 자녀(35~44세, 주성 천기)
        out.append(f"자미두수의 10년 흐름(대한)으로는 지금 {seat} 자리를 지나고 있어.")
    ly = zw.get("liunian") or ""
    if "유년명궁 " in ly and "(" in ly:
        pal = ly.split("유년명궁 ", 1)[1].split("(", 1)[1].split(")", 1)[0]
        out.append(f"올해 한 해의 중심(유년 명궁)은 {pal} 자리에 걸려 있어.")
    return " ".join(out)


def born_with(extra: list[str]) -> list[str]:
    return [house_plain(x) for x in extra if x.startswith("태어날 때")]


def run_now(extra: list[str]) -> list[str]:
    return [x for x in extra if not x.startswith("태어날 때")]


# ---------------------------------------------------------------- 총운 (오늘)

TODAY_WORD = {"love": "연애", "career": "직장", "money": "금전"}


def today(f: dict, ch: str) -> dict:
    t, n = f["today"], f["natal"]
    heads, sc = t["heads"], t["scores"]
    saju = next((s for s in t["systems"] if s["name"] == "사주"), {"lines": []})
    doms = t["domains"]
    if ch == "today":
        return chapter(heads["total"], t["agreement"], [
            callout(f"오늘 총운 {sc['total']}점은 연애 {sc['love']}점, 직장 {sc['career']}점, 금전 {sc['money']}점의 "
                    "평균에 오늘 공통 기운을 더한 값이야."),
            text("세 체계를 합치면", t["focus"]),
            *[text(f"{s['name']}: {s['signal']}", *s["lines"]) for s in t["systems"]],
            cards("영역별 오늘", [(f"연애 {sc['love']}점", heads["love"]), (f"직장 {sc['career']}점", heads["career"]),
                               (f"금전 {sc['money']}점", heads["money"])]),
        ], "점수는 오늘 흐름의 방향을 보는 참고값이야.")
    if ch == "me":
        kw = "·".join(t["keywords"])
        return chapter(f"오늘의 키워드는 {kw}", n["character"], [
            text("오늘 내 기운의 단계", *saju["lines"][:1]),
            text("오늘 들어온 기운과 나", *saju["lines"][1:]),
            quote(heads["total"]),
            callout(t["focus"]),
        ])
    if ch == "todo":
        tips = doms["career"]["tips"] + doms["money"]["tips"]
        avoid = [doms[d]["avoid"] for d in ("career", "money") if doms[d]["avoid"]]
        return chapter("오늘 달력으로 본 할 일", t["almanac"][0] if t["almanac"] else "", [
            text("오늘 달력 풀이", *t["almanac"][1:-1]),
            checklist("오늘 해 보면 좋은 것", tips),
            checklist("오늘 피할 것", avoid),
            callout(t["almanac"][-1] if len(t["almanac"]) > 1 else ""),
        ])
    tip = (doms["career"]["tips"] or doms["money"]["tips"] or [""])[0]
    return chapter(heads["total"], t["focus"], [
        text("오늘을 한 문단으로", t["agreement"], heads["love"], heads["career"], heads["money"]),
        quote(heads["total"]),
    ], f"오늘 딱 하나만 한다면: {tip}" if tip else "")


# ---------------------------------------------------------------- 연애·직장·금전 (오늘)

def _points_line(p: int, word: str) -> str:
    """체계별 가감 신호 (점수 그 자체가 아니라 방향과 세기)."""
    if p > 0:
        return f"{word} 쪽 신호 +{p}, 오늘 {j(word, '을')} 받쳐 주는 쪽이야."
    if p < 0:
        return f"{word} 쪽 신호 {p}, 오늘 {j(word, '을')} 조금 누르는 쪽이야."
    return f"{word} 쪽으로는 더하거나 빼는 신호가 없어."


def today_domain(f: dict, ch: str, dom: str) -> dict:
    t = f["today"]
    d = t["domains"][dom]
    word = TODAY_WORD[dom]
    if ch == "score":
        return chapter(f"오늘 {word} {d['score']}점", d["head"], [
            checklist("이 점수가 나온 근거", d["reasons"]),
            cards("세 체계가 더하고 뺀 몫", [(s["name"], _points_line(s["points"], word)) for s in d["systems"]]),
        ], "점수는 오늘 흐름의 방향을 보는 참고값이야.")
    if ch == "systems":
        blocks = []
        for s in d["systems"]:
            blocks.append(text(s["name"], *(s["lines"] or [f"오늘 {word}에만 따로 걸리는 신호는 없어."]),
                               *(f"모든 운에 함께 걸리는 것: {x}" for x in s.get("common", [])),
                               _points_line(s["points"], word)))
        blocks.append(callout(t["agreement"]))
        return chapter(f"세 체계로 본 오늘 {word}", d["head"], blocks)
    if ch == "howto":
        if dom == "love":
            L = f["love"]
            todo = [L["spouse_seat"].split("팁: ")[-1], L["venus"]["how"],
                    "오늘 가 보기 좋은 자리: " + ", ".join(L["meet_paths"])]
            avoid = []
        else:
            todo, avoid = d["tips"], [d["avoid"]] if d["avoid"] else []
        return chapter("오늘 이렇게 해 봐", d["head"], [
            checklist("오늘 해 보면 좋은 것", todo),
            checklist("오늘 피할 것", avoid),
            text("오늘 달력으로 보면", *t["almanac"][1:2]),
            callout(t["almanac"][-1] if len(t["almanac"]) > 1 else ""),
        ])
    best = d["reasons"][0] if d["reasons"] else ""
    return chapter(d["head"], f"오늘 {j(word, '은')} {d['score']}점, {d['head']}.", [
        text("오늘을 한 문단으로", best, *(x for s in d["systems"] for x in s["lines"][:1])),
        quote(d["head"]),
    ])


# ---------------------------------------------------------------- 평생 (타고난 결·앞으로의 흐름)

def _animals_line(a: dict) -> str:
    good = ", ".join(f"{x['animal']}띠" for x in a["good"])
    bad = ", ".join(f"{x['animal']}띠" for x in a["bad"])
    out = f"내 띠({a['me']}) 기준으로 {j(good, '와')} 잘 맞는 편이야." if good else ""
    if bad:
        out += f" {j(bad, '와')}는 서로 서운하거나 부딪치기 쉬워서 말을 한 번 더 고르면 좋아."
    return out.strip()


def love_nature(f: dict) -> dict:
    n, L = f["natal"], f["love"]
    zs, v, m = L.get("ziwei_spouse"), L["venus"], L["moon"]
    return chapter("타고난 연애의 결", n["character"], [
        text("배우자를 보는 별(배우자성)", L["spouse_star"]),
        text("배우자 자리", L["spouse_seat"]),
        text("일주의 기운", L["day_stage"]),
        text("끌림의 별(도화·홍염)", *L["dohwa"], L["hongyeom"]),
        text("내가 사랑하는 방식", f"금성이 {j(v['sign'], '라')} {v['style']}", v["ideal"],
             f"달이 {j(m['sign'], '라')} {m['need']}"),
        cards(f"부처궁 {zs['star']}로 본 잘 맞는 상대의 결",
              [("인상", zs["look"]), ("성격", zs["mind"]), ("어울리는 분야", zs["job"]),
               ("만나는 자리", zs["meet"])]) if zs else None,
        checklist("인연이 들어오기 쉬운 자리", L["meet_paths"]),
        text("띠로 본 궁합", _animals_line(L["animals"])),
    ], "잘 맞는 상대의 결은 예언이 아니라 계산으로 본 경향이야.")


def work_nature(f: dict, dom: str) -> dict:
    n, D = f["natal"], f[dom]
    main = D["guanlu"] if dom == "career" else D["caibo"]
    star = D["guan"] if dom == "career" else D["cai"]
    guiin = [x for x in n["classic_sinsal"] if x.startswith("천을귀인")]
    blocks = [text("타고난 그릇", strength_line(n)),
              text("원국의 별" if dom == "career" else "원국의 돈 기운", star),
              text("자미두수로 본 자리", main)]
    if dom == "career":
        blocks.append(text("잘 맞는 분야", D["fit_jobs"]))
        blocks.append(text("도움이 되는 사람(귀인)", *guiin, *n["guiin"]))
    blocks.append(text("태어날 때 하늘의 별", *born_with(D["extra"])))
    blocks.append(callout(f"균형을 잡아 주는 기운(용신)은 {n['yongsin']}이야. 계절로 보면(조후) "
                          f"{j(n['johu']['main'][0], '도')} 반가운 기운이야. 이런 기운이 들어오는 때와 자리를 살리면 "
                          f"{j(DOMAIN_WORD[dom], '이')} 한결 편해지기 쉬워."))
    title = "타고난 일의 결" if dom == "career" else "타고난 돈의 결"
    return chapter(title, n["character"], blocks, "투자·이직 같은 큰 결정은 전문가와 함께 따져 봐." if dom == "money" else "")


def flow(f: dict, dom: str) -> dict:
    D = f[dom]
    blocks = months_blocks(D["months"], dom) + years_blocks(D["years"], dom)
    if dom == "love":
        blocks.insert(0, text("올해의 연애", D["this_year"]))
    word = DOMAIN_WORD[dom]
    return chapter(f"{word}의 흐름: 12개월과 3년", best_line(D["best"], dom), blocks)


def L_day_stage(f: dict) -> str:
    return f["love"]["day_stage"]


def life(f: dict, ch: str) -> dict:
    n, Li = f["natal"], f["life"]
    current = Li["current"].split(" 아래 ")[0]
    zw, a = n.get("ziwei"), n["astro"]
    if ch == "wonguk":
        sky = f"태양은 {a['sun']}, 달은 {j(a['moon'], '야')}."
        if a.get("asc"):
            sky += f" 상승궁(첫인상)은 {j(a['asc'], '야')}."
        bd = n.get("boundary") or {}
        return chapter("원국 완전 풀이", n["character"], [
            callout(" ".join([i["text"] for i in bd.get("items", [])] + ([bd["note"]] if bd.get("note") else []))),
            text("타고난 그릇", strength_line(n)),
            text("계절로 본 용신(조후)", *n["johu"]["text"]),
            text("여덟 글자와 나의 관계(십신)", ten_gods_plain(n)),
            text("자미두수 명반", ziwei_plain(zw)) if zw else None,
            text("태어날 때 하늘", sky),
            sinsal_cards(n["classic_sinsal"]),
        ])
    if ch == "ilju":
        c = n["ilju"]
        return chapter(f"{c['pillar']} 일주: {c['title']}", n["character"], [
            text("일주 그림", f"일간 {j(c['pillar'][0], '은')} {j(c['image'], '이고')} 일지 {j(c['pillar'][1], '은')} {c['animal']}띠 자리야. "
                 f"그래서 {c['pillar']} 일주는 '{c['title']}'로 그려 볼 수 있어.",
                 f"요즘 색으로 부르는 말로는 '{c['modern']}'인데, 띠에 색을 붙이는 건 요즘 생긴 표현이야."),
            text("일주의 기운 단계", L_day_stage(f)),
            text("배우자 자리", f["love"]["spouse_seat"].split(" 팁:")[0]),
            cards("일주에 붙은 신살", [(m["name"], m["talk"]) for m in c["marks"]]),
        ])
    if ch == "love_nature":
        return love_nature(f)
    if ch in ("career_nature", "money_nature"):
        return work_nature(f, ch.split("_")[0])
    if ch in ("love_flow", "career_flow", "money_flow"):
        return flow(f, ch.split("_")[0])
    if ch == "decades":
        return chapter("연대별 흐름", current, [
            cards("세 시기", [(p.split(":")[0], p.split(":", 1)[-1]) for p in Li["phases"]]),
        ])
    if ch == "dayun":
        rel = Li.get("dayun_rel") or []
        now = next((r for r in rel if r["now"]), None)
        return chapter("대운 여덟 걸음", dayun_now(n), [
            callout(f"지금 대운과 원국: {now['line']}") if now else None,
            steps("10년씩 걷는 큰 흐름", [(s.split(":")[0], dayun_plain(s.split(":", 1)[-1].strip())) for s in Li["dayun_narr"]]),
            cards("대운이 원국과 만나는 자리", [(f"{r['ganzhi']}운 ({r['from']}~{r['to']}세)", r["line"].split("운은 ", 1)[-1])
                                         for r in rel]),
        ])
    return chapter("평생 흐름 정리", current, [
        text("타고난 그릇", strength_line(n)),
        text("지금 10년", dayun_now(n)),
        text("앞으로 힘이 실리는 때", best_line(f["love"]["best"], "love"), best_line(f["career"]["best"], "career"),
             best_line(f["money"]["best"], "money")),
        quote(n["character"]),
    ])


# ---------------------------------------------------------------- 신년운세

def newyear(f: dict, ch: str) -> dict:
    ny = f["newyear"]
    y = ny["year"]
    words = {"love": "연애", "career": "일", "money": "돈"}
    if ch == "overview":
        sig = ny["signals"]
        return chapter(f"{y}년 {ny['ganzhi']}년, 만 {ny['age']}세의 한 해",
                       f"{y}년 기운은 나에게 {ny['god']}으로 다가와. {ny['rel']}", [
            cards("세 영역의 한 해", [(f"{words[d]}: {sig[d]['tag']}", ", ".join(sig[d]["why"]) or "특별히 걸리는 신호 없이 잔잔한 해")
                                   for d in ("love", "career", "money")]),
            callout(ny["dayun_note"]),
            text("타고난 나와 함께 보면", f["natal"]["character"]),
        ])
    if ch == "tojeong":
        t = ny["tojeong"]
        tone = {"good": "좋은 쪽", "mid": "좋고 나쁨이 엇갈리는 쪽", "care": "조심하라는 쪽"}[t["tone"]]
        return chapter(f"{y}년 토정비결 {t['gua']}괘: {t['read']}", t["mean"], [
            text("괘가 가리키는 쪽", f"이 괘는 한 해를 {tone}으로 보는 괘야."),
            checklist("괘를 뽑은 계산", [t["steps"]["upper"], t["steps"]["middle"], t["steps"]["lower"]]),
            callout(t["note"]),
            text("알아 둘 것", "토정비결은 조선 후기 필사본으로 전해 온 옛 점서야. 여기서는 한 해 총평(괘사 여덟 글자)만 풀었고, "
                 "달마다 붙는 괘사는 넣지 않았어."),
        ])
    if ch == "months":
        blocks = []
        for d in ("love", "career", "money"):
            rows = ny["months"][d]
            push = [r for r in rows if r["tag"] in ("밀고 나갈 때", "좋은 흐름")]
            care = [r for r in rows if r["tag"] in ("다듬을 때", "조심할 때")]
            body = []
            if push:
                body.append("힘이 실리는 달은 " + ", ".join(f"{r['label']}({r['ganzhi']})" for r in push) + "이야.")
            if care:
                body.append("다듬을 달은 " + ", ".join(f"{r['label']}({r['ganzhi']})" for r in care) + "이야.")
            blocks.append(text(f"{words[d]}의 열두 달", *(body or ["특별히 튀는 달 없이 잔잔한 흐름이야."])))
        return chapter(f"{y}년 달마다 흐름", "밀고 나갈 달과 다듬을 달을 미리 알아 두면 한 해를 쓰기 편해.", blocks)
    if ch == "ziwei":
        z = ny["ziwei"]
        if not z:
            return chapter("자미두수로 본 한 해", "태어난 시간을 몰라 자미두수 명반을 세우지 못해서 이 부분은 보지 않았어.", [
                text("대신 이렇게 봐", "한 해의 흐름은 사주 세운(한 해를 여는 기운·달마다 흐름)과 점성술(하늘의 큰 별) 챕터로 볼 수 있어.",
                     "태어난 시간을 알게 되면 다시 넣어 봐. 그해의 중심 자리와 사화가 붙는 자리까지 볼 수 있어."),
            ])
        return chapter(f"{y}년의 중심은 {z['palace']} 자리", z["line"], [
            checklist("그해 사화(록권과기)가 붙는 자리", z["hua"]),
        ])
    if ch == "sky":
        return chapter(f"{y}년 목성과 토성", "목성은 기회와 넓어짐을, 토성은 과제와 다짐을 보는 별이야.",
                       [text("", line) for line in ny["sky"]])
    sig = ny["signals"]
    top = max(("love", "career", "money"), key=lambda d: ["조심할 때", "다듬을 때", "무난한 흐름", "좋은 흐름", "밀고 나갈 때"].index(sig[d]["tag"]))
    return chapter(f"{y}년은 {words[top]}에 힘이 실리는 해", ny["rel"], [
        text("정리하면", *(f"{words[d]}은 {sig[d]['tag']}." if d != "love" else f"연애는 {sig[d]['tag']}." for d in ("love", "career", "money"))),
        text("미리 표시해 둘 달", *(f"{words[d]}: {', '.join(ny['best'][d])}" for d in ("love", "career", "money"))),
        callout(ny["dayun_note"]),
    ])


def build(tab: str, ch: str, facts: dict) -> dict:
    if tab == "newyear":
        return newyear(facts, ch)
    if tab == "today":
        return today(facts, ch)
    if tab in ("love", "career", "money"):
        return today_domain(facts, ch, tab)
    return life(facts, ch)
