"""web.py, 홈페이지식 로컬 웹 UI + 채팅 상담 에이전트 (표준라이브러리만).

실행: python -m love_fortune form [--port 8765]  → http://localhost:8765

구성:
- 화면: love_fortune/static (app.html·app.css·app.js·viz.js). 서버는 JSON 만 돌려준다.
- 채팅 패널: 오늘 리포트를 아는 상담 에이전트와 대화
  * 기본 = 구독 AI 모델을 로컬 CLI 명령으로 호출 (API 키 불필요).
    CLI 명령이 없거나 실패하면 로컬 규칙 에이전트가 대신 답한다.
  * 선택 = OpenAI 호환 엔드포인트 연결 (채팅창 설정에서 endpoint/key/model 입력,
    브라우저 localStorage에만 저장, 서버에 저장 안 함)
  * LLM 에 보내는 건 개인정보를 뺀 리포트 요약과 대화뿐이다.
- 개인정보(생년월일·시간·성별·도시): 서버 메모리에만 잠시 보관, 파일·로그에 기록 안 함.
  LLM 전송 컨텍스트에는 개인정보를 제외한다.
"""
from __future__ import annotations

import html
import re
import json
import os
import secrets
import sys
import threading
import time
import urllib.request
import webbrowser
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .cli import build_report, DISCLAIMER

# token -> {"target": str, "summary": str(개인정보 제외), "created": float}
_CONTEXTS: dict[str, dict] = {}
_CONTEXTS_LOCK = threading.Lock()
CONTEXT_TTL = 6 * 3600      # 리포트 요약을 들고 있는 시간(초)
CONTEXT_MAX = 300           # 동시에 들고 있는 최대 개수
MAX_BODY = 64_000           # 요청 본문 상한(바이트)

# 요청 횟수 제한 (공개 서버에서 한 사람이 계산·AI 를 마구 두드리지 못하게). 1분 동안 IP 하나당 횟수.
# LOVE_FORTUNE_RATE=0 이면 끈다 (시험용). 프록시 뒤(Render 등)에서는 LOVE_FORTUNE_TRUST_PROXY=1 로
# X-Forwarded-For 첫 주소를 쓴다. 이 값은 속일 수 있으니, 돈이 드는 AI 는 ai.py 의 시간당 총량으로 한 번 더 막는다.
RATE_WINDOW = 60
RATE_POST = 90              # 모든 POST
RATE_CHAT = 12              # 상담 채팅 (AI 를 바로 부른다)
_HITS: dict[tuple[str, str], list[float]] = {}
_HITS_LOCK = threading.Lock()


def _rate_ok(ip: str, path: str) -> bool:
    if not _truthy(os.environ.get("LOVE_FORTUNE_RATE", "1")):
        return True
    now = time.time()
    keys = [(ip, "post", RATE_POST)] + ([(ip, "chat", RATE_CHAT)] if path == "/api/chat" else [])
    with _HITS_LOCK:
        if len(_HITS) > 5000:                       # 오래된 IP 기록은 치운다
            for k in [k for k, v in _HITS.items() if not v or now - v[-1] > RATE_WINDOW]:
                del _HITS[k]
        for ip_, kind, cap in keys:
            hits = [t for t in _HITS.get((ip_, kind), []) if now - t < RATE_WINDOW]
            _HITS[(ip_, kind)] = hits
            if len(hits) >= cap:
                return False
        for ip_, kind, _cap in keys:
            _HITS[(ip_, kind)].append(now)
    return True

# 채팅 기본 모델. 구독 인증을 쓰는 로컬 AI CLI 명령으로 부른다.
from .ai import AI_CLI, AI_MODEL  # noqa: E402,F401  (예전 이름 유지)
from .ai import LABEL as AI_LABEL  # noqa: E402  화면에 보이는 이름 (구독 AI / OpenRouter)
AI_TIMEOUT = 120


def _truthy(v) -> bool:
    return str(v).strip().lower() not in ("", "0", "false", "off", "none", "no")


def _remember(md: str, summary: str, target: str, token: str | None = None,
              facts: dict | None = None) -> str:
    """리포트 요약을 잠시 보관하고 토큰을 돌려준다.

    예전엔 넣기만 하고 지우지 않아서, watchdog 이 서버를 계속 살려두는 동안
    메모리가 끝없이 늘었다. 오래된 것부터 치운다.
    """
    token = token or secrets.token_hex(8)
    now = time.time()
    with _CONTEXTS_LOCK:
        for k in [k for k, v in _CONTEXTS.items() if now - v["created"] > CONTEXT_TTL]:
            del _CONTEXTS[k]
        while len(_CONTEXTS) >= CONTEXT_MAX:
            del _CONTEXTS[min(_CONTEXTS, key=lambda k: _CONTEXTS[k]["created"])]
        _CONTEXTS[token] = {"md": md, "summary": summary, "target": target, "created": now,
                            "facts": facts}
    return token


def _context(token: str) -> dict | None:
    with _CONTEXTS_LOCK:
        ctx = _CONTEXTS.get(token)
        if ctx and time.time() - ctx["created"] > CONTEXT_TTL:
            del _CONTEXTS[token]
            return None
        return ctx


def _clean_history(raw) -> list[dict]:
    """브라우저가 보낸 대화 기록을 역할·길이만 남기고 정리한다 (최근 10개)."""
    out = []
    for h in raw if isinstance(raw, list) else []:
        if not isinstance(h, dict) or h.get("role") not in ("user", "assistant"):
            continue
        out.append({"role": h["role"], "content": str(h.get("content", ""))[:2000]})
    return out[-10:]


# ---------------- 로컬 상담 에이전트 (오프라인) ----------------

def agent_context(birth: date, hour: int | None, minute: int, sex: str,
                  city: str, target: date) -> tuple[str, str, str]:
    """(md, 터미널텍스트, 에이전트용 PII제외 요약) 반환."""
    from .manseryuk import four_pillars, day_pillar, ganzhi_str
    from .rules import love_score, headline
    from .advise import build_advice
    from .synthesis import detailed_reading

    text, md = build_report(birth, hour, minute, sex, city, target,
                            "all", True)
    natal = four_pillars(birth, hour, minute, city)
    ts, tb = day_pillar(target)
    score, reasons, today_elem = love_score(
        natal["ilgan_stem"],
        [s for _, s in (natal["pillars"][k] for k in ("year", "month", "day", "hour"))
         if s is not None],
        ts, tb, target.isoformat(), sex)
    adv = build_advice(natal["ilgan"], today_elem, target, birth)
    ma = detailed_reading(birth, hour, minute, sex, city, target)
    ast = ma["astro"]
    zd = ma["ziwei_detail"]
    vd = ma["venus_detail"]
    score, reasons = ma["love"]["score"], ma["love"]["reasons"]
    _td = ma["today"]
    _sys = " ; ".join(f"{x['name']}({x['signal']}) " + " ".join(x["lines"]) for x in _td["systems"])
    summary = (
        f"대상일 {target.isoformat()} / 일간 {natal['ilgan']}({natal['ilgan_element']}) / "
        f"오늘 일진 {ganzhi_str(ts, tb)} / 오늘종합 {_td['agreement']} {_td['focus']} / "
        f"체계별 {_sys} / 오늘택일 {' '.join(_td['almanac']['lines'])} / "
        f"점수 {score}점, {headline(score)} / "
        f"근거: {'; '.join(reasons)} / 행운의 색 {adv['color']}, 번호 {adv['number']}, "
        f"방향 {adv['direction']}, 시간대 {adv['time']}, 장소 {', '.join(adv['places'])}, "
        f"대화팁 {'; '.join(adv['talk'])}, 피할 것 {adv['avoid']} / "
        f"{ma['guo_line']} / {ast['compat_line']} / "
        f"생명수 {adv['life_path']}({adv['life_path_vibe']}) / "
        f"타로 {adv['tarot']}({adv['tarot_line']}) / 주역 {adv['gua']}({adv['gua_line']}) / "
        f"배우자궁 {ma['god']}({ma['god_rel']}) / 상대 {ma['side']} / "
        f"관계 {ma['god_vibe']} / 관계팁 {ma['god_tip']} / 직업군 {ma['god_job']} / "
        f"{ma['star_line']} / 일주운성 {ma['stage']}({ma['stage_love']}) / "
        f"도화 {'; '.join(ma['dohwa_lines']) or '원국 도화 없음'} / {ma['hong_line']} / "
        f"올해 {ma['timing']} / {ma['daxian_line']} / {ma['liunian_line']} / "
        f"{ma['dayun_line']} / 신살 {'; '.join(ma['shensha_lines'])} / "
        f"직장운 근거 {'; '.join(ma['career']['reasons'])} / "
        f"{ma['career']['guanlu_line']} / {ma['career']['guan_line']} / "
        f"금전운 근거 {'; '.join(ma['money']['reasons'])} / "
        f"{ma['money']['caibo_line']} / {ma['money']['cai_line']} / "
        f"총운 근거 {'; '.join(ma['total']['reasons'])} / "
        f"부처궁 {ma['ziwei_main']}(인상 {zd['look']} / 성격 {zd['mind']} / "
        f"직업 {zd['job']} / 만남 {zd['meet']} / 팁 {zd['tip']}) / "
        f"생년사화 {'; '.join(ma['sihua_lines'])} / "
        f"금성 {ma['venus']}(스타일 {vd['style']} / 끌림 {vd['ideal']} / 통함 {vd['how']}) / "
        f"달 {ma['moon']}({ma['moon_need']}) / {ma['asc_line']} / "
        f"하우스 {ma['houses_line']} / 어스펙트 {ma['aspects_line']} / "
        f"총운 {ma['total']['score']}점({ma['total']['head']}) / "
        f"직장운 {ma['career']['score']}점({ma['career']['head']}) / "
        f"금전운 {ma['money']['score']}점({ma['money']['head']}) / "
        f"평생흐름 {'; '.join(p['line'] for p in ma['lifetime']['phases'])} / "
        f"현재연대 {ma['lifetime']['current']['short']} / "
        f"타고난기질 {ma['yongsin']['ilgang']} / "
        f"신강약 {ma['yongsin']['analysis']['geguk']}, "
        f"{ma['yongsin']['analysis']['strong_label']}, "
        f"용신 {ma['yongsin']['analysis']['yongsin']} / "
        f"유년열 {'; '.join(y['line'] for y in ma['lifetime']['years'])} / "
        f"이야기총운 {'; '.join(ma['stories']['total'])} / "
        f"이야기연애 {'; '.join(ma['stories']['love'])} / "
        f"이야기직장 {'; '.join(ma['stories']['career'])} / "
        f"이야기금전 {'; '.join(ma['stories']['money'])} / "
        f"이야기평생 {'; '.join(ma['stories']['life'])} / "
        f"일운표 {'; '.join(r['line'] for r in ma['ilun'])} / "
        f"이번달 {ma['month_line']} / "
        f"만남TOP3 {', '.join(ma['meet_top3'])}")
    if ma["hour_unknown"]:
        summary += f" / 시간안내 {ma['time_notice']}"
    return md, text, summary


def josa_iya(word: str) -> str:
    """'공원이야 / 카페야' 처럼 받침에 맞는 서술 조사."""
    w = word.strip()
    c = ord(w[-1]) - 0xAC00 if w else -1
    return "이야" if 0 <= c < 11172 and c % 28 else "야"


def local_agent_reply(message: str, summary: str) -> str:
    """규칙 기반 오프라인 답변. 단정적 예언 금지, 흐름체만 사용."""
    m = message.replace(" ", "")

    def has(*keys):
        return any(k in m for k in keys)

    _CHAT_STRIP = ("이야기총운 ", "이야기연애 ", "이야기직장 ", "이야기금전 ",
                   "이야기평생 ", "직장운 근거 ", "금전운 근거 ", "총운 근거 ",
                   "근거: ", "평생흐름 ", "현재연대 ", "유년열 ",
                   "타고난기질 ", "신강약 ", "직장운 ", "금전운 ", "총운 ",
                   "이번달 ", "이야기 ", "잘맞는점 ", "조심할점 ", "참고 ")

    def _strip_story(s: str) -> str:
        for _p in _CHAT_STRIP:
            if s.startswith(_p):
                return s[len(_p):]
        return s


    from .glossary import TERMS
    if has("뭐야", "뭔가요", "뭡니까", "뜻", "의미", "설명", "몰라", "모르겠") \
            or "?" in message:
        for term in sorted(TERMS, key=len, reverse=True):
            if len(term) >= 2 and term in m:
                return f"{term}: {TERMS[term]}"
        for term, pat in (("합", "합이"), ("충", "충이"), ("형", "형이"),
                          ("파", "파가"), ("해", "해가")):
            if pat in m:
                return f"{term}: {TERMS[term]}"

    if has("쉽게", "풀어서", "알기쉽게", "이야기처럼", "이야기해줘", "쉽게설명"):
        dom = "총운"
        if has("연애"):
            dom = "연애"
        elif has("직장", "회사", "업무", "취업", "면접"):
            dom = "직장"
        elif has("금전", "돈", "재물", "투자"):
            dom = "금전"
        elif has("평생", "인생", "대운", "앞으로"):
            dom = "평생"
        seg = [s for s in summary.split(" / ") if s.startswith("이야기" + dom)]
        if seg:
            return " ".join(s.split(" ", 1)[1] if " " in s else s for s in seg)

    decide = has("해야", "할까", "말까", "어떡", "이별", "헤어")
    if has("궁합", "잘맞", "조심할", "상대방", "우리둘", "우리사이") and not decide:
        seg = [s for s in summary.split(" / ")
               if s.startswith(("궁합", "잘맞는점", "조심할점", "나 일간", "상대 일간", "참고", "이야기"))]
        seg = [_strip_story(s) for s in seg]
        return ("두 사람 궁합은 이래: " + (" / ".join(seg) if seg
                else "궁합은 결과 화면의 궁합 탭에서 두 사람 생년월일을 넣으면 볼 수 있어."))

    import re as _re_wk
    import datetime as _dt_wk
    if has("이번주", "다음주", "이번달") and not decide:
        if "달" in m and "주" not in m:
            _seg_m = next((_strip_story(s) for s in summary.split(" / ")
                           if s.startswith("이번달 ")), "")
            if _seg_m:
                return "이번 달 전체 흐름은 이래: " + _seg_m
        _t_wk = _re_wk.search(r"대상일 (\d{4})-(\d{2})-(\d{2})", summary)
        _seg_wk = next((s for s in summary.split(" / ") if s.startswith("일운표 ")), "")
        _rows_wk = [r.strip() for r in _seg_wk[len("일운표 "):].split(";")] if _seg_wk else []
        if _t_wk and _rows_wk:
            _base_wk = _dt_wk.date(int(_t_wk.group(1)), int(_t_wk.group(2)), int(_t_wk.group(3)))
            _cands = []
            for _r in _rows_wk:
                _mrow = _re_wk.match(r"(\d+)/(\d+) \| \S+ \| 연애 (\d+) \| 직장 (\d+) \| 금전 (\d+)", _r)
                if not _mrow:
                    continue
                _drow = _dt_wk.date(_base_wk.year, int(_mrow.group(1)), int(_mrow.group(2)))
                _delta = (_drow - _base_wk).days
                _ok = (_delta <= 6 if "이번주" in m else
                       7 <= _delta <= 13 if "다음주" in m else
                       _drow.month == _base_wk.month)
                if _ok:
                    _tot = int(_mrow.group(3)) + int(_mrow.group(4)) + int(_mrow.group(5))
                    _cands.append((_tot, _r))
            _cands.sort(reverse=True)
            if _cands:
                _label = "이번 주" if "이번주" in m else "다음 주" if "다음주" in m else "이번 달"
                _top3 = "; ".join(r for _, r in _cands[:3])
                return f"{_label} 좋은 날 top3는 이거야: {_top3}."
        return "해당 기간 표가 없어. 리포트의 총운 탭 일운 표를 참고해줘."
    import re as _re_ilun
    _mm_ilun = _re_ilun.search(r"(\d+)일\s*(뒤|후)", m)
    if (has("내일", "모레", "일운") or _mm_ilun) and not decide:
        import datetime as _dt_ilun
        _off = 2 if "모레" in m else 1 if "내일" in m else 0
        if _mm_ilun:
            try:
                _off = int(_mm_ilun.group(1))
            except ValueError:
                pass
        _t_ilun = _re_ilun.search(r"대상일 (\d{4})-(\d{2})-(\d{2})", summary)
        if _t_ilun:
            _base = _dt_ilun.date(int(_t_ilun.group(1)), int(_t_ilun.group(2)),
                                 int(_t_ilun.group(3)))
            _want = _base + _dt_ilun.timedelta(days=_off)
            _tag = f"{_want.month}/{_want.day} |"
            _seg = next((s for s in summary.split(" / ") if s.startswith("일운표 ")), "")
            _rows = [r.strip() for r in _seg[len("일운표 "):].split(";")] if _seg else []
            _hit = next((r for r in _rows if r.startswith(_tag)), "")
            if _hit:
                return f"{_want.month}월 {_want.day}일 운세는 이래: {_hit}."
            return "그 날짜는 30일 표 밖에 있어. 리포트의 평생 탭 연도별 표를 참고해줘."

    if has("택일", "길일", "좋은날", "날짜고르", "언제가좋", "날잡기") and not decide:
        seg = [s for s in summary.split(" / ")
               if s.startswith(("택일", "상위", "이야기"))]
        seg = [_strip_story(s) for s in seg]
        return ("고른 날짜 중에서는 이래: " + (" / ".join(seg) if seg
                else "결과 화면의 길일 고르기 탭에서 기간을 넣으면 볼 수 있어."))

    if has("안녕", "하이", "헬로", "처음"):
        return ("안녕! 지금 본 사주 계산 결과를 바탕으로 같이 이야기해 줄게. "
                "연애·직장·금전·평생 흐름, 모르는 용어 같은 거 편하게 물어봐.")
    if has("배우자", "결혼", "상대", "신랑", "신부", "아내", "남편", "와이프") and not decide:
        seg = [s for s in summary.split(" / ")
               if s.startswith(("배우자궁", "상대 ", "관계 ", "관계팁", "직업군", "배우자성", "일주운성"))]
        return ("사주로 본 인연의 모습은 이래: " + " / ".join(seg)
                + ". 더 궁금하면 '어떤 사람을 만나기 쉬울까'라고 물어봐.")
    if has("이상형", "외모", "생김", "어떤사람", "만날", "만남", "직업", "인상", "스타일") \
            and not has("장소", "코스", "어디"):
        seg = [s for s in summary.split(" / ")
               if s.startswith(("부처궁", "금성", "달 ", "만남TOP3", "직업군"))]
        return ("만나기 쉬운 인연의 모습은 이래: " + " / ".join(seg)
                + ". '배우자 궁합'처럼 더 물어봐도 돼.")
    if has("도화", "홍염", "매력", "인기"):
        seg = [s for s in summary.split(" / ") if s.startswith(("도화", "홍염살", "올해", "이야기연애"))]
        seg = [_strip_story(s) for s in seg]
        return "매력·인연의 기운은 이래: " + (" / ".join(seg) if seg else "연애 탭을 같이 봐 줘.")
    if has("직장", "회사", "업무", "상사", "동료", "취업", "이직", "승진", "면접",
            "출근", "야근", "프로젝트") and not decide:
        seg = [s for s in summary.split(" / ")
               if s.startswith(("직장운", "관록궁", "원국 관성", "현재 대운", "사주 대운",
                                "직장운 근거", "이야기직장"))]
        seg = [_strip_story(s) for s in seg]
        return ("오늘 직장운은 이래: " + (" / ".join(seg) if seg else "직장 탭을 같이 봐 줘."))
    if has("금전", "돈", "재물", "투자", "저축", "월급", "지출", "쇼핑", "주식", "코인") \
            and not decide:
        seg = [s for s in summary.split(" / ")
               if s.startswith(("금전운", "재백궁", "원국 재성",
                                "금전운 근거", "이야기금전"))]
        seg = [_strip_story(s) for s in seg]
        return ("오늘 금전운은 이래: " + (" / ".join(seg) if seg else "금전 탭을 같이 봐 줘."))
    if has("총운", "오늘운", "키워드", "종합", "전반"):
        seg = [s for s in summary.split(" / ")
               if s.startswith(("총운", "오늘 일진",
                                "총운 근거", "이야기총운"))]
        seg = [_strip_story(s) for s in seg]
        return ("오늘 총운은 이래: " + (" / ".join(seg) if seg else "오늘 탭을 같이 봐 줘."))
    if has("평생", "인생", "앞으로", "노후", "말년", "초년", "중년", "여생",
            "대운", "유년", "소운", "용신", "격국", "신강", "신약",
            "기질", "타고난") and not decide:
        seg = [s for s in summary.split(" / ")
               if s.startswith(("평생흐름", "현재연대", "유년열", "초년",
                                 "중년", "말년", "타고난기질", "신강약",
                                 "이야기평생"))]
        seg = [_strip_story(s) for s in seg]
        return ("평생 흐름은 이래: " + (" / ".join(seg) if seg else "평생 탭을 같이 봐 줘."))
    if has("시기", "언제", "올해", "운성"):
        seg = [s for s in summary.split(" / ") if s.startswith(("올해", "일주운성"))]
        return "시기의 흐름은 이래: " + (" / ".join(seg) if seg else "평생 탭의 연도별 흐름을 같이 봐 줘.")
    import re as _re_wk
    import datetime as _dt_wk
    if has("점수", "총평", "어때"):
        head = summary.split("점,", 1)[1].split(" / 근거")[0] if "점," in summary else summary
        score = summary.split("/ 점수 ")[1].split("점")[0] if "/ 점수 " in summary else "?"
        reason = next((_strip_story(s) for s in summary.split(" / ") if s.startswith("근거:")), "")
        story = next((_strip_story(s) for s in summary.split(" / ")
                      if s.startswith("이야기연애")), "")
        return (f"오늘 연애운은 {score}점이야. {head} 흐름으로 보면 돼. "
                + (reason + " " if reason else "")
                + (story + " " if story else "")
                + "자세한 근거는 각 챕터의 '근거 보기'를 눌러 봐.")
    if has("색", "번호", "숫자", "방향", "시간"):
        seg = summary.split("/ 행운의 색 ")[1].split(" / ")[0] if "/ 행운의 색 " in summary else summary
        return f"오늘 행운 요소는 이렇게 나와: {seg}. 나갈 때 하나쯤 챙기면 기분 전환에 좋아."
    if has("장소", "코스", "데이트", "어디"):
        seg = summary.split("장소 ", 1)[1].split(" / ")[0] if "장소 " in summary else ""
        return (f"오늘 추천 장소는 {seg}{josa_iya(seg)}. 무리한 이벤트보다 가볍게 걷고 이야기 나누기 좋은 흐름이야. "
                "시간대는 오늘 탭의 좋은 시간대를 같이 봐 줘.")
    if has("대화", "말", "카톡", "연락", "팁", "화제"):
        seg = summary.split("대화팁 ", 1)[1].split(", 피할 것")[0] if "대화팁 " in summary else ""
        avoid = summary.split("피할 것 ", 1)[1].split(" / ")[0] if "피할 것 " in summary else ""
        return (f"대화 팁으로는 '{seg}' 같은 흐름이 좋아 보여. "
                f"반대로 '{avoid}'는 오늘은 피하는 게 좋아.")
    if has("신살", "천을", "역마", "화개", "공망", "장성", "괴강", "고진", "사주") \
            and not decide:
        seg = [s for s in summary.split(" / ")
               if s.startswith(("사주 대운", "신살", "천을", "역마", "화개",
                                 "공망", "장성", "괴강", "고진"))]
        return ("사주 대운·신살은 이래: " + (" / ".join(seg) if seg else "평생 탭을 같이 봐 줘."))
    if has("역행"):
        seg = [s for s in summary.split(" / ") if "역행" in s]
        return ("역행은 이래: " + (" / ".join(seg) if seg else "지금 역행 중인 행성은 없어."))
    if has("자미", "명궁", "부처", "도화", "사화", "명반"):
        seg = [s for s in summary.split(" / ")
               if any(k in s for k in ("부처궁", "생년사화", "대운", "유년", "오행국", "명궁", "도화"))]
        return ("자미두수 명반에서는 이렇게 나와: " + " / ".join(seg)
                + ". 궁별 전체 배치는 평생 탭의 자미두수 챕터를 같이 봐 줘.")
    if has("별자리", "금성", "달", "점성", "궁합", "하우스", "어스펙트", "상승궁"):
        seg = [s for s in summary.split(" / ")
               if any(k in s for k in ("금성", "궁합", "생명수", "상승궁", "하우스", "어스펙트", "달 "))]
        return " / ".join(seg) if seg else "평생 탭의 점성술 챕터를 같이 봐 줘."
    if has("타로", "주역", "오미쿠지", "점괘", "운세"):
        seg = [s for s in summary.split(" / ") if "타로" in s or "주역" in s or "오미쿠지" in s]
        return "오늘의 점괘는 이래: " + (" / ".join(seg) if seg else "지금 결과에는 점괘가 없어.")
    if has("내일"):
        return ("내일 운세는 '내일 운세 어때'처럼 물어보면 30일 표에서 찾아 줄게. "
                "오늘 탭에서도 앞으로 며칠 흐름을 볼 수 있어.")
    if has("고마", "감사", "좋아", "도움"):
        return "도움이 됐다니 다행이다! 좋은 흐름은 살리고, 애매한 날은 무리하지 않는 게 포인트야."
    # 스스로를 해치는 말이 분명할 때만 도움받을 곳을 알려 준다. 이별·결혼 고민에 전화번호를 붙이지 않는다
    if has("자살", "죽고싶", "죽을래", "죽어버리", "자해"):
        return ("많이 힘든 것 같아. 이건 사주로 답할 일이 아니라서, 지금 바로 믿는 사람이나 "
                "자살예방상담전화 109(24시간)와 이야기해 줘.")
    if has("우울", "외로", "힘들", "지쳐", "슬퍼"):
        return ("마음이 무거운 때구나. 사주가 답을 정해 주진 못해도, 지금 흐름이 어떤지는 같이 볼 수 있어. "
                "'이번 달 연애운 어때'나 '올해 흐름 알려줘'처럼 물어봐.")
    if has("결혼", "헤어", "이별"):
        return ("그건 네가 정할 일이라 사주로 대신 정해 주진 않을게. 대신 두 사람 흐름이나 "
                "올해 연애 흐름처럼 궁금한 걸 물어보면 계산 결과로 같이 봐 줄게.")
    return ("음, 그 질문은 지금 결과만으로는 답하기 어려워. "
            "총운·연애·직장·금전·평생 중에서 궁금한 걸 골라 물어봐 줘. "
            "모르는 용어는 '정관이 뭐야'처럼 물어보면 풀어 줄게.")


# ---------------- 선택적 LLM 연결 (OpenAI 호환) ----------------

SYSTEM_PROMPT = ("너는 '종합 사주' 리포트를 바탕으로 상담하는 다정한 상담 에이전트다. "
                 "규칙: 1) 정통 공식 기반 상세 해석임을 전제로 답한다. 2) 단정적 예언 금지 "
                 "('~할 것이다' 대신 '~하기 좋은 흐름'으로 말한다). "
                 "3) 결혼·이별·정신건강 등 중요한 주제에는 결정을 대신 내려주지 말고 "
                 "신중한 대화와 전문가 상담을 권한다. 4) 한국어로 답한다. "
                 "5) 리포트 요약에 있는 내용만 근거로 삼고, 없는 해석은 지어내지 않는다. "
                 "6) 별·궁·십신 같은 용어가 나오면 그 자리에서 뜻을 쉽게 풀어 준다. "
                 "7) 한자·일본어와 긴 줄표(em dash)는 쓰지 않는다. "
                 "8) 점술가가 말로 풀어 주듯 서너 문장 안팎으로 답한다.")

USER_PII_NOTE = "아래 컨텍스트에는 개인정보가 포함되어 있지 않다."


def llm_chat(endpoint: str, api_key: str, model: str,
             summary: str, history: list[dict], message: str) -> str:
    """OpenAI 호환 /chat/completions 호출 (표준라이브러리만).

    예전엔 방금 한 질문(message)을 빼고 지난 대화만 보내서 LLM 이 한 박자
    늦은 대화에 답했다.
    """
    # 서버가 와이파이에 열려 있으면 이 칸으로 서버가 아무 주소나 부르게 만들 수 있다.
    # file:// 등은 막고 http(s) 만 받는다.
    from urllib.parse import urlparse
    if urlparse(endpoint).scheme not in ("http", "https"):
        raise RuntimeError("LLM 주소는 http:// 또는 https:// 로 시작해야 해")
    url = endpoint.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "system", "content": USER_PII_NOTE + "\n" + summary}]
        + history[-10:] + [{"role": "user", "content": message}],
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            data = json.loads(res.read().decode("utf-8"))
    except Exception as e:  # 네트워크 차단·오타 등 → 친절한 폴백
        raise RuntimeError(f"LLM 연결 실패: {e}")
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise RuntimeError(f"LLM 응답 형식 오류: {str(data)[:200]}")


def cli_available() -> bool:
    from . import ai
    return ai.available()


def cli_chat(summary: str, history: list[dict], message: str) -> str:
    """구독 AI 모델로 답한다 (ai.run: 도구 끔·기록 안 남김·동시 호출 제한).

    임시 시스템 프롬프트 파일에는 개인정보를 뺀 요약만 들어간다.
    """
    from . import ai
    lines = [("사용자" if h["role"] == "user" else "상담사") + ": " + h["content"]
             for h in history]
    prompt = (("지금까지 나눈 대화:\n" + "\n".join(lines) + "\n\n") if lines else "") \
        + f"사용자의 새 질문: {message}\n\n위 리포트를 아는 상담사로서 답해 줘."
    system = SYSTEM_PROMPT + "\n\n" + USER_PII_NOTE + "\n" + summary
    return ai.run(system, prompt, AI_TIMEOUT)


# ---------------- 채팅 요약 (궁합·택일) ----------------

DOM_NAME = {"total": "총운", "love": "연애", "career": "직장", "money": "금전"}


def pick_summary(r: dict) -> str:
    """택일 결과를 채팅 상담용 한 줄 요약으로. 개인정보 없음."""
    top = [f"{x['label']} {x['ganzhi']} 연애{x['love']} 직장{x['career']} 금전{x['money']}"
           for x in r["rows"][:5]]
    return (f"택일 {r['start']}~{r['end']}({DOM_NAME[r['domain']]} 기준) / "
            f"상위 {'; '.join(top)} / "
            f"이야기 {'; '.join(r['story'])}")


def match_summary(r: dict) -> str:
    """궁합 결과를 채팅 상담용 한 줄 요약으로. 개인정보 없음."""
    return (f"궁합 {r['score']}점({r['head']}) / "
            f"잘맞는점 {'; '.join(r['strengths'])} / "
            f"조심할점 {'; '.join(r['cautions'])} / "
            f"참고 {'; '.join(r['info'])} / "
            f"이야기 {'; '.join(r['story'])} / "
            f"나 일간 {r['a_ilgan']} 일지 {r['a_day_branch']} 띠 {r['a_animal']} "
            f"명궁 {r['a_mingong']} 태양 {r['a_sun']} / "
            f"상대 일간 {r['b_ilgan']} 일지 {r['b_day_branch']} 띠 {r['b_animal']} "
            f"명궁 {r['b_mingong']} 태양 {r['b_sun']}")


def api_match_data(r: dict) -> dict:
    """궁합 결과 JSON. PII 없음."""
    return {"score": r["score"], "head": r["head"],
            "story": list(r["story"]),
            "strengths": list(r["strengths"]),
            "cautions": list(r["cautions"]), "info": list(r["info"]),
            "a": {"ilgan": r["a_ilgan"], "branch": r["a_day_branch"],
                  "animal": r["a_animal"], "mingong": r["a_mingong"],
                  "sun": r["a_sun"]},
            "b": {"ilgan": r["b_ilgan"], "branch": r["b_day_branch"],
                  "animal": r["b_animal"], "mingong": r["b_mingong"],
                  "sun": r["b_sun"]}}


def together_days(a: tuple, b: tuple, start: date, days: int = 30) -> dict:
    """두 사람의 날마다 연애 점수를 맞대어 '둘 다 좋은 날'과 '둘 다 예민한 날'을 고른다.

    둘 중 낮은 점수를 먼저 본다 (한 사람만 좋은 날보다 둘 다 무난한 날이 만나기 편하다). 같으면 평균.
    """
    from .taekil import pick_dates
    end = start + timedelta(days=days - 1)
    ra = {x["date"]: x for x in pick_dates(*a, start, end, "love")["rows"]}
    rb = {x["date"]: x for x in pick_dates(*b, start, end, "love")["rows"]}
    rows = [{"date": d, "label": ra[d]["label"], "ganzhi": ra[d]["ganzhi"],
             "me": ra[d]["love"], "you": rb[d]["love"],
             "both": min(ra[d]["love"], rb[d]["love"]), "avg": round((ra[d]["love"] + rb[d]["love"]) / 2)}
            for d in sorted(ra) if d in rb]
    good = sorted(rows, key=lambda r: (-r["both"], -r["avg"], r["date"]))[:5]
    tense = sorted(rows, key=lambda r: (r["both"], r["avg"], r["date"]))[:2]
    return {"start": start.isoformat(), "days": days, "good": good, "tense": tense}


def api_pick_data(r: dict) -> dict:
    """택일 결과 JSON. PII 없음."""
    dom_name = DOM_NAME[r["domain"]]
    return {"start": r["start"], "end": r["end"], "domain": r["domain"],
            "dom_name": dom_name, "story": list(r["story"]),
            "rows": [{"rank": x["rank"], "label": x["label"],
                      "ganzhi": x["ganzhi"], "love": x["love"],
                      "career": x["career"], "money": x["money"],
                      "god": x["god"]} for x in r["rows"]]}


# ---------------- HTTP 서버 ----------------

from pathlib import Path  # noqa: E402

STATIC_DIR = Path(__file__).resolve().parent / "static"
SHARE_ID = re.compile(r"[A-Za-z0-9_-]{8,16}")
SHARE_PATH = re.compile(r"/r/[A-Za-z0-9_-]{8,16}")
STATIC_FILES = {"app.html": "text/html; charset=utf-8", "app.css": "text/css; charset=utf-8",
                "viz.js": "text/javascript; charset=utf-8",
                "app.js": "text/javascript; charset=utf-8"}


CHAPTER_WAIT = 300         # AI 챕터 풀이를 기다리는 최대 시간(초). 넘으면 계산 풀이를 준다


def _prefetch_on() -> bool:
    """입력하자마자 모든 탭의 AI 풀이를 미리 만들지. LOVE_FORTUNE_PREFETCH=0 이면 연 탭만 만든다."""
    return os.environ.get("LOVE_FORTUNE_PREFETCH", "1") != "0"


def _ai_on() -> bool:
    """챕터 풀이에 AI 를 쓸지. LOVE_FORTUNE_AI=0 이면 계산 문장만 쓴다 (시험·오프라인)."""
    from . import ai
    return os.environ.get("LOVE_FORTUNE_AI", "1") != "0" and ai.available()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # 개인정보가 로그에 남지 않도록
        pass

    def _send(self, body: bytes, ctype: str, disp: str = "", code: int = 200, cache: str = ""):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        if cache:
            self.send_header("Cache-Control", cache)
        if disp:
            self.send_header("Content-Disposition", disp)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _fail(self, code: int, msg: str):
        """오류를 응답 본문으로 알린다.

        예전엔 send_error(400, "입력 형식 오류") 처럼 한글을 상태줄에 넣었는데,
        상태줄은 latin-1 이라 인코딩 오류로 응답 자체가 끊겼다.
        """
        if self.path.startswith("/api/"):
            body = json.dumps({"error": msg}, ensure_ascii=False).encode("utf-8")
            self._send(body, "application/json; charset=utf-8", code=code)
            return
        page = ("<!doctype html><html lang=\"ko\"><meta charset=\"utf-8\">"
                "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
                "<title>입력 확인</title><div style=\"font-family:sans-serif;padding:2em;"
                "max-width:640px;margin:auto\"><h2>다시 확인해 줘</h2>"
                f"<p>{html.escape(msg)}</p><p><a href=\"/\">처음으로</a></p></div></html>")
        self._send(page.encode("utf-8"), "text/html; charset=utf-8", code=code)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/" or SHARE_PATH.fullmatch(path):
            self._static("app.html")          # 저장 링크(/r/<id>)도 같은 화면이 열어서 불러온다
        elif path.startswith("/static/"):
            self._static(path[len("/static/"):])
        elif self.path == "/healthz":
            self._send(b'{"ok":true}', "application/json")
        elif self.path.split("?")[0] == "/api/lunar-year":
            self._lunar_year()
        elif path == "/api/name/hanja":
            self._name_hanja()
        elif self.path == "/api/glossary":
            from .glossary import TERMS
            body = json.dumps(TERMS, ensure_ascii=False).encode("utf-8")
            self._send(body, "application/json; charset=utf-8")
        else:
            self.send_error(404)

    def _static(self, name: str):
        """화면 파일 (love_fortune/static). 이름은 목록에 있는 것만."""
        if name not in STATIC_FILES:
            self.send_error(404)
            return
        body = (STATIC_DIR / name).read_bytes()
        self._send(body, STATIC_FILES[name], cache="no-cache")

    def _lunar_year(self):
        """그해 음력 달 목록 (캘린더 선택기용). ?y=1995"""
        from urllib.parse import parse_qs, urlparse
        from .lunar import MIN_YEAR, MAX_YEAR, _months
        try:
            y = int(parse_qs(urlparse(self.path).query).get("y", [""])[0])
            if not MIN_YEAR <= y <= MAX_YEAR:
                raise ValueError
        except ValueError:
            self._fail(400, f"연도는 {MIN_YEAR}~{MAX_YEAR} 사이여야 해")
            return
        months = [{"m": m, "leap": leap, "days": days} for m, leap, days in _months(y)]
        self._json({"year": y, "months": months})

    def _fields(self) -> dict:
        n = int(self.headers.get("Content-Length", 0) or 0)
        if n > MAX_BODY:
            raise ValueError("요청이 너무 커")
        ctype = self.headers.get("Content-Type", "")
        raw = self.rfile.read(n)
        if "application/json" in ctype:
            data = json.loads(raw.decode("utf-8") or "{}")
            if not isinstance(data, dict):
                raise ValueError("요청 형식 오류")
            return data
        from urllib.parse import parse_qs
        return {k: v[0] for k, v in
                parse_qs(raw.decode("utf-8")).items()}

    @staticmethod
    def _person(q: dict, n: str = "") -> tuple[date, int | None, int, str, str]:
        """폼 값 → (양력 생일, 시, 분, 성별, 도시). n 은 두 번째 사람이면 "2".

        양력·음력(윤달 포함) 입력과 성별을 여기서 검증한다. 잘못되면 ValueError.
        """
        from .cli import _parse_hm
        from .lunar import parse_birth_date
        from .manseryuk import normalize_sex
        birth = parse_birth_date(q.get(f"birth{n}", ""), q.get(f"calendar{n}") or "solar",
                                 _truthy(q.get(f"leap{n}")))
        bt_key = f"birth{n}_time" if n else "birth_time"
        bt = "모름" if _truthy(q.get(f"unknown_time{n}")) else (q.get(bt_key) or "12:00")
        try:
            hh, mm = _parse_hm(str(bt))
        except ValueError:
            raise ValueError("태어난 시간은 HH:MM 형식이어야 해 (예: 12:00)") from None
        sex = normalize_sex(q.get(f"sex{n}") or ("female" if n else "male"))
        city = str(q.get(f"city{n}") or "서울").strip()[:40] or "서울"
        return birth, hh, mm, sex, city

    @staticmethod
    def _period(q: dict) -> tuple[date, date, str]:
        try:
            start = datetime.strptime(str(q.get("from_date", "")), "%Y-%m-%d").date()
            end = datetime.strptime(str(q.get("to_date", "")), "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("기간은 YYYY-MM-DD 형식으로 입력해 줘") from None
        domain = q.get("domain", "total") or "total"
        if domain not in ("total", "love", "career", "money"):
            domain = "total"
        return start, end, domain

    def _drain(self):
        """본문을 읽지 않고 오류로 답하면 클라이언트가 아직 보내는 중인 연결이 끊겨(윈도에서 잦음)
        상태 코드 대신 연결 오류가 난다. 상한 안의 본문은 읽어 버린다."""
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if 0 < n <= MAX_BODY:
                self.rfile.read(n)
        except (ValueError, OSError):
            pass

    def _client_ip(self) -> str:
        if _truthy(os.environ.get("LOVE_FORTUNE_TRUST_PROXY", "")):
            xff = (self.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
            if xff:
                return xff
        return self.client_address[0]

    def do_POST(self):
        routes = {
            "/api/match": self._api_match, "/api/pick": self._api_pick,
            "/api/chat": self._chat,
            "/api/v2/report": self._v2_report, "/api/v2/chapter": self._v2_chapter,
            "/api/v2/share": self._v2_share, "/api/v2/shared": self._v2_shared,
            "/api/name": self._name, "/api/v2/rectify": self._rectify,
        }
        route = routes.get(self.path)
        if route is None:
            self._drain()
            self.send_error(404)
            return
        if not _rate_ok(self._client_ip(), self.path):
            self._drain()
            self._fail(429, "요청이 너무 많아. 1분쯤 뒤에 다시 해 줘.")
            return
        try:
            q = self._fields()
        except (ValueError, UnicodeDecodeError):
            self._fail(400, "요청 형식 오류")
            return
        from .manseryuk import zi_mode
        try:
            with zi_mode(str(q.get("zi") or "next")):
                route(q)
        except ValueError as e:
            self._fail(400, str(e))
        except Exception as e:  # noqa: BLE001  계산 오류가 나도 서버는 살아 있게
            # 입력값(개인정보)은 남기지 않고 오류 종류만 남긴다
            print(f"[오류] {self.path} {type(e).__name__}", file=sys.stderr)
            self._fail(500, "계산 중 오류가 났어. 입력값을 확인하고 다시 시도해 줘.")

    # ---------------- 경로별 처리

    def _api_match(self, q: dict):
        from .matchmaking import compatibility
        from .cli import build_match_report
        a = self._person(q)
        b = self._person(q, "2")
        r = compatibility(*a, *b)
        _text, md = build_match_report(*a, *b, r)
        summary = match_summary(r)
        token = _remember(md, summary, date.today().isoformat())
        data = api_match_data(r)
        data["dates"] = together_days(a, b, date.today(), 30)
        from .astro import natal_chart
        from .manseryuk import four_pillars
        from . import sok
        data["sok"] = sok.pair(natal_chart(a[0], a[1], a[2], a[4]), natal_chart(b[0], b[1], b[2], b[4]),
                               four_pillars(a[0], a[1], a[2], a[4])["day_branch"],
                               four_pillars(b[0], b[1], b[2], b[4])["day_branch"])   # 화면은 성인 확인 때만 보여 줌
        self._json({"token": token, "data": data})

    def _api_pick(self, q: dict):
        from .taekil import pick_dates
        from .cli import build_pick_report
        birth, hh, mm, sex, city = self._person(q)
        start, end, domain = self._period(q)
        r = pick_dates(birth, hh, mm, sex, city, start, end, domain)
        _text, md = build_pick_report(birth, hh, mm, sex, city, start, end, domain, 5, r)
        summary = pick_summary(r)
        token = _remember(md, summary, start.isoformat())
        self._json({"token": token, "data": api_pick_data(r)})

    # ---------------- 새 화면 (탭·챕터)

    def _v2_report(self, q: dict):
        """사실표와 모든 챕터의 계산 풀이를 돌려준다 (화면이 바로 보여 준다).

        AI 를 쓸 수 있으면 모든 탭의 AI 풀이를 대기열에 넣어 미리 만들기 시작한다.
        화면은 /api/v2/chapter 로 AI 풀이를 받아 계산 풀이를 바꿔 끼운다.
        """
        from . import chapters, facts as facts_mod, prefetch
        birth, hh, mm, sex, city = self._person(q)
        target = date.today()
        f = facts_mod.build(birth, hh, mm, sex, city, target)
        _md, _text, summary = agent_context(birth, hh, mm, sex, city, target)
        token = _remember("", summary, target.isoformat(), facts=f)
        ai_on = _ai_on()
        if ai_on and _prefetch_on():
            prefetch.submit_all(f)
        self._json({"token": token, "facts": f, "outline": chapters.outline(),
                    "rules": chapters.rule_all(f), "ai": ai_on})

    def _rectify(self, q: dict):
        """태어난 시간 추정: 인생 사건으로 12시진 후보에 점수를 매긴다 (재미·참고용)."""
        from . import rectify
        birth, _hh, _mm, sex, city = self._person(q)
        events = q.get("events") or []
        if not isinstance(events, list):
            raise ValueError("사건 형식 오류")
        self._json(rectify.rectify(birth, sex, city, events))

    def _name_hanja(self):
        """이름 한 글자의 인명용 한자 목록 (훈음·원획). ?r=민&s=1 (s=1 이면 성)."""
        from urllib.parse import parse_qs, urlparse
        from . import naming
        qs = parse_qs(urlparse(self.path).query)
        r = (qs.get("r", [""])[0] or "")[:1]
        if not r or naming.split_syllable(r) is None:
            self._fail(400, "한글 한 글자를 넣어 줘")
            return
        self._json({"r": r, "items": naming.hanja_for(r, qs.get("s", ["0"])[0] == "1")})

    def _name(self, q: dict):
        """이름 풀이. 사주 결과 토큰이 있으면 원국 오행과 함께 본다."""
        from . import naming
        hanja = q.get("hanja") or []
        if not isinstance(hanja, list) or len(hanja) > 5:
            raise ValueError("한자 선택 형식 오류")
        hanja = [int(x) if str(x).isdigit() else None for x in hanja]
        ctx = _context(str(q.get("token", ""))) or {}
        natal = (ctx.get("facts") or {}).get("natal", {}).get("elements")
        self._json(naming.analyze(str(q.get("surname", "")).strip(), str(q.get("given", "")).strip(),
                                  hanja, natal))

    def _v2_share(self, q: dict):
        """지금 결과를 저장하고 링크 이름을 준다 (사실표·상담 요약만, 개인정보 없음)."""
        from . import content_store
        ctx = self._v2_ctx(q)
        share_id = secrets.token_urlsafe(8)
        content_store.put_share(share_id, ctx["facts"], ctx["summary"])
        self._json({"id": share_id, "path": f"/r/{share_id}"})

    def _v2_shared(self, q: dict):
        """저장한 결과를 다시 연다. 챕터·상담이 이어지게 새 토큰을 붙인다."""
        from . import chapters, content_store
        share_id = str(q.get("id", ""))
        got = content_store.get_share(share_id) if SHARE_ID.fullmatch(share_id) else None
        if not got:
            raise ValueError("없는 링크야")
        f = got["facts"]
        token = _remember("", got["summary"], f["meta"]["target"], facts=f)
        self._json({"token": token, "facts": f, "outline": chapters.outline(),
                    "rules": chapters.rule_all(f), "ai": _ai_on(), "shared": True})

    def _v2_ctx(self, q: dict) -> dict:
        ctx = _context(str(q.get("token", "")))
        if not ctx or not ctx.get("facts"):
            raise ValueError("만료된 결과야. 처음 화면에서 다시 펼쳐 줘.")
        return ctx

    def _v2_chapter(self, q: dict):
        from . import chapters
        ctx = self._v2_ctx(q)
        tab, ch = str(q.get("tab", "")), str(q.get("chapter", ""))
        if tab not in chapters.TABS:
            raise ValueError("없는 탭")
        chapters.spec(tab, ch)
        body = None
        if _ai_on():
            from . import prefetch
            body = prefetch.wait(tab, ch, ctx["facts"], CHAPTER_WAIT)
        self._json(body or chapters.rule_chapter(tab, ch, ctx["facts"]))

    def _chat(self, q: dict):
        ctx = _context(str(q.get("token", ""))) or {}
        summary = ctx.get("summary", "리포트 컨텍스트 없음. 일반적인 운세 상담으로 답할 것.")
        message = str(q.get("message", "")).strip()[:1000]
        if not message:
            raise ValueError("질문을 입력해 줘")
        history = _clean_history(q.get("history"))
        endpoint = str(q.get("endpoint", "") or "").strip()
        api_key = str(q.get("api_key", "") or "")
        model = str(q.get("model", "") or "gpt-4o-mini")
        backend = str(q.get("backend", "") or "").strip().lower()
        # 요청이 준 주소로 서버가 대신 요청을 보내는 기능이라, 공개 서버에서는 아무 주소나
        # 찌르는 통로(SSRF)가 된다. 화면은 쓰지 않으니 LOVE_FORTUNE_CUSTOM_LLM=1 일 때만 연다.
        custom_ok = os.environ.get("LOVE_FORTUNE_CUSTOM_LLM", "0") == "1"
        if backend == "openai" and not custom_ok:
            backend = ""
        if backend not in ("cli", "openai", "local"):
            # 기본: (허용된 경우) 직접 연결한 엔드포인트, 없으면 구독 AI 모델(CLI),
            # CLI 명령이 없으면 로컬 규칙 에이전트
            backend = ("openai" if custom_ok and endpoint and api_key
                       else "cli" if cli_available() else "local")
        try:
            if backend == "openai":
                reply, mode, used = llm_chat(endpoint, api_key, model, summary,
                                             history, message), "llm", model
            elif backend == "cli":
                reply, mode, used = cli_chat(summary, history, message), "cli", AI_LABEL
            else:
                reply, mode, used = local_agent_reply(message, summary), "local", "로컬 규칙 에이전트"
        except RuntimeError as e:
            reply = (f"{e}\n\n대신 계산 결과로 바로 답할게: "
                     + local_agent_reply(message, summary))
            mode, used = "local-fallback", "로컬 규칙 에이전트"
        self._json({"reply": reply, "mode": mode, "model": used})

    def _json(self, obj: dict):
        self._send(json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")


def serve(port: int = 8765, host: str = "127.0.0.1"):
    """로컬 웹 서버. 기본은 이 컴퓨터에서만 열린다.

    예전엔 0.0.0.0 으로 열려서 같은 와이파이의 누구나 접속할 수 있었다. 채팅이
    구독 AI 모델로 답하게 되면서 남이 내 사용량을 쓰는 통로도 되므로 막는다.
    휴대폰 등 다른 기기에서 보려면 --host 0.0.0.0 으로 직접 연다.
    """
    print(DISCLAIMER)
    print(f"홈페이지: http://localhost:{port} (종료: Ctrl+C)")
    if host not in ("127.0.0.1", "localhost"):
        print(f"주의: {host} 로 열려 있어 같은 네트워크의 다른 기기도 접속할 수 있습니다.")
    if not os.environ.get("PORT"):          # 배포 환경(PORT 지정)에서는 브라우저를 열지 않는다
        try:
            webbrowser.open(f"http://localhost:{port}")
        except Exception:
            pass
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    server.serve_forever()
