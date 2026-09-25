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


def sinsal_cards(lines: list[str]) -> dict | None:
    items = []
    for x in lines:
        name, _, body = x.partition(":")
        items.append((name.strip(), body.strip()))
    return cards("원국에 든 별과 살", items)


def strength_line(n: dict) -> str:
    return (f"내 사주는 {n['strength']}이고 격국(타고난 그릇의 모양)은 {n['geguk']}이야. "
            f"{n['geguk_mean']} 균형을 잡아 주는 기운(용신)은 {n['yongsin']}이야.")


def dayun_now(n: dict) -> str:
    """지금 대운(10년 단위 큰 흐름)을 말로 푼다. dayun 문장의 '현재 ○○운' 단계를 찾는다."""
    head = n.get("dayun") or ""
    cur = head.split("현재 ")[-1].split("(")[0] if "현재 " in head else ""
    step = next((s for s in n.get("dayun_steps") or [] if cur and s.startswith(cur)), "")
    if not step:
        return _end(head) if head else ""
    name, _, rest = step.partition(": ")
    return f"지금은 대운(10년 단위 큰 흐름) {j(name, '을')} 지나는 중이야. {rest}"


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
    return [x for x in extra if x.startswith("태어날 때")]


def run_now(extra: list[str]) -> list[str]:
    return [x for x in extra if not x.startswith("태어날 때")]


# ---------------------------------------------------------------- 총운

def today(f: dict, ch: str) -> dict:
    t, n = f["today"], f["natal"]
    heads, sc = t["heads"], t["scores"]
    saju = next((s for s in t["systems"] if s["name"] == "사주"), {"lines": []})
    if ch == "today":
        return chapter(heads["total"], t["agreement"], [
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
        return chapter("오늘 달력으로 본 할 일", t["almanac"][0] if t["almanac"] else "", [
            text("오늘 달력 풀이", *t["almanac"][1:-1]),
            checklist("오늘 해 보면 좋은 것", f["career"]["tips"] + f["money"]["tips"]),
            checklist("오늘 피할 것", [f["career"]["avoid"], f["money"]["avoid"]]),
            callout(t["almanac"][-1] if len(t["almanac"]) > 1 else ""),
        ])
    tip = (f["career"]["tips"] or f["money"]["tips"] or [""])[0]
    return chapter(heads["total"], t["focus"], [
        text("오늘을 한 문단으로", t["agreement"], heads["love"] + ".", heads["career"] + ".", heads["money"] + "."),
        quote(heads["total"]),
    ], f"오늘 딱 하나만 한다면: {tip}" if tip else "")


# ---------------------------------------------------------------- 연애

def love(f: dict, ch: str) -> dict:
    n, L = f["natal"], f["love"]
    zs, v, m = L.get("ziwei_spouse"), L["venus"], L["moon"]
    if ch == "wonguk":
        return chapter("연애로 읽는 나의 원국", n["character"], [
            text("일간이 말해 주는 나", n["geguk_mean"]),
            text("배우자를 보는 별(배우자성)", L["spouse_star"]),
            text("배우자 자리(일지)", L["spouse_seat"]),
            text("일주의 기운", L["day_stage"]),
            text("끌림의 별(도화·홍염)", *L["dohwa"], L["hongyeom"]),
            sinsal_cards(n["classic_sinsal"]),
        ])
    if ch == "why":
        return chapter(L["this_year"], strength_line(n), [
            text("지금 10년의 흐름", dayun_now(n)),
            text("자미두수로 본 지금", ziwei_now(n)),
            text("올해의 연애", L["this_year"], *L["extra"]),
            checklist("스스로 확인해 볼 연애 습관", [v["style"], m["need"], L["day_stage"].split(": ", 1)[-1]]),
        ])
    if ch == "map":
        return chapter(f"금성 {v['sign']}의 연애 지도", v["ideal"], [
            text("내가 사랑하는 방식", v["style"]),
            text("마음이 편해지는 조건", f"달이 {j(m['sign'], '라')} {m['need']}."),
            text("배우자 자리의 별", f"부처궁(배우자를 보는 자리) 주성은 {j(zs['star'], '이야')}. {zs['look']}. {zs['mind']}.")
            if zs else None,
            checklist("인연이 들어오기 쉬운 자리", L["meet_paths"]),
            text("띠로 본 궁합", _animals_line(L["animals"])),
        ])
    if ch == "howto":
        return chapter("인연을 부르는 실전 설계", v["how"], [
            steps("세 걸음", [("먼저 보여 줄 모습", L["spouse_seat"].split("팁 ")[-1]),
                           ("다가가는 방식", v["how"]),
                           ("만나는 자리", ", ".join(L["meet_paths"]))]),
            text("관계를 오래 가게 하는 법", zs["tip"] + "." if zs else "", m["need"] + "."),
            callout(L["day_stage"].split(": ", 1)[-1]),
        ])
    if ch == "calendar":
        return chapter("월별 러브 시그널", best_line(L["best"], "love"), months_blocks(L["months"], "love"))
    if ch == "partner":
        blocks = [cards(f"부처궁 {zs['star']}로 본 상대의 결",
                        [("인상", zs["look"]), ("성격", zs["mind"]), ("어울리는 분야", zs["job"]),
                         ("만나는 자리", zs["meet"])]) if zs else None,
                  text("금성으로 본 끌림", v["ideal"] + ".", v["how"] + "."),
                  text("배우자 자리로 본 상대", L["spouse_seat"].split(". 관계")[0] + "."),
                  callout(zs["tip"] if zs else m["need"])]
        return chapter("잘 맞는 상대의 결", "예언이 아니라, 계산으로 본 잘 맞는 결을 설명하는 거야.", blocks)
    if ch == "timing":
        return chapter(L["this_year"], best_line(L["best"], "love"),
                       [*years_blocks(L["years"], "love"), text("지금 10년의 흐름", dayun_now(n))])
    return chapter(L["this_year"], n["character"], [
        text("정리하면", L["spouse_seat"].split(". 팁")[0] + ".", best_line(L["best"], "love")),
        quote(v["how"]),
    ], "오늘부터 할 한 가지: " + L["spouse_seat"].split("팁 ")[-1])


def _animals_line(a: dict) -> str:
    good = ", ".join(f"{x['animal']}띠" for x in a["good"])
    bad = ", ".join(f"{x['animal']}띠" for x in a["bad"])
    out = f"내 띠({a['me']}) 기준으로 {good}와 잘 맞는 편이야." if good else ""
    if bad:
        out += f" {bad}와는 서로 서운하거나 부딪치기 쉬워서 말을 한 번 더 고르면 좋아."
    return out.strip()


# ---------------------------------------------------------------- 직장·금전 (같은 틀)

def work(f: dict, ch: str, dom: str) -> dict:
    n, D = f["natal"], f[dom]
    main = D["guanlu"] if dom == "career" else D["caibo"]
    star = D["guan"] if dom == "career" else D["cai"]
    word = DOMAIN_WORD[dom]
    if ch == "wonguk":
        blocks = [text("일간이 말해 주는 나", n["geguk_mean"]),
                  text("원국의 별" if dom == "career" else "원국의 돈 기운", star),
                  text("자미두수로 본 자리", main)]
        if dom == "career":
            blocks.append(text("잘 맞는 판", D["fit_jobs"]))
        blocks.append(sinsal_cards(n["classic_sinsal"]))
        return chapter(f"{j(word, '으로')} 읽는 나의 원국", n["character"], blocks)
    if ch == "why":
        return chapter(main, strength_line(n), [
            text("지금 10년의 흐름", *run_now(D["extra"])),
            text("자미두수로 본 지금", ziwei_now(n)),
            callout(f"균형을 잡아 주는 기운은 {n['yongsin']}이야. 이 기운이 들어오는 때와 자리를 살리면 {j(word, '이')} 한결 편해지기 쉬워."),
        ])
    if ch == "map":
        blocks = [text("나에게 맞는 결", main, star)]
        if dom == "career":
            blocks.append(text("잘 맞는 분야", D["fit_jobs"]))
        blocks.append(text("태어날 때 하늘의 별", *born_with(D["extra"])))
        a = n["astro"]
        if a.get("mc"):
            blocks.append(text("사회에서 보이는 얼굴", f"태양은 {a['sun']}, 사회적 얼굴(MC)은 {j(a['mc'], '야')}."))
        return chapter(f"나의 {'커리어' if dom == 'career' else '재물'} 지도", n["geguk_mean"], blocks)
    if ch == "howto":
        return chapter(f"{j(word, '을')} 다루는 실전 설계", n["character"], [
            steps("세 걸음", [("강점 자리 잡기", main),
                           ("맞는 판 고르기", D["fit_jobs"] if dom == "career" else star),
                           ("균형 맞추기", f"용신(균형을 잡아 주는 기운)은 {n['yongsin']}이야. 이 기운을 쓰는 쪽으로 방향을 잡아 봐.")]),
            callout(n["character"].split(". ")[-1]),
        ])
    if ch == "calendar":
        title = "월별 커리어 시그널" if dom == "career" else "월별 머니 시그널"
        return chapter(title, best_line(D["best"], dom), months_blocks(D["months"], dom))
    if ch in ("mentor", "partner"):
        guiin = [x for x in n["classic_sinsal"] if x.startswith("천을귀인")]
        return chapter("도움이 되는 사람과 자리", "예언이 아니라, 계산으로 본 도움의 결을 설명하는 거야.", [
            text("귀인(돕는 사람의 별)", *guiin, *n["guiin"]),
            text("자미두수로 본 자리", main),
            text("지금 10년의 흐름", *run_now(D["extra"])[:1]),
        ])
    if ch == "timing":
        return chapter(best_line(D["best"], dom) or f"앞으로 3년 {word}의 흐름", dayun_now(n),
                       years_blocks(D["years"], dom))
    return chapter(main, strength_line(n), [
        text("정리하면", star, best_line(D["best"], dom)),
        quote(n["geguk_mean"]),
    ], "")


# ---------------------------------------------------------------- 평생

def life(f: dict, ch: str) -> dict:
    n, Li = f["natal"], f["life"]
    current = Li["current"].split(" 아래 ")[0]
    zw, a = n.get("ziwei"), n["astro"]
    if ch == "wonguk":
        sky = f"태양은 {a['sun']}, 달은 {j(a['moon'], '야')}."
        if a.get("asc"):
            sky += f" 상승궁(첫인상)은 {j(a['asc'], '야')}."
        return chapter("원국 완전 풀이", n["character"], [
            text("타고난 그릇", strength_line(n)),
            text("십신(나와 다른 기운의 관계)", n["ten_gods"]),
            text("자미두수 명반", zw["guo"] + ".", " ".join(x + "." for x in zw["sihua"])) if zw else None,
            text("태어날 때 하늘", sky),
            sinsal_cards(n["classic_sinsal"]),
        ])
    if ch == "decades":
        return chapter("연대별 흐름", current, [
            cards("세 시기", [(p.split(":")[0], p.split(":", 1)[-1]) for p in Li["phases"]]),
        ])
    if ch == "dayun":
        return chapter("대운 여덟 걸음", dayun_now(n), [
            steps("10년씩 걷는 큰 흐름", [(s.split(":")[0], s.split(":", 1)[-1]) for s in Li["dayun_narr"]]),
        ])
    if ch == "years":
        rows = []
        this_year = int(f["meta"]["target"][:4])
        for y in Li["years"]:
            parts = [p.strip() for p in y.split("|")]
            note = next((p for p in parts if p.startswith("풀이:")), "")
            if len(parts) > 2 and note and parts[0][:4].isdigit() and int(parts[0][:4]) >= this_year:
                rows.append((f"{parts[0]} {parts[2]}", note[3:].strip().split(";")[0]))
        return chapter("해마다의 흐름", "연애·일·돈의 3년 흐름과 해마다의 기운을 함께 놓고 봐.", [
            *years_blocks(f["love"]["years"], "love"),
            *years_blocks(f["career"]["years"], "career"),
            *years_blocks(f["money"]["years"], "money"),
            cards("해마다 들어오는 기운", rows[:6]),
        ])
    return chapter("평생 흐름 정리", current, [
        text("타고난 그릇", strength_line(n)),
        text("지금 10년", dayun_now(n)),
        quote(n["character"]),
    ])


def build(tab: str, ch: str, facts: dict) -> dict:
    if tab == "today":
        return today(facts, ch)
    if tab == "love":
        return love(facts, ch)
    if tab in ("career", "money"):
        return work(facts, ch, tab)
    return life(facts, ch)
