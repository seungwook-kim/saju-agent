"""chapters.py, 탭별 챕터 설계와 챕터 풀이 생성 (AI + 계산 문장 대체).

탭마다 챕터 순서를 정하고, 챕터마다
- widgets: 계산값으로 그리는 화면 부품 (원국 표, 띠 카드, 월별 캘린더 등)
- pick:    AI 에게 넘길 사실표 부분
- ask:     그 챕터에서 풀어야 할 것
을 둔다. AI 는 넘겨받은 사실만 근거로 쓰고, 답은 블록(JSON)으로 받는다.
AI 를 못 쓰면 사실표 문장으로 같은 모양의 블록을 만든다 (source='rule').
"""
from __future__ import annotations

import hashlib
import json
import re

from . import ai, content_store

PROMPT_VERSION = "ch-2"

SYSTEM = """너는 정통 사주명리·자미두수·서양 점성술을 함께 보는 다정한 상담가다.
아래 규칙을 반드시 지킨다.
1. 사용자가 준 '사실표'에 있는 계산 결과만 근거로 쓴다. 사실표에 없는 것
   (과거 경험, 직업, 성격 단정, 인연의 수, 확률, 퍼센트, 사실표에 없는 날짜나 나이)은 절대 지어내지 않는다.
   시기를 말할 때는 사실표에 나온 달·해만 쓴다. 숫자는 사실표에 있는 것만 쓴다.
2. 단정적 예언을 하지 않는다. '~할 것이다', '반드시', '100%', '확률' 대신 '~하기 좋은 흐름', '~하기 쉬워' 로 말한다.
3. 별·궁·십신·신살 같은 용어가 나오면 그 자리에서 괄호로 쉬운 뜻을 붙인다.
4. 친근한 반말(…야, …해, …거든)로, 점술가가 마주 앉아 말해 주듯 쓴다. 과장하거나 겁주지 않는다.
5. 한자·일본어를 쓰지 않는다. 긴 줄표(엠 대시)를 쓰지 않는다. 이모지를 쓰지 않는다.
6. 건강·법률·투자 같은 중요한 결정은 대신 내려 주지 않고 전문가와 상의하라고 권한다.
7. 출력은 JSON 객체 하나만 쓴다. 설명이나 코드 울타리를 붙이지 않는다.

JSON 형식:
{"headline": "챕터 결론 한 줄 (40자 안쪽)",
 "lead": "도입 두세 문장",
 "blocks": [
   {"type": "text", "title": "소제목", "body": "문단 (3~6문장)"},
   {"type": "quote", "body": "마음에 남을 한 줄"},
   {"type": "checklist", "title": "제목", "items": ["항목", "..."]},
   {"type": "steps", "title": "제목", "items": [{"title": "단계 이름", "body": "설명"}]},
   {"type": "cards", "title": "제목", "items": [{"title": "카드 제목", "body": "설명"}]},
   {"type": "callout", "body": "강조할 요점 한두 문장"}
 ],
 "closing": "마무리 한 줄"}
blocks 는 4~7개. text 블록을 두 개 이상 넣고, 나머지 형식은 챕터에 맞게 골라 쓴다."""

BLOCK_TYPES = {"text", "quote", "checklist", "steps", "cards", "callout"}

# ---------------------------------------------------------------- 탭 설계

TABS = {
    "today": {
        "title": "오늘의 운세", "hand": "Today", "theme": "peach",
        "sub": "사주·자미두수·점성술이 함께 보는 오늘",
        "chapters": [
            {"id": "today", "nav": "오늘", "emoji": "☀️", "title": "세 체계가 본 오늘",
             "widgets": ["gauge:today", "systems"], "pick": ["today"],
             "ask": "세 체계(사주·자미두수·점성술)가 오늘을 어떻게 보는지, 서로 맞는 점과 엇갈리는 점을 풀어 줘. 오늘 가장 힘이 실린 영역과 쉬어 갈 영역도."},
            {"id": "me", "nav": "오늘의 나", "emoji": "🪞", "title": "오늘의 나",
             "widgets": [], "pick": ["today", "natal.character", "natal.ilgan"],
             "ask": "오늘 내 기운의 결(십이운성·일진과의 관계)을 바탕으로 오늘 어떤 모습으로 지내면 좋은지 그려 줘."},
            {"id": "todo", "nav": "할 일", "emoji": "✅", "title": "오늘 할 일과 피할 일",
             "widgets": ["almanac"], "pick": ["today"],
             "ask": "오늘 택일(생기복덕·건제·황도흑도·손 없는 날)과 세 체계 신호를 근거로, 오늘 하면 좋은 일 체크리스트와 피할 일을 정리해 줘."},
            {"id": "final", "nav": "한마디", "emoji": "✨", "title": "오늘의 한마디",
             "widgets": [], "pick": ["today"],
             "ask": "오늘을 한 문단으로 정리하고, 오늘 딱 하나만 한다면 무엇을 하면 좋을지 말해 줘."},
        ]},
    "love": {
        "title": "연애 A to Z", "hand": "Love", "theme": "rose",
        "sub": "사주로 읽는 인연의 결과 흐름",
        "chapters": [
            {"id": "wonguk", "nav": "원국", "emoji": "📜", "title": "연애로 읽는 나의 원국",
             "widgets": ["wonguk"], "pick": ["natal", "love.spouse_star", "love.spouse_seat", "love.day_stage", "love.dohwa", "love.hongyeom"],
             "ask": "원국을 연애 관점에서 풀어 줘: 일간의 기질, 배우자성, 배우자궁, 도화·홍염, 연애에 닿는 신살·귀인."},
            {"id": "why", "nav": "왜 지금", "emoji": "👁️", "title": "지금 연애가 이런 이유",
             "widgets": [], "pick": ["natal.strength", "natal.dayun", "natal.ziwei", "love"],
             "ask": "지금 연애 흐름이 이런 구조적 이유(원국·대운·올해 유년)를 풀고, 사실표 근거로 스스로 확인해 볼 성향 체크리스트를 만들어 줘."},
            {"id": "map", "nav": "연애 지도", "emoji": "💭", "title": "나의 연애 지도",
             "widgets": ["animals"], "pick": ["love"],
             "ask": "끌리는 상대의 결(금성·달·부처궁), 인연이 들어오는 경로(meet_paths), 띠 궁합 결과를 풀어 줘. 띠 궁합은 사실표의 분류를 그대로 따른다."},
            {"id": "howto", "nav": "실전", "emoji": "💫", "title": "인연을 부르는 실전 설계",
             "widgets": [], "pick": ["love", "natal.character"],
             "ask": "사실표 근거로 행동 설계를 3단계(steps)로, 그리고 말 한마디·만나는 자리·피할 것을 알려 줘."},
            {"id": "calendar", "nav": "월별", "emoji": "📊", "title": "월별 러브 시그널",
             "widgets": ["calendar:love"], "pick": ["love.months", "love.best"],
             "ask": "앞으로 12개월 월운 시그널을 풀어 줘: 밀고 나갈 달, 다듬을 달, 조심할 달과 그 이유. 사실표의 달만 쓴다."},
            {"id": "partner", "nav": "잘 맞는 상대", "emoji": "💝", "title": "잘 맞는 상대 미리보기",
             "widgets": [], "pick": ["love.ziwei_spouse", "love.venus", "love.moon", "love.spouse_seat"],
             "ask": "부처궁 주성·금성·배우자궁으로 본 잘 맞는 상대의 인상, 성격, 어울리는 분야, 둘이 하게 될 연애의 장면을 그려 줘. 예언이 아니라 결을 설명하는 것이다."},
            {"id": "timing", "nav": "타이밍", "emoji": "🗓️", "title": "움직일 때와 쉴 때",
             "widgets": ["years:love"], "pick": ["love.years", "love.best", "love.this_year", "natal.dayun"],
             "ask": "앞으로 3년 흐름과, 지금 움직일지 기다릴지를 사실표 근거로 말해 줘."},
            {"id": "final", "nav": "최종 진단", "emoji": "✨", "title": "최종 진단",
             "widgets": [], "pick": ["love", "natal.character"],
             "ask": "연애 탭 전체를 정리하는 결론과, 오늘부터 할 한 가지."},
        ]},
    "career": {
        "title": "일과 커리어", "hand": "Career", "theme": "sky",
        "sub": "사주로 읽는 일하는 방식과 때",
        "chapters": [
            {"id": "wonguk", "nav": "원국", "emoji": "📜", "title": "일로 읽는 나의 원국",
             "widgets": ["wonguk"], "pick": ["natal", "career.guanlu", "career.guan"],
             "ask": "원국을 일 관점에서 풀어 줘: 일간 기질, 관성(직장·책임)과 인성(뒷받침), 관록궁, 일에 닿는 신살·귀인."},
            {"id": "why", "nav": "일 기질", "emoji": "👁️", "title": "일에서의 나의 기질",
             "widgets": [], "pick": ["natal.strength", "natal.geguk", "natal.geguk_mean", "natal.dayun", "career"],
             "ask": "일에서 강점과 걸림돌이 생기는 구조적 이유를 풀고, 스스로 확인해 볼 일 습관 체크리스트를 만들어 줘."},
            {"id": "map", "nav": "커리어 지도", "emoji": "🧭", "title": "나의 커리어 지도",
             "widgets": [], "pick": ["career", "natal.astro"],
             "ask": "잘 맞는 일의 결과 분야(사실표 fit_jobs·관록궁 삼방), 조직에서의 자리, 협업 방식을 카드로 풀어 줘."},
            {"id": "howto", "nav": "실전", "emoji": "💼", "title": "성과를 내는 실전 설계",
             "widgets": [], "pick": ["career", "natal.character"],
             "ask": "사실표 근거로 일의 행동 설계를 3단계(steps)로, 그리고 피할 것을 알려 줘."},
            {"id": "calendar", "nav": "월별", "emoji": "📊", "title": "월별 커리어 시그널",
             "widgets": ["calendar:career"], "pick": ["career.months", "career.best"],
             "ask": "앞으로 12개월 커리어 시그널을 풀어 줘: 밀고 나갈 달과 다듬을 달, 이유. 사실표의 달만 쓴다."},
            {"id": "mentor", "nav": "귀인", "emoji": "🤝", "title": "나를 끌어줄 귀인 미리보기",
             "widgets": [], "pick": ["natal.classic_sinsal", "natal.guiin", "career.palaces"],
             "ask": "천을귀인·관록궁 삼방으로 본, 일에서 도움이 되는 사람의 결(인상·일하는 방식)과 그런 사람을 만나는 자리를 풀어 줘. 예언이 아니라 결을 설명한다."},
            {"id": "timing", "nav": "타이밍", "emoji": "🗓️", "title": "움직일 때와 다질 때",
             "widgets": ["years:career"], "pick": ["career.years", "career.best", "natal.dayun"],
             "ask": "앞으로 3년 커리어 흐름과 지금 할 일을 사실표 근거로 말해 줘."},
            {"id": "final", "nav": "최종 진단", "emoji": "✨", "title": "최종 진단",
             "widgets": [], "pick": ["career", "natal.character"],
             "ask": "직장 탭 전체 결론과 이번 주에 할 한 가지."},
        ]},
    "money": {
        "title": "돈의 흐름", "hand": "Money", "theme": "mint",
        "sub": "사주로 읽는 돈이 모이는 방식",
        "chapters": [
            {"id": "wonguk", "nav": "원국", "emoji": "📜", "title": "돈으로 읽는 나의 원국",
             "widgets": ["wonguk"], "pick": ["natal", "money.caibo", "money.cai"],
             "ask": "원국을 돈 관점에서 풀어 줘: 재성(돈의 별)·식상(돈을 낳는 재주)·비겁, 재백궁, 돈에 닿는 신살·귀인(암록·금여 등)."},
            {"id": "why", "nav": "모이고 새는 이유", "emoji": "👁️", "title": "돈이 모이고 새는 이유",
             "widgets": [], "pick": ["natal.strength", "natal.elements", "natal.dayun", "money"],
             "ask": "돈이 모이는 구조와 새기 쉬운 구조를 풀고, 스스로 확인할 돈 습관 체크리스트를 만들어 줘."},
            {"id": "map", "nav": "재물 지도", "emoji": "🗺️", "title": "나의 재물 지도",
             "widgets": [], "pick": ["money", "natal.astro"],
             "ask": "버는 방식(월급형·사업형·재주형)의 결, 재백궁 삼방, 점성 차트의 돈 관련 신호를 카드로 풀어 줘. 투자 조언은 하지 않는다."},
            {"id": "howto", "nav": "습관", "emoji": "💰", "title": "돈을 지키는 습관 설계",
             "widgets": [], "pick": ["money", "natal.character"],
             "ask": "사실표 근거로 돈 습관 설계를 3단계(steps)로, 피할 것을 알려 줘. 구체 투자 상품은 권하지 않는다."},
            {"id": "calendar", "nav": "월별", "emoji": "📊", "title": "월별 머니 시그널",
             "widgets": ["calendar:money"], "pick": ["money.months", "money.best"],
             "ask": "앞으로 12개월 돈의 시그널: 들어오기 좋은 달, 지출을 조심할 달과 이유. 사실표의 달만 쓴다."},
            {"id": "partner", "nav": "재물 귀인", "emoji": "🤝", "title": "재물 귀인 미리보기",
             "widgets": [], "pick": ["natal.guiin", "natal.classic_sinsal", "money.palaces"],
             "ask": "돈 흐름에 도움이 되는 사람·자리의 결을 풀어 줘. 예언이 아니라 결을 설명한다."},
            {"id": "timing", "nav": "타이밍", "emoji": "🗓️", "title": "모을 때와 쓸 때",
             "widgets": ["years:money"], "pick": ["money.years", "money.best", "natal.dayun"],
             "ask": "앞으로 3년 돈 흐름과 지금 할 일을 사실표 근거로 말해 줘."},
            {"id": "final", "nav": "최종 진단", "emoji": "✨", "title": "최종 진단",
             "widgets": [], "pick": ["money", "natal.character"],
             "ask": "금전 탭 전체 결론과 이번 달에 할 한 가지."},
        ]},
    "life": {
        "title": "평생 흐름", "hand": "Life", "theme": "lilac",
        "sub": "원국·대운·자미 대한으로 보는 인생의 결",
        "chapters": [
            {"id": "wonguk", "nav": "원국", "emoji": "📜", "title": "원국 완전 풀이",
             "widgets": ["wonguk"], "pick": ["natal"],
             "ask": "원국 전체를 풀어 줘: 일간, 오행 분포, 신강약·격국·용신, 신살·귀인, 자미 명궁·사화, 점성 태양·달·상승궁."},
            {"id": "decades", "nav": "연대별", "emoji": "🕰️", "title": "연대별 나의 모습",
             "widgets": ["decades"], "pick": ["life.phases", "life.decades", "life.current"],
             "ask": "연대별 흐름(청년·중년·장년)을 풀고, 지금 연대에서 중요한 것을 말해 줘."},
            {"id": "dayun", "nav": "대운", "emoji": "🌊", "title": "대운 여덟 걸음",
             "widgets": [], "pick": ["life.dayun_narr", "natal.dayun"],
             "ask": "대운(10년 단위 큰 흐름) 여덟 걸음을 차례로 풀고, 지금 대운의 과제를 말해 줘."},
            {"id": "years", "nav": "3년", "emoji": "🗓️", "title": "앞으로 3년",
             "widgets": ["years:love", "years:career", "years:money"], "pick": ["love.years", "career.years", "money.years", "life.years"],
             "ask": "앞으로 3년을 연애·일·돈을 함께 놓고 풀어 줘. 해마다 무게가 실리는 영역."},
            {"id": "final", "nav": "최종 진단", "emoji": "✨", "title": "평생 흐름 최종 진단",
             "widgets": [], "pick": ["natal", "life.current"],
             "ask": "인생 전체 흐름의 결론과 지금 세울 방향."},
        ]},
}


# ---------------------------------------------------------------- 사실 고르기


def _get(facts: dict, path: str):
    cur = facts
    for part in path.split("."):
        cur = cur.get(part) if isinstance(cur, dict) else None
        if cur is None:
            return None
    return cur


def pick(facts: dict, paths: list[str]) -> dict:
    out = {"meta": facts["meta"]}
    for p in paths:
        v = _get(facts, p)
        if v is not None:
            out[p] = v
    return out


def spec(tab: str, chapter: str) -> dict:
    ch = next((c for c in TABS[tab]["chapters"] if c["id"] == chapter), None)
    if ch is None:
        raise ValueError("없는 챕터")
    return ch


def cache_key(tab: str, chapter: str, facts_part: dict) -> str:
    blob = json.dumps({"v": PROMPT_VERSION, "model": ai.AI_MODEL, "tab": tab, "ch": chapter,
                       "facts": facts_part}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- 정리·검사

_CJK = re.compile("[" + chr(0x4E00) + "-" + chr(0x9FFF) + chr(0x3040) + "-" + chr(0x30FF) + "]")
_EMOJI = re.compile("[" + chr(0x1F300) + "-" + chr(0x1FAFF) + chr(0x2600) + "-" + chr(0x27BF) + "]")


def _clean(s) -> str:
    s = str(s or "").strip()
    s = s.replace(chr(0x2014), ", ").replace(chr(0x2013), "~")
    s = _CJK.sub("", s)
    s = _EMOJI.sub("", s)
    # 지어낸 확률을 막는다: 퍼센트가 든 문장은 뺀다
    s = s.replace("확률이 높아", "쪽으로 기울기 쉬워").replace("확률이 높은", "쪽으로 기울기 쉬운")
    if "%" in s or "퍼센트" in s or "확률" in s:
        s = " ".join(x for x in re.split(r"(?<=[.!?])\s+", s)
                     if "%" not in x and "퍼센트" not in x and "확률" not in x)
    return s.strip()


def normalize(obj: dict) -> dict:
    """AI 답을 화면이 기대하는 모양으로 정리한다. 모양이 틀리면 ValueError."""
    blocks = []
    for b in obj.get("blocks") or []:
        if not isinstance(b, dict) or b.get("type") not in BLOCK_TYPES:
            continue
        t = b["type"]
        if t in ("text", "quote", "callout"):
            body = _clean(b.get("body"))
            if body:
                blocks.append({"type": t, "title": _clean(b.get("title")), "body": body})
        elif t == "checklist":
            items = [_clean(x) for x in (b.get("items") or []) if _clean(x)]
            if items:
                blocks.append({"type": t, "title": _clean(b.get("title")), "items": items[:8]})
        else:
            items = [{"title": _clean(x.get("title")), "body": _clean(x.get("body"))}
                     for x in (b.get("items") or []) if isinstance(x, dict) and _clean(x.get("body"))]
            if items:
                blocks.append({"type": t, "title": _clean(b.get("title")), "items": items[:6]})
    if sum(1 for b in blocks if b["type"] == "text") < 1:
        raise ValueError("풀이 문단이 없어")
    return {"headline": _clean(obj.get("headline"))[:60], "lead": _clean(obj.get("lead")),
            "blocks": blocks[:8], "closing": _clean(obj.get("closing"))}


# ---------------------------------------------------------------- 계산 문장 대체


def _lines(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    if isinstance(v, list):
        out = []
        for x in v:
            if isinstance(x, str):
                out.append(x)
            elif isinstance(x, dict):
                if "ym" in x:
                    out.append(f"{x['label']} {x['ganzhi']}: {x['tag']}"
                               + (f" ({', '.join(x['why'])})" if x.get("why") else ""))
                elif "year" in x and "tag" in x:
                    out.append(f"{x['year']}년 {x['ganzhi']}: {x['tag']}"
                               + (f" ({', '.join(x['why'])})" if x.get("why") else ""))
                elif "lines" in x:
                    out.append(f"{x.get('name', '')}: " + " ".join(x["lines"]))
        return out
    if isinstance(v, dict):
        out = []
        for k, x in v.items():
            if isinstance(x, (str, int)) and k not in ("hour_known",):
                out.append(f"{k}: {x}")
            else:
                out += _lines(x)
        return out
    return [str(v)]


def rule_chapter(tab: str, chapter: str, part: dict) -> dict:
    """AI 없이 사실표 문장으로 만든 챕터 (같은 블록 모양)."""
    ch = spec(tab, chapter)
    blocks = []
    for path, v in part.items():
        if path == "meta":
            continue
        lines = [_clean(x) for x in _lines(v) if _clean(x)]
        if not lines:
            continue
        blocks.append({"type": "text", "title": "", "body": " ".join(lines[:6])})
        if len(blocks) >= 6:
            break
    if not blocks:
        blocks = [{"type": "text", "title": "", "body": "이 챕터에 쓸 계산 결과가 없어."}]
    return {"headline": ch["title"], "lead": "계산 결과를 그대로 정리했어. (AI 풀이를 쓸 수 없을 때의 요약본)",
            "blocks": blocks, "closing": ""}


# ---------------------------------------------------------------- 생성


def generate(tab: str, chapter: str, facts: dict, use_ai: bool = True) -> dict:
    """챕터 풀이. 저장해 둔 것이 있으면 그대로, 없으면 AI 로 만들고 저장한다."""
    ch = spec(tab, chapter)
    part = pick(facts, ch["pick"])
    key = cache_key(tab, chapter, part)
    hit = content_store.get_chapter(key)
    if hit:
        return hit
    if use_ai and ai.available():
        prompt = ("[사실표]\n" + json.dumps(part, ensure_ascii=False, indent=1)
                  + f"\n\n[탭] {TABS[tab]['title']}\n[챕터] {ch['title']}\n[요청] {ch['ask']}"
                  + "\n\nJSON 하나로 답해.")
        for _ in range(2):
            try:
                body = normalize(ai.run_json(SYSTEM, prompt))
                content_store.put_chapter(key, tab, chapter, "ai", body)
                body["source"] = "ai"
                return body
            except (RuntimeError, ValueError):
                continue
    body = rule_chapter(tab, chapter, part)
    body["source"] = "rule"
    return body          # 계산 문장 대체본은 저장하지 않는다 (다음에 AI 로 다시 시도)


def outline() -> dict:
    """화면이 쓰는 탭·챕터 목록 (내용 없이)."""
    return {t: {"title": v["title"], "hand": v["hand"], "theme": v["theme"], "sub": v["sub"],
                "chapters": [{"id": c["id"], "emoji": c["emoji"],
                              "title": c["title"], "widgets": c["widgets"]} for c in v["chapters"]]}
            for t, v in TABS.items()}
