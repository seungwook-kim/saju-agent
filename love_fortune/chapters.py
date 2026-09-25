"""chapters.py, 탭별 챕터 설계와 챕터 풀이 생성 (AI + 계산 문장 대체).

탭마다 챕터 순서를 정하고, 챕터마다
- widgets: 계산값으로 그리는 화면 부품 (원국 표, 띠 카드, 월별 캘린더 등)
- pick:    AI 에게 넘길 사실표 부분
- ask:     그 챕터에서 풀어야 할 것
을 둔다. AI 는 넘겨받은 사실만 근거로 쓰고, 답은 블록(JSON)으로 받는다.
AI 를 못 쓰면 rule_chapters 의 계산 풀이로 같은 모양의 블록을 만든다 (source='rule').
"""
from __future__ import annotations

import hashlib
import json
import re

from . import ai, content_store, rule_chapters

PROMPT_VERSION = "ch-4"

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
7. 체계의 용어를 섞지 않는다. 배우자궁은 사주의 일지(배우자 자리)이고, 부처궁은 자미두수의 궁이다. 둘을 같은 것이라고 말하지 않는다.
8. 사실표 meta.hour_known 이 false 이면 태어난 시간을 모르는 것이다. 자미두수 명반·상승궁·하우스는 계산하지 않았다고만 말하고 풀이하지 않는다.
9. 나이는 meta.age(만 나이)를 쓴다. 세는나이가 필요한 문장은 사실표에 적힌 대로 '세는나이'라고 밝힌다.
10. 출력은 JSON 객체 하나만 쓴다. 설명이나 코드 울타리를 붙이지 않는다.

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

# 탭 구성 (2026-09-25 사용자 결정)
# - 총운·연애·직장·금전은 '오늘 하루'만 본다. 총운 = 연애·직장·금전 평균 + 오늘 공통 기운.
# - 타고난 결(원국·배우자·일·돈)과 앞으로의 흐름(12개월·3년·대운)은 평생 탭에 모은다.


def _today_domain_tab(dom: str, word: str, title: str, hand: str, theme: str, emoji: str) -> dict:
    d = f"today.domains.{dom}"
    howto_pick = [d, "today.almanac"] + (["love.spouse_seat", "love.venus", "love.meet_paths"]
                                         if dom == "love" else [])
    return {
        "title": title, "hand": hand, "theme": theme,
        "sub": f"오늘 하루, {word}에 닿는 기운만 모았어",
        "chapters": [
            {"id": "score", "emoji": emoji, "title": f"오늘의 {word} 점수",
             "widgets": [f"gauge:{dom}"], "pick": [d],
             "ask": f"오늘 {word} 점수가 이렇게 나온 근거(reasons)와 세 체계가 더하고 뺀 몫(systems.points)을 풀어 줘. 오늘 하루 이야기만 한다."},
            {"id": "systems", "emoji": "🔮", "title": f"세 체계로 본 오늘 {word}",
             "widgets": [f"dsys:{dom}"], "pick": [d, "today.agreement"],
             "ask": f"사주·자미두수·점성술이 오늘 {word}을(를) 각각 어떻게 보는지, 서로 맞는 점과 엇갈리는 점을 풀어 줘. 오늘 하루 이야기만 한다."},
            {"id": "howto", "emoji": "💫", "title": "오늘 이렇게 해 봐",
             "widgets": [], "pick": howto_pick,
             "ask": f"오늘 {word}에서 해 보면 좋은 것(체크리스트)과 피할 것, 오늘 건넬 말 한마디를 사실표 근거로 알려 줘. 오늘 하루 이야기만 한다."},
            {"id": "final", "emoji": "✨", "title": f"오늘 {word} 한마디",
             "widgets": [], "pick": [d, "today.heads"],
             "ask": f"오늘 {word}을(를) 한 문단으로 정리하고, 오늘 딱 하나만 한다면 무엇을 하면 좋을지 말해 줘."},
        ]}


TABS = {
    "today": {
        "title": "오늘의 총운", "hand": "Today", "theme": "peach",
        "sub": "연애·직장·금전을 합친 오늘 하루",
        "chapters": [
            {"id": "today", "emoji": "☀️", "title": "세 체계가 본 오늘",
             "widgets": ["gauge:today", "systems"],
             "pick": ["today.agreement", "today.focus", "today.systems", "today.scores", "today.heads",
                      "today.total_reasons"],
             "ask": "오늘 총운이 연애·직장·금전 점수의 평균에 오늘 공통 기운을 더한 값이라는 점을 짚고, 세 체계(사주·자미두수·점성술)가 오늘을 어떻게 보는지, 서로 맞는 점과 엇갈리는 점, 가장 힘이 실린 영역과 쉬어 갈 영역을 풀어 줘."},
            {"id": "me", "emoji": "🪞", "title": "오늘의 나",
             "widgets": [], "pick": ["today.systems", "today.heads", "today.keywords", "natal.character", "natal.ilgan"],
             "ask": "오늘 내 기운의 결(십이운성·일진과의 관계)을 바탕으로 오늘 어떤 모습으로 지내면 좋은지 그려 줘."},
            {"id": "todo", "emoji": "✅", "title": "오늘 할 일과 피할 일",
             "widgets": ["almanac"], "pick": ["today.almanac", "today.heads", "today.domains"],
             "ask": "오늘 택일(생기복덕·건제·황도흑도·손 없는 날)과 영역별 팁을 근거로, 오늘 하면 좋은 일 체크리스트와 피할 일을 정리해 줘."},
            {"id": "final", "emoji": "✨", "title": "오늘의 한마디",
             "widgets": [], "pick": ["today.agreement", "today.focus", "today.heads", "today.keywords"],
             "ask": "오늘을 한 문단으로 정리하고, 오늘 딱 하나만 한다면 무엇을 하면 좋을지 말해 줘."},
        ]},
    "love": _today_domain_tab("love", "연애", "오늘의 연애", "Love", "rose", "💗"),
    "career": _today_domain_tab("career", "직장", "오늘의 직장운", "Career", "sky", "💼"),
    "money": _today_domain_tab("money", "금전", "오늘의 금전운", "Money", "mint", "💰"),
    "newyear": {
        "title": "신년운세", "hand": "New Year", "theme": "peach",
        "sub": "다가올 한 해를 사주·자미두수·점성술로 미리 봐",
        "chapters": [
            {"id": "overview", "emoji": "🎍", "title": "한 해를 여는 기운",
             "widgets": ["ny"],
             "pick": ["newyear.year", "newyear.ganzhi", "newyear.age", "newyear.god", "newyear.rel",
                      "newyear.signals", "newyear.dayun_note", "natal.character"],
             "ask": "그해 간지가 나에게 어떤 기운인지(십신), 배우자 자리와의 관계, 연애·일·돈 세운 시그널, 교운기 여부로 그해의 큰 그림을 풀어 줘. 사실표의 해만 말한다."},
            {"id": "tojeong", "emoji": "📖", "title": "토정비결",
             "widgets": ["tojeong"], "pick": ["newyear.year", "newyear.tojeong"],
             "ask": "그해 토정비결 괘(세 자리 번호)와 괘사(독음)·풀이(mean)를 쉬운 말로 풀어 줘. 괘사가 말하지 않는 구체적 사건·날짜·금액은 지어내지 않는다. 토정비결은 조선 후기 필사본으로 전하는 옛 점서라는 점을 가볍게 밝힌다."},
            {"id": "months", "emoji": "📅", "title": "달마다 흐름",
             "widgets": ["nycal"], "pick": ["newyear.year", "newyear.months", "newyear.best"],
             "ask": "그해 열두 달을 연애·일·돈으로 나눠 밀고 나갈 달과 조심할 달, 그 이유를 풀어 줘. 사실표의 달만 쓴다."},
            {"id": "ziwei", "emoji": "🧭", "title": "자미두수로 본 한 해",
             "widgets": [], "pick": ["newyear.year", "newyear.ziwei"],
             "ask": "그해 유년 명궁이 걸린 자리와 그해 사화(록권과기)가 붙는 자리를 풀어 줘. 사실표 ziwei 가 없으면 태어난 시간을 몰라 보지 못했다고만 말한다."},
            {"id": "sky", "emoji": "🪐", "title": "하늘의 큰 별",
             "widgets": [], "pick": ["newyear.year", "newyear.sky"],
             "ask": "그해 목성(기회)과 토성(과제)이 지나는 별자리와 내 하우스, 회귀 여부로 한 해의 기회와 과제를 풀어 줘."},
            {"id": "final", "emoji": "✨", "title": "한 해 한마디",
             "widgets": [], "pick": ["newyear.year", "newyear.signals", "newyear.best", "newyear.dayun_note"],
             "ask": "그해를 한 문단으로 정리하고, 그해 꼭 챙길 한 가지를 말해 줘."},
        ]},
    "life": {
        "title": "평생 흐름", "hand": "Life", "theme": "lilac",
        "sub": "타고난 결과 앞으로의 흐름 (연애·일·돈)",
        "chapters": [
            {"id": "ilju", "emoji": "🎴", "title": "나의 일주",
             "widgets": ["ilju"], "pick": ["natal.ilju", "natal.character", "love.spouse_seat", "love.day_stage"],
             "ask": "일주(태어난 날의 간지)를 일간의 비유와 일지의 띠 동물, 십이운성, 배우자 자리의 십성, 일주에 붙은 신살로 풀어 줘. 색 이름(modern)은 요즘 표현이라고 밝힌다."},
            {"id": "wonguk", "emoji": "📜", "title": "원국 완전 풀이",
             "widgets": ["wonguk", "mingpan", "wheel"], "pick": ["natal"],
             "ask": "원국 전체를 풀어 줘: 일간, 오행 분포, 신강약·격국·용신, 신살·귀인, 자미 명궁·사화, 점성 태양·달·상승궁."},
            {"id": "love_nature", "emoji": "💞", "title": "타고난 연애의 결",
             "widgets": ["animals"],
             "pick": ["natal.character", "love.spouse_star", "love.spouse_seat", "love.day_stage", "love.dohwa",
                      "love.hongyeom", "love.ziwei_spouse", "love.venus", "love.moon", "love.meet_paths", "love.animals"],
             "ask": "타고난 연애의 결을 풀어 줘: 연애 기질, 배우자성·배우자궁, 도화·홍염, 끌리는 상대와 잘 맞는 상대의 결(부처궁·금성·달), 인연이 들어오는 자리, 띠 궁합(사실표 분류 그대로). 예언이 아니라 결을 설명한다."},
            {"id": "love_flow", "emoji": "📊", "title": "연애 흐름: 12개월과 3년",
             "widgets": ["calendar:love", "years:love"], "pick": ["love.months", "love.years", "love.best", "love.this_year"],
             "ask": "앞으로 12개월과 3년의 연애 흐름을 풀어 줘: 밀고 나갈 때, 다듬을 때와 그 이유. 사실표의 달·해만 쓴다."},
            {"id": "career_nature", "emoji": "🧭", "title": "타고난 일의 결",
             "widgets": [],
             "pick": ["natal.character", "natal.strength", "natal.geguk", "natal.geguk_mean", "natal.yongsin",
                      "career.guanlu", "career.guan", "career.palaces", "career.fit_jobs", "career.extra",
                      "natal.classic_sinsal", "natal.guiin", "natal.astro"],
             "ask": "타고난 일의 결을 풀어 줘: 일하는 기질, 관성·관록궁, 잘 맞는 분야, 조직에서의 자리, 도움이 되는 사람(귀인)의 결. 예언이 아니라 결을 설명한다."},
            {"id": "career_flow", "emoji": "📈", "title": "일의 흐름: 12개월과 3년",
             "widgets": ["calendar:career", "years:career"], "pick": ["career.months", "career.years", "career.best", "natal.dayun"],
             "ask": "앞으로 12개월과 3년의 일 흐름을 풀어 줘: 밀고 나갈 때, 다질 때와 그 이유. 사실표의 달·해만 쓴다."},
            {"id": "money_nature", "emoji": "🪙", "title": "타고난 돈의 결",
             "widgets": [],
             "pick": ["natal.character", "natal.strength", "natal.elements", "natal.yongsin", "money.caibo", "money.cai",
                      "money.palaces", "money.extra", "natal.guiin", "natal.astro"],
             "ask": "타고난 돈의 결을 풀어 줘: 재성·식상·비겁, 재백궁, 돈이 모이는 구조와 새기 쉬운 구조, 버는 방식의 결. 투자 조언은 하지 않는다."},
            {"id": "money_flow", "emoji": "💹", "title": "돈의 흐름: 12개월과 3년",
             "widgets": ["calendar:money", "years:money"], "pick": ["money.months", "money.years", "money.best"],
             "ask": "앞으로 12개월과 3년의 돈 흐름을 풀어 줘: 들어오기 좋은 때, 지출을 조심할 때와 이유. 사실표의 달·해만 쓴다. 투자 조언은 하지 않는다."},
            {"id": "decades", "emoji": "🕰️", "title": "연대별 나의 모습",
             "widgets": ["decades"], "pick": ["life.phases", "life.decades", "life.current"],
             "ask": "연대별 흐름(청년·중년·장년)을 풀고, 지금 연대에서 중요한 것을 말해 줘."},
            {"id": "dayun", "emoji": "🌊", "title": "대운 여덟 걸음",
             "widgets": [], "pick": ["life.dayun_narr", "natal.dayun"],
             "ask": "대운(10년 단위 큰 흐름) 여덟 걸음을 차례로 풀고, 지금 대운의 과제를 말해 줘."},
            {"id": "final", "emoji": "✨", "title": "평생 흐름 최종 진단",
             "widgets": [], "pick": ["natal", "life.current", "love.best", "career.best", "money.best"],
             "ask": "인생 전체 흐름의 결론과 지금 세울 방향을 연애·일·돈을 함께 놓고 말해 줘."},
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


_NUM = re.compile(r"\d+(?:\.\d+)?")
_NUM_CTX = re.compile(r"(STEP\s*)?(\d+(?:\.\d+)?)\s*(단계|가지|번째|걸음|순위)?")
_SENT = re.compile(r"(?<=[.!?])\s+")
_SURE = re.compile("반드시|틀림없|할 것이다|될 것이다|올 것이다|운명의 상대")
# 챕터의 틀로 늘 쓰는 기간 말 (대운 10년, 앞으로 12개월·3년). 사람마다 다른 숫자가 아니라 허용한다
_GENERIC = re.compile("10년|12개월|3년")


def _grounded_sentence(sent: str, allowed: set[str]) -> bool:
    """문장 속 숫자가 모두 사실표에 있으면 통과. '3단계', '2가지', 'STEP 1' 같은 순서 표기는 허용."""
    if _SURE.search(sent):
        return False
    for step, n, unit in _NUM_CTX.findall(_GENERIC.sub("", sent)):
        counting = (step or unit) and float(n) <= 10
        if n not in allowed and not counting:
            return False
    return True


def _ground_text(s: str, allowed: set[str]) -> str:
    return " ".join(x for x in _SENT.split(s or "") if x and _grounded_sentence(x, allowed)).strip()


def ground(body: dict, facts_part: dict) -> dict:
    """사실표에 없는 숫자(날짜·나이·개월 수 등)나 단정 표현이 든 문장·항목을 뺀다.

    AI 가 '3개월 안에', '35세에' 처럼 사실표에 없는 숫자를 지어내는 것을 막는 마지막 거름망.
    저장된 풀이에도 읽을 때마다 적용한다.
    """
    allowed = set(_NUM.findall(json.dumps(facts_part, ensure_ascii=False)))
    out = dict(body)
    out["headline"] = _ground_text(body.get("headline", ""), allowed)
    out["lead"] = _ground_text(body.get("lead", ""), allowed)
    out["closing"] = _ground_text(body.get("closing", ""), allowed)
    blocks = []
    for b in body.get("blocks", []):
        b = dict(b)
        if b["type"] in ("text", "quote", "callout"):
            b["body"] = _ground_text(b.get("body", ""), allowed)
            if not b["body"]:
                continue
        elif b["type"] == "checklist":
            b["items"] = [x for x in b["items"] if _grounded_sentence(x, allowed)]
            if not b["items"]:
                continue
        else:
            b["items"] = [dict(i, body=_ground_text(i["body"], allowed)) for i in b["items"]
                          if _grounded_sentence(i.get("title", ""), allowed)]
            b["items"] = [i for i in b["items"] if i["body"]]
            if not b["items"]:
                continue
        blocks.append(b)
    out["blocks"] = blocks
    return out


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


# ---------------------------------------------------------------- 계산 풀이


def rule_chapter(tab: str, chapter: str, facts: dict) -> dict:
    """AI 없이 계산 결과로 쓴 챕터 (같은 블록 모양, 바로 만들어진다)."""
    spec(tab, chapter)
    body = rule_chapters.build(tab, chapter, facts)
    body["source"] = "rule"
    return body


def rule_all(facts: dict) -> dict:
    """모든 탭·챕터의 계산 풀이 {tab: {chapter: body}}. 화면이 처음에 바로 보여 준다."""
    return {t: {c["id"]: rule_chapter(t, c["id"], facts) for c in v["chapters"]} for t, v in TABS.items()}


# ---------------------------------------------------------------- 생성


def generate(tab: str, chapter: str, facts: dict, use_ai: bool = True) -> dict:
    """챕터 풀이. 저장해 둔 것이 있으면 그대로, 없으면 AI 로 만들고 저장한다."""
    ch = spec(tab, chapter)
    part = pick(facts, ch["pick"])
    key = cache_key(tab, chapter, part)
    hit = content_store.get_chapter(key)
    if hit:
        body = ground(hit, part)
        if len(body["blocks"]) >= 2:
            return body
        return rule_chapter(tab, chapter, facts)
    if use_ai and ai.available():
        prompt = ("[사실표]\n" + json.dumps(part, ensure_ascii=False, indent=1)
                  + f"\n\n[탭] {TABS[tab]['title']}\n[챕터] {ch['title']}\n[요청] {ch['ask']}"
                  + "\n\nJSON 하나로 답해.")
        for _ in range(2):
            try:
                body = normalize(ai.run_json(SYSTEM, prompt))
                content_store.put_chapter(key, tab, chapter, "ai", body)
                body = ground(body, part)
                if len(body["blocks"]) < 2:
                    raise ValueError("근거 없는 문장을 빼고 나니 남는 게 없어")
                body["source"] = "ai"
                return body
            except (RuntimeError, ValueError):
                continue
    return rule_chapter(tab, chapter, facts)   # 계산 풀이는 저장하지 않는다 (다음에 AI 로 다시 시도)


def outline() -> dict:
    """화면이 쓰는 탭·챕터 목록 (내용 없이)."""
    return {t: {"title": v["title"], "hand": v["hand"], "theme": v["theme"], "sub": v["sub"],
                "chapters": [{"id": c["id"], "emoji": c["emoji"],
                              "title": c["title"], "widgets": c["widgets"]} for c in v["chapters"]]}
            for t, v in TABS.items()}


def key_of(tab: str, chapter: str, facts: dict) -> str:
    """이 사실표로 만든 챕터 풀이의 저장 키."""
    return cache_key(tab, chapter, pick(facts, spec(tab, chapter)["pick"]))
