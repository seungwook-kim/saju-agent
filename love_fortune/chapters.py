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

PROMPT_VERSION = "ch-8"   # ch-8: 나쁜 신호도 분명하게, 사실표에 없는 용어 금지 (2026-09-28)

SYSTEM = """너는 정통 사주명리·자미두수·서양 점성술을 함께 보는 다정한 상담가다.
아래 규칙을 반드시 지킨다.
1. 사용자가 준 '사실표'에 있는 계산 결과만 근거로 쓴다. 사실표에 없는 것
   (과거 경험, 직업, 성격 단정, 인연의 수, 확률, 퍼센트, 사실표에 없는 날짜나 나이)은 절대 지어내지 않는다.
   시기를 말할 때는 사실표에 나온 달·해만 쓴다. 숫자는 사실표에 있는 것만 쓴다.
2. 미래를 확정하지 않는다. '~할 것이다', '100%', '확률', '운명의 상대' 같은 말은 쓰지 않는다.
   하지만 좋은 것만 골라 말하지 않는다. 사실표에 나쁜 신호(충·형·파·해, 화기, 조심·주의 신호, 낮은 점수,
   여러 체계가 같이 조심을 가리킴)가 있으면 돌려 말하지 말고 분명하고 강하게 말한다 ("이건 안 좋은 신호야",
   "이 달은 정말 조심해"). 좋은 신호와 나쁜 신호가 같이 있으면 둘 다 말한다. 나쁜 신호를 좋은 말로 덮지 않는다.
3. 별·궁·십신·신살 같은 용어가 나오면 그 자리에서 괄호로 쉬운 뜻을 붙인다.
4. 친근한 반말(…야, …해, …거든)로, 점술가가 마주 앉아 말해 주듯 쓴다. 과장하지 않되, 나쁜 건 나쁘다고 분명히 말한다.
5. 한자·일본어를 쓰지 않는다. 긴 줄표(엠 대시)를 쓰지 않는다. 이모지를 쓰지 않는다.
6. 건강·법률·투자 같은 중요한 결정은 대신 내려 주지 않고 전문가와 상의하라고 권한다.
7. 체계의 용어를 섞지 않는다. 배우자궁은 사주의 일지(배우자 자리)이고, 부처궁은 자미두수의 궁이다. 둘을 같은 것이라고 말하지 않는다.
8. 사실표 meta.hour_known 이 false 이면 태어난 시간을 모르는 것이다. 자미두수 명반·상승궁·하우스는 계산하지 않았다고만 말하고 풀이하지 않는다.
9. 나이는 meta.age(만 나이)를 쓴다. 세는나이가 필요한 문장은 사실표에 적힌 대로 '세는나이'라고 밝힌다.
10. 출력은 JSON 객체 하나만 쓴다. 설명이나 코드 울타리를 붙이지 않는다.
11. 사실표에 없는 별 이름(자미두수 주성·사화), 궁 이름, 신살, 십신, 별자리, 행성은 쓰지 않는다. 절대 지어내지 않는다.
    사실표에 없는 걸 물어보는 챕터면 "계산에 그 정보는 없어"라고 말한다.
12. 여러 가지를 나열할 때는 text 블록 한 문단에 늘어놓지 말고 steps 나 checklist 블록으로 나눠 읽기 쉽게 쓴다.

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
             "pick": ["newyear.year", "newyear.ganzhi", "newyear.age", "newyear.age_kr", "newyear.god", "newyear.rel",
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
             "ask": "원국 전체를 풀어 줘: 일간, 오행 분포, 신강약·격국·용신(억부와 계절로 본 조후를 함께, 둘이 다르면 다르다고), 신살·귀인, 자미 명궁·사화, 점성 태양·달·상승궁."},
            {"id": "love_nature", "emoji": "💞", "title": "타고난 연애의 결",
             "widgets": ["animals"],
             "pick": ["natal.character", "love.spouse_star", "love.spouse_seat", "love.day_stage", "love.dohwa",
                      "love.hongyeom", "love.ziwei_spouse", "love.venus", "love.moon", "love.meet_paths", "love.animals"],
             "ask": "타고난 연애의 결을 풀어 줘: 연애 기질, 배우자성·배우자궁, 도화·홍염, 끌리는 상대와 잘 맞는 상대의 결(부처궁·금성·달), 인연이 들어오는 자리, 띠 궁합(사실표 분류 그대로). 예언이 아니라 결을 설명한다."},
            {"id": "love_flow", "emoji": "📊", "title": "연애 흐름: 12개월과 3년",
             "widgets": ["calendar:love", "years:love", "consensus:love"], "pick": ["love.months", "love.years", "love.best", "love.this_year"],
             "ask": "앞으로 12개월과 3년의 연애 흐름을 풀어 줘: 밀고 나갈 때, 다듬을 때와 그 이유. 사실표의 달·해만 쓴다."},
            {"id": "career_nature", "emoji": "🧭", "title": "타고난 일의 결",
             "widgets": [],
             "pick": ["natal.character", "natal.strength", "natal.geguk", "natal.geguk_mean", "natal.yongsin", "natal.johu",
                      "career.guanlu", "career.guan", "career.palaces", "career.fit_jobs", "career.extra",
                      "natal.classic_sinsal", "natal.guiin", "natal.astro"],
             "ask": "타고난 일의 결을 풀어 줘: 일하는 기질, 관성·관록궁, 잘 맞는 분야, 조직에서의 자리, 도움이 되는 사람(귀인)의 결. 예언이 아니라 결을 설명한다."},
            {"id": "career_flow", "emoji": "📈", "title": "일의 흐름: 12개월과 3년",
             "widgets": ["calendar:career", "years:career", "consensus:career"], "pick": ["career.months", "career.years", "career.best", "natal.dayun"],
             "ask": "앞으로 12개월과 3년의 일 흐름을 풀어 줘: 밀고 나갈 때, 다질 때와 그 이유. 사실표의 달·해만 쓴다."},
            {"id": "money_nature", "emoji": "🪙", "title": "타고난 돈의 결",
             "widgets": [],
             "pick": ["natal.character", "natal.strength", "natal.elements", "natal.yongsin", "natal.johu",
                      "money.caibo", "money.cai",
                      "money.palaces", "money.extra", "natal.guiin", "natal.astro"],
             "ask": "타고난 돈의 결을 풀어 줘: 재성·식상·비겁, 재백궁, 돈이 모이는 구조와 새기 쉬운 구조, 버는 방식의 결. 투자 조언은 하지 않는다."},
            {"id": "money_flow", "emoji": "💹", "title": "돈의 흐름: 12개월과 3년",
             "widgets": ["calendar:money", "years:money", "consensus:money"], "pick": ["money.months", "money.years", "money.best"],
             "ask": "앞으로 12개월과 3년의 돈 흐름을 풀어 줘: 들어오기 좋은 때, 지출을 조심할 때와 이유. 사실표의 달·해만 쓴다. 투자 조언은 하지 않는다."},
            {"id": "decades", "emoji": "🕰️", "title": "연대별 나의 모습",
             "widgets": ["decades"], "pick": ["life.phases", "life.decades", "life.current"],
             "ask": "연대별 흐름(청년·중년·장년)을 풀고, 지금 연대에서 중요한 것을 말해 줘."},
            {"id": "dayun", "emoji": "🌊", "title": "대운 여덟 걸음",
             "widgets": ["dayunrel"], "pick": ["life.dayun_narr", "life.dayun_rel", "natal.dayun"],
             "ask": "대운(10년 단위 큰 흐름) 여덟 걸음을 차례로 풀고, 지금 대운의 과제를 말해 줘. "
                    "각 대운이 원국의 어느 자리(해·달·날·시)와 합·충·형·파·해로 만나는지는 사실표(life.dayun_rel) 그대로만 쓴다."},
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
_AGE = re.compile(r"(\d+)\s*(살|세|개월)")
_SURE = re.compile("반드시|틀림없|할 것이다|될 것이다|올 것이다|운명의 상대")
# 강하게 말하는 조언은 허용한다 ("반드시 조심해"). 미래를 못 박는 말은 계속 막는다 (2026-09-28 사용자: 강하게 말할 땐 말해)
_SURE_OK = re.compile("반드시 (조심|주의|피해|피하|확인|챙기|챙겨|점검|대비|멈춰|쉬어)")

# 사실표에 있어야만 쓸 수 있는 용어 (지어낸 별·궁·신살을 막는다). 두 글자 이상만.
_SYSTEM_WORDS = ("자미두수", "점성술", "사주명리", "사주팔자", "사주")          # 체계 이름은 늘 허용 (용어 검사 전에 지운다)
DOMAIN_TERMS = tuple(sorted({
    # 자미두수 주성·사화·궁
    "자미", "천기", "무곡", "천동", "염정", "천부", "태음", "탐랑", "거문", "천상", "천량", "칠살", "파군",
    "화록", "화권", "화과", "화기", "문창", "문곡", "좌보", "우필", "천괴", "천월", "녹존", "경양", "타라", "화성성", "영성",
    "형제궁", "부처궁", "자녀궁", "재백궁", "질액궁", "천이궁", "노복궁", "관록궁", "전택궁", "복덕궁", "부모궁",
    # 사주 십신·신살·십이운성
    "비견", "겁재", "식신", "상관", "편재", "정재", "편관", "정관", "편인", "정인",
    "도화", "홍염", "역마", "화개", "공망", "천을귀인", "괴강", "고진", "과숙", "양인", "백호", "원진", "귀문",
    "홍란", "천희", "장성", "문창귀인", "학당", "현침", "탕화",
    "장생", "관대", "건록", "제왕",
    # 점성술 별자리·행성
    "양자리", "황소자리", "쌍둥이자리", "게자리", "사자자리", "처녀자리", "천칭자리", "전갈자리", "사수자리",
    "염소자리", "물병자리", "물고기자리", "수성", "금성", "목성", "토성", "천왕성", "해왕성", "명왕성",
}, key=len, reverse=True))


def terms_ok(sent: str, text: str) -> bool:
    """문장에 나온 전문 용어가 모두 사실표(text)에 있으면 통과. 궁은 '궁'을 뺀 이름으로도 찾는다."""
    s = sent
    for w in _SYSTEM_WORDS:
        s = s.replace(w, " ")
    for t in DOMAIN_TERMS:
        if t in s:
            base = t[:-1] if t.endswith("궁") and len(t) > 2 else t
            if t not in text and base not in text:
                return False
            s = s.replace(t, " ")                  # 긴 말부터 지워 짧은 말이 겹쳐 걸리지 않게 (천을귀인 > 귀인)
    return True
# 챕터의 틀로 늘 쓰는 기간 말 (대운 10년, 앞으로 12개월·3년). 사람마다 다른 숫자가 아니라 허용한다
_GENERIC = re.compile("10년|12개월|3년")


def _grounded_sentence(sent: str, allowed: set[str], text: str | None = None) -> bool:
    """문장 속 숫자와 전문 용어가 모두 사실표에 있으면 통과. '3단계', '2가지', 'STEP 1' 같은 순서 표기는 허용."""
    if _SURE.search(_SURE_OK.sub("", sent)):
        return False
    if text is not None and not terms_ok(sent, text):
        return False
    if text is not None:
        # 나이·기간은 숫자만 맞으면 안 되고 그 나이·기간으로 사실표에 있어야 한다 ('37살' 이 점수 37 로 통과하지 않게)
        for n, unit in _AGE.findall(sent):
            if unit in ("살", "세") and not any(k in text for k in (f"{n}살", f"{n}세", f'"age": {n}', f"만 {n}")):
                return False
            if unit == "개월" and f"{n}개월" not in text:
                return False
    for step, n, unit in _NUM_CTX.findall(_GENERIC.sub("", sent)):
        counting = (step or unit) and float(n) <= 10
        if n not in allowed and not counting:
            return False
    return True


def _ground_text(s: str, allowed: set[str], text: str | None = None) -> str:
    return " ".join(x for x in _SENT.split(s or "") if x and _grounded_sentence(x, allowed, text)).strip()


_LIST_NO = re.compile(r"^\s*(\d{1,2})[.)]\s+")


def ground_reply(reply: str, context: str) -> str:
    """상담 답 거름망: 상담 요약(context)에 없는 숫자·용어가 든 문장, 미래를 못 박는 문장을 뺀다.
    줄 단위로 거르고 '1. 2. 3.' 번호 줄은 번호를 빼고 검사한 뒤, 남은 줄끼리 번호를 다시 매긴다."""
    allowed = set(_NUM.findall(context))
    out, n = [], 0
    for line in (reply or "").splitlines():
        m = _LIST_NO.match(line)
        body = line[m.end():] if m else line
        kept = _ground_text(body, allowed, context)
        if not kept:
            continue
        if m:
            n += 1
            out.append(f"{n}. {kept}")
        else:
            out.append(kept)
    return "\n".join(out).strip()


def numbered(reply: str) -> str:
    """계산값 답(' / ' 로 이은 것)을 '머리말' + '1. 2. 3.' 줄로 바꿔 읽기 쉽게 한다."""
    if " / " not in reply:
        return reply
    head, sep, rest = reply.partition(": ")
    if not sep or " / " in head:
        head, rest = "", reply
    items = [x.strip().rstrip(".") for x in rest.split(" / ") if x.strip()]
    lines = [f"{i}. {x}." for i, x in enumerate(items, 1)]
    return ((head + ":\n") if head else "") + "\n".join(lines)


def ground(body: dict, facts_part: dict) -> dict:
    """사실표에 없는 숫자(날짜·나이·개월 수 등)나 단정 표현이 든 문장·항목을 뺀다.

    AI 가 '3개월 안에', '35세에' 처럼 사실표에 없는 숫자를 지어내는 것을 막는 마지막 거름망.
    저장된 풀이에도 읽을 때마다 적용한다.
    """
    text = json.dumps(facts_part, ensure_ascii=False)
    allowed = set(_NUM.findall(text))
    out = dict(body)
    out["headline"] = _ground_text(body.get("headline", ""), allowed, text)
    out["lead"] = _ground_text(body.get("lead", ""), allowed, text)
    out["closing"] = _ground_text(body.get("closing", ""), allowed, text)
    blocks = []
    for b in body.get("blocks", []):
        b = dict(b)
        if b["type"] in ("text", "quote", "callout"):
            b["body"] = _ground_text(b.get("body", ""), allowed, text)
            if not b["body"]:
                continue
        elif b["type"] == "checklist":
            b["items"] = [x for x in b["items"] if _grounded_sentence(x, allowed, text)]
            if not b["items"]:
                continue
        else:
            b["items"] = [dict(i, body=_ground_text(i["body"], allowed, text)) for i in b["items"]
                          if _grounded_sentence(i.get("title", ""), allowed, text)]
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
                body = normalize(ai.run_json(SYSTEM, prompt, name="chapter",
                                             meta={"tab": tab, "chapter": chapter, "prompt_version": PROMPT_VERSION}))
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
                              "title": c["title"], "widgets": c["widgets"], "pick": c["pick"]}
                             for c in v["chapters"]]}
            for t, v in TABS.items()}


def key_of(tab: str, chapter: str, facts: dict) -> str:
    """이 사실표로 만든 챕터 풀이의 저장 키."""
    return cache_key(tab, chapter, pick(facts, spec(tab, chapter)["pick"]))
