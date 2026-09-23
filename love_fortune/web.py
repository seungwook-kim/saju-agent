"""web.py, 홈페이지식 로컬 웹 UI + 채팅 상담 에이전트 (표준라이브러리만).

실행: python -m love_fortune form [--port 8765]  → http://localhost:8765

구성:
- 홈페이지: 입력폼 + 리포트 카드(점수 게이지·행운요소·사주·자미두수·점성술·점괘)
- 채팅 패널: 오늘 리포트를 아는 상담 에이전트와 대화
  * 기본 = 로컬 규칙 기반 에이전트 (오프라인 동작, API 키 불필요)
  * 선택 = OpenAI 호환 엔드포인트 연결 (채팅창 설정에서 endpoint/key/model 입력,
    브라우저 localStorage에만 저장, 서버에 저장 안 함)
- 개인정보(생년월일·시간·성별·도시): 서버 메모리에만 잠시 보관, 파일·로그에 기록 안 함.
  다운로드 md와 LLM 전송 컨텍스트에는 개인정보를 제외한다.
"""
from __future__ import annotations

import html
import json
import secrets
import time
import urllib.request
import webbrowser
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .cli import build_report, DISCLAIMER

# token -> {"target": str, "summary": str(개인정보 제외), "created": float}
_CONTEXTS: dict[str, dict] = {}


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
        ts, tb, target.isoformat())
    adv = build_advice(natal["ilgan"], today_elem, target, birth)
    ma = detailed_reading(birth, hour, minute, sex, city, target)
    ast = ma["astro"]
    zd = ma["ziwei_detail"]
    vd = ma["venus_detail"]
    summary = (
        f"대상일 {target.isoformat()} / 일간 {natal['ilgan']}({natal['ilgan_element']}) / "
        f"오늘 일진 {ganzhi_str(ts, tb)} / 점수 {score}점, {headline(score)} / "
        f"근거: {'; '.join(reasons)} / 행운의 색 {adv['color']}, 번호 {adv['number']}, "
        f"방향 {adv['direction']}, 시간대 {adv['time']}, 장소 {', '.join(adv['places'])}, "
        f"대화팁 {'; '.join(adv['talk'])}, 피할 것 {adv['avoid']} / "
        f"{ma['guo_line']} / {ast['compat_line']} / "
        f"생명수 {adv['life_path']}({adv['life_path_vibe']}) / "
        f"타로 {adv['tarot']}({adv['tarot_line']}) / 주역 {adv['gua']}({adv['gua_line']}) / "
        f"오미쿠지 {adv['omikuji']}({adv['omikuji_line']}) / "
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
        return ("두 사람 궁합은요, " + (" / ".join(seg) if seg
                else "궁합은 첫 화면의 궁합 폼에서 두 사람 생년월일을 입력하면 봐요."))

    import re as _re_wk
    import datetime as _dt_wk
    if has("이번주", "다음주", "이번달") and not decide:
        if "달" in m and "주" not in m:
            _seg_m = next((_strip_story(s) for s in summary.split(" / ")
                           if s.startswith("이번달 ")), "")
            if _seg_m:
                return "이번 달 전체 흐름은요, " + _seg_m
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
                return f"{_label} 좋은 날 top3는요, {_top3}."
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
                return f"{_want.month}월 {_want.day}일 운세는요, {_hit}."
            return "그 날짜는 30일 표 밖에 있어. 리포트의 평생 탭 연도별 표를 참고해줘."

    if has("택일", "길일", "좋은날", "날짜고르", "언제가좋", "날잡기") and not decide:
        seg = [s for s in summary.split(" / ")
               if s.startswith(("택일", "상위", "이야기"))]
        seg = [_strip_story(s) for s in seg]
        return ("고른 날짜 중에서는요, " + (" / ".join(seg) if seg
                else "첫 화면의 길일 고르기 폼에서 기간을 입력하면 봐요."))

    if has("안녕", "하이", "헬로", "처음"):
        return ("안녕하세요! 오늘 리포트를 바탕으로 운세 고민을 함께 이야기하는 상담 에이전트예요. "
                "(정통 공식 기반 상세 해석, 전통 해석 체계에 근거합니다.) "
                "점수·장소·대화팁·별자리·타로·대운·사화 등 편하게 물어보세요.")
    if has("배우자", "결혼", "상대", "신랑", "신부", "아내", "남편", "와이프") and not decide:
        seg = [s for s in summary.split(" / ")
               if s.startswith(("배우자궁", "상대 ", "관계 ", "관계팁", "직업군", "배우자성", "일주운성"))]
        return ("사주 기반 인연 아키타입(정통 계산)은요, " + " / ".join(seg)
                + ". 더 자세한 직업군·만남 자리는 '어떤 사람을 만나기 쉬울까'라고 물어보세요.")
    if has("이상형", "외모", "생김", "어떤사람", "만날", "만남", "직업", "인상", "스타일") \
            and not has("장소", "코스", "어디"):
        seg = [s for s in summary.split(" / ")
               if s.startswith(("부처궁", "금성", "달 ", "만남TOP3", "직업군"))]
        return ("만나기 쉬운 인연의 모습(정통 계산)은요, " + " / ".join(seg)
                + ". '배우자 궁합'처럼 더 물어보셔도 돼요.")
    if has("도화", "홍염", "매력", "인기"):
        seg = [s for s in summary.split(" / ") if s.startswith(("도화", "홍염살", "올해", "이야기연애"))]
        seg = [_strip_story(s) for s in seg]
        return "매력·인연의 기운은요, " + (" / ".join(seg) if seg else "리포트의 인연 카드를 참고해 주세요.")
    if has("직장", "회사", "업무", "상사", "동료", "취업", "이직", "승진", "면접",
            "출근", "야근", "프로젝트") and not decide:
        seg = [s for s in summary.split(" / ")
               if s.startswith(("직장운", "관록궁", "원국 관성", "현재 대운", "사주 대운",
                                "직장운 근거", "이야기직장"))]
        seg = [_strip_story(s) for s in seg]
        return ("오늘 직장운은요, " + (" / ".join(seg) if seg else "리포트의 직장 탭을 참고해 주세요."))
    if has("금전", "돈", "재물", "투자", "저축", "월급", "지출", "쇼핑", "주식", "코인") \
            and not decide:
        seg = [s for s in summary.split(" / ")
               if s.startswith(("금전운", "재백궁", "원국 재성",
                                "금전운 근거", "이야기금전"))]
        seg = [_strip_story(s) for s in seg]
        return ("오늘 금전운은요, " + (" / ".join(seg) if seg else "리포트의 금전 탭을 참고해 주세요."))
    if has("총운", "오늘운", "키워드", "종합", "전반"):
        seg = [s for s in summary.split(" / ")
               if s.startswith(("총운", "오늘 일진",
                                "총운 근거", "이야기총운"))]
        seg = [_strip_story(s) for s in seg]
        return ("오늘 총운은요, " + (" / ".join(seg) if seg else "리포트의 총운 탭을 참고해 주세요."))
    if has("평생", "인생", "앞으로", "노후", "말년", "초년", "중년", "여생",
            "대운", "유년", "소운", "용신", "격국", "신강", "신약",
            "기질", "타고난") and not decide:
        seg = [s for s in summary.split(" / ")
               if s.startswith(("평생흐름", "현재연대", "유년열", "초년",
                                 "중년", "말년", "타고난기질", "신강약",
                                 "이야기평생"))]
        seg = [_strip_story(s) for s in seg]
        return ("평생 흐름은요, " + (" / ".join(seg) if seg else "리포트의 평생 탭을 참고해 주세요."))
    if has("시기", "언제", "올해", "운성"):
        seg = [s for s in summary.split(" / ") if s.startswith(("올해", "일주운성"))]
        return "시기의 흐름은요, " + (" / ".join(seg) if seg else "리포트의 인연 카드를 참고해 주세요.")
    import re as _re_wk
    import datetime as _dt_wk
    if has("점수", "총평", "어때"):
        head = summary.split("점,", 1)[1].split(" / 근거")[0] if "점," in summary else summary
        score = summary.split("/ 점수 ")[1].split("점")[0] if "/ 점수 " in summary else "?"
        reason = next((_strip_story(s) for s in summary.split(" / ") if s.startswith("근거:")), "")
        story = next((_strip_story(s) for s in summary.split(" / ")
                      if s.startswith("이야기연애")), "")
        return (f"오늘 연애운은 {score}점이에요. {head} 흐름으로 보시면 좋을 것 같아요. "
                + (reason + " " if reason else "")
                + (story + " " if story else "")
                + "자세한 근거는 위 리포트 카드의 '해석 근거'를 참고해 주세요.")
    if has("색", "번호", "숫자", "방향", "시간"):
        seg = summary.split("/ 행운의 색 ")[1].split(" / ")[0] if "/ 행운의 색 " in summary else summary
        return f"오늘 행운 요소는 이렇게 나와 있어요: {seg}. 외출할 때 하나쯤 챙겨보시면 기분 전환에 좋은 흐름이에요."
    if has("장소", "코스", "데이트", "어디"):
        seg = summary.split("장소 ", 1)[1].split(" / ")[0] if "장소 " in summary else ""
        return (f"오늘 추천 장소는 {seg}예요. 무리한 이벤트보다 가볍게 걷고 이야기 나누기 좋은 흐름이에요. "
                "시간대는 리포트의 '좋은 시간대'를 참고해 보세요.")
    if has("대화", "말", "카톡", "연락", "팁", "화제"):
        seg = summary.split("대화팁 ", 1)[1].split(", 피할 것")[0] if "대화팁 " in summary else ""
        avoid = summary.split("피할 것 ", 1)[1].split(" / ")[0] if "피할 것 " in summary else ""
        return (f"대화 팁으로는 '{seg}' 같은 흐름이 좋아 보여요. "
                f"반대로 '{avoid}'은 오늘은 피하는 게 좋은 흐름이에요.")
    if has("신살", "천을", "역마", "화개", "공망", "장성", "괴강", "고진", "사주") \
            and not decide:
        seg = [s for s in summary.split(" / ")
               if s.startswith(("사주 대운", "신살", "천을", "역마", "화개",
                                 "공망", "장성", "괴강", "고진"))]
        return ("사주 대운·신살은요, " + (" / ".join(seg) if seg else "리포트를 참고해 주세요."))
    if has("역행"):
        seg = [s for s in summary.split(" / ") if "역행" in s]
        return ("역행 관련해서는요, " + (" / ".join(seg) if seg else "현재 역행 중인 행성은 없어요."))
    if has("자미", "명궁", "부처", "도화", "사화", "명반"):
        seg = [s for s in summary.split(" / ")
               if any(k in s for k in ("부처궁", "생년사화", "대운", "유년", "오행국", "명궁", "도화"))]
        return ("자미두수 정통 명반에서는 이렇게 나와 있어요: " + " / ".join(seg)
                + ". 궁별 전체 배치는 리포트의 자미두수 카드를 참고해 주세요.")
    if has("별자리", "금성", "달", "점성", "궁합", "하우스", "어스펙트", "상승궁"):
        seg = [s for s in summary.split(" / ")
               if any(k in s for k in ("금성", "궁합", "생명수", "상승궁", "하우스", "어스펙트", "달 "))]
        return " / ".join(seg) if seg else "리포트의 점성술 카드를 참고해 주세요."
    if has("타로", "주역", "오미쿠지", "점괘", "운세"):
        seg = [s for s in summary.split(" / ") if "타로" in s or "주역" in s or "오미쿠지" in s]
        return "오늘의 점괘는요, " + " / ".join(seg)
    if has("내일"):
        return ("내일 리포트는 상단 폼에서 '내일 운세 보기'를 체크하고 다시 조회해 보세요. "
                "그럼 내일 날짜 기준으로 새 리포트와 함께 이어서 대화할 수 있어요.")
    if has("고마", "감사", "좋아", "도움"):
        return ("도움이 됐다니 다행이에요! 좋은 흐름은 살리고, 애매한 날은 무리하지 않는 게 포인트예요. "
                "(정통 공식 기반 상세 해석, 전통 해석 체계에 근거합니다.)")
    if has("결혼", "헤어", "이별", "죽", "자살", "우울"):
        return ("그런 고민을 하고 계시는군요. 저는 운세 해석 에이전트라서 인생의 중요한 결정에는 답해드릴 수 없어요. "
                "힘들면 주변 사람이나 전문 상담(예: 생명의전화 109, 청소년 1388)과 꼭 이야기해 보세요.")
    return ("음, 그 질문에는 오늘 리포트만으로 답하기 어렵네요. "
            "총운·연애·직장·금전·평생 중에서 궁금한 걸 골라 물어봐 주세요. "
            "모르는 용어는 '정관이 뭐야'처럼 물어보면 풀어드립니다.")


# ---------------- 선택적 LLM 연결 (OpenAI 호환) ----------------

SYSTEM_PROMPT = ("너는 '종합 사주' 리포트를 바탕으로 상담하는 다정한 상담 에이전트다. "
                 "규칙: 1) 정통 공식 기반 상세 해석임을 전제로 답한다. 2) 단정적 예언 금지 "
                 "('~할 것이다' 대신 '~하기 좋은 흐름'으로 말한다). "
                 "3) 결혼·이별·정신건강 등 중요한 주제에는 결정을 대신 내려주지 말고 "
                 "신중한 대화와 전문가 상담을 권한다. 4) 한국어로 답한다.")

USER_PII_NOTE = "아래 컨텍스트에는 개인정보가 포함되어 있지 않다."


def llm_chat(endpoint: str, api_key: str, model: str,
             summary: str, history: list[dict]) -> str:
    """OpenAI 호환 /chat/completions 호출 (표준라이브러리만)."""
    url = endpoint.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "system", "content": USER_PII_NOTE + "\n" + summary}]
        + history[-10:],
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


# ---------------- HTML ----------------

CSS = """
*{box-sizing:border-box}body{font-family:'Malgun Gothic',sans-serif;margin:0;
background:linear-gradient(160deg,#fff0f3,#f3ecff);color:#333}
header{background:linear-gradient(120deg,#e5486f,#7c5cff);color:#fff;padding:2.2em 1em;text-align:center}
header h1{margin:0;font-size:1.8em}header p{opacity:.9}
main{max-width:960px;margin:-1.2em auto 3em;padding:0 1em}
.card{background:#fff;border-radius:14px;padding:1.2em 1.4em;margin:1em 0;
box-shadow:0 4px 16px rgba(0,0,0,.08)}
.form-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.7em}
label{font-size:.9em;display:block}input,select{width:100%;padding:.55em;font-size:1em;
border:1px solid #ccc;border-radius:8px}
button{background:#e5486f;color:#fff;border:0;border-radius:8px;padding:.7em 1.4em;
font-size:1em;cursor:pointer}button:hover{background:#c93a5d}
.score{display:flex;align-items:center;gap:1em}
.ring{width:96px;height:96px;border-radius:50%;display:flex;align-items:center;
justify-content:center;font-size:1.5em;font-weight:bold;color:#fff;flex:none}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1em}
.tag{display:inline-block;background:#f3ecff;border-radius:20px;padding:.2em .8em;margin:.15em;font-size:.9em}
#chat{display:flex;flex-direction:column;gap:.5em}
#msgs{max-height:300px;overflow-y:auto;border:1px solid #eee;border-radius:8px;padding:.7em;background:#fafafa}
.msg{margin:.4em 0;padding:.5em .8em;border-radius:10px;max-width:85%}
.me{background:#e5486f;color:#fff;margin-left:auto}
.bot{background:#eee}
.row{display:flex;gap:.5em}#q{flex:1;padding:.55em;border:1px solid #ccc;border-radius:8px}
details{font-size:.85em;color:#666}footer{text-align:center;color:#888;font-size:.85em;padding:2em}
.tabs{display:flex;gap:.5em;margin:1em 0;flex-wrap:wrap}
.tab{background:#fff;color:#333;border:1px solid #ddd}
.tab.on{background:#e5486f;color:#fff;border-color:#e5486f}
table.life{border-collapse:collapse;width:100%;font-size:.82em}
table.life td,table.life th{border:1px solid #ddd;padding:.3em .5em;text-align:center}
.story{background:#fffaf2}.story p{line-height:1.75}
@media print{header{background:#fff;color:#000}.card{box-shadow:none;break-inside:avoid}#chat,.row,button,details{display:none}}
@media (max-width:640px){.card{padding:.8em}table.life{font-size:.72em}}
"""

HOME_PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>종합 사주 (로컬·정통 계산)</title><style>{css}</style></head><body>
<header><h1>💫 종합 사주</h1>
<p>[정통 계산] 사주·자미두수·점성술 전통 공식 그대로 · 입력값은 파일에 저장되지 않음</p></header>
<main><div class="card"><h2>🔮 오늘의 운세 보기</h2>
<form method="post" action="/report"><div class="form-grid">
<label>양력 생년월일<input name="birth" type="date" value="1995-02-28" required></label>
<label>태어난 시간<input name="birth_time" type="time" value="12:00">
<span style="font-size:.85em"><input name="unknown_time" type="checkbox" value="1" style="width:auto"> 모름</span></label>
<label>성별<select name="sex"><option value="male">남자</option><option value="female">여자</option></select></label>
<label>태어난 도시<input name="city" value="부산"></label>
</div><p><label><input name="tomorrow" type="checkbox" value="1" style="width:auto"> 내일 운세 보기</label></p>
<button type="submit">운세 보기</button></form></div>
<div class="card"><h2>💞 두 사람 궁합 보기</h2>
<form method="post" action="/match"><div class="form-grid">
<label>내 생년월일<input name="birth" type="date" value="1995-02-28" required></label>
<label>내가 태어난 시간<input name="birth_time" type="time" value="12:00">
<span style="font-size:.85em"><input name="unknown_time" type="checkbox" value="1" style="width:auto"> 모름</span></label>
<label>내 성별<select name="sex"><option value="male">남자</option><option value="female">여자</option></select></label>
<label>내가 태어난 도시<input name="city" value="부산"></label>
<label>상대 생년월일<input name="birth2" type="date" value="1997-06-15" required></label>
<label>상대가 태어난 시간<input name="birth2_time" type="time" value="12:00">
<span style="font-size:.85em"><input name="unknown_time2" type="checkbox" value="1" style="width:auto"> 모름</span></label>
<label>상대 성별<select name="sex2"><option value="female">여자</option><option value="male">남자</option></select></label>
<label>상대가 태어난 도시<input name="city2" value="서울"></label>
</div>
<button type="submit">궁합 보기</button></form></div>
<div class="card"><h2>📅 길일 고르기</h2>
<form method="post" action="/pick"><div class="form-grid">
<label>양력 생년월일<input name="birth" type="date" value="1995-02-28" required></label>
<label>태어난 시간<input name="birth_time" type="time" value="12:00">
<span style="font-size:.85em"><input name="unknown_time" type="checkbox" value="1" style="width:auto"> 모름</span></label>
<label>성별<select name="sex"><option value="male">남자</option><option value="female">여자</option></select></label>
<label>태어난 도시<input name="city" value="부산"></label>
<label>시작일<input name="from_date" type="date" value="2026-10-01" required></label>
<label>끝일<input name="to_date" type="date" value="2026-10-31" required></label>
<label>목적<select name="domain"><option value="total">총운</option><option value="love">연애</option><option value="career">직장</option><option value="money">금전</option></select></label>
</div>
<button type="submit">길일 보기</button></form></div>
<div class="card"><h2>💬 상담 에이전트</h2>
<p>리포트를 먼저 조회하면, 그 내용을 아는 상담 에이전트와 채팅할 수 있어요.
기본은 오프라인 로컬 에이전트이며, 원하면 OpenAI 호환 LLM에 연결할 수 있어요.</p></div></main>
<footer>정통 공식 기반 상세 해석 · 네트워크 전송 없음.</footer></body></html>"""

REPORT_PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>종합 사주 결과</title><style>{css}</style></head><body>
<header><h1>💫 {target}의 종합 사주</h1>
<p>총운 {tscore}점 · 연애 {lscore} · 직장 {cscore} · 금전 {mscore}</p></header>
<main>
<div class="tabs">
<button class="tab on" id="b-total" onclick="tab('total')">오늘의 운세</button>
<button class="tab" id="b-love" onclick="tab('love')">오늘의 연애</button>
<button class="tab" id="b-career" onclick="tab('career')">오늘의 직장운세</button>
<button class="tab" id="b-money" onclick="tab('money')">오늘의 금전운</button>
<button class="tab" id="b-life" onclick="tab('life')">평생 운세</button>
</div>
<div id="tab-total">
<div class="card story"><h2>📖 오늘 이야기</h2>{story_total}</div>
<div class="card score"><div class="ring" style="background:{tcolor}">{tscore}</div>
<div><h2 style="margin:0">오늘 총운 한 줄</h2><p>{thead}</p>
<p style="font-size:.85em;color:#666">{disclaimer}</p>
<form method="post" action="/download"><input type="hidden" name="token" value="{token}">
<button type="submit">md 다운로드 (개인정보 제외)</button></form></div></div>
<div class="card"><h2>📜 총운 근거</h2>{treasons}<h2>🔑 오늘의 키워드</h2><p>{tkeywords}</p></div>
<div class="grid2">
<div class="card"><h2>🍀 행운 요소</h2>{lucky}</div>
<div class="card"><h2>🧭 사주 4기둥·오늘 일진</h2><p>{saju}</p></div>
</div>
<div class="card"><h2>🎴 오늘의 점괘</h2><p>{divi}</p></div>
<div class="card"><h2>📅 일운 30일</h2>{ilun}</div>
<div class="card"><h2>📖 용어 풀이</h2>{gloss}</div>
</div>
<div id="tab-love" style="display:none">
<div class="card story"><h2>📖 연애 이야기</h2>{story_love}</div>
<div class="card score"><div class="ring" style="background:{lcolor}">{lscore}</div>
<div><h2 style="margin:0">오늘 연애운 한 줄</h2><p>{lhead}</p></div></div>
<div class="card"><h2>📜 연애 근거</h2>{lreasons}</div>
<div class="card"><h2>💬 데이트 대화 팁</h2>{talk}</div>
<div class="grid2">
<div class="card"><h2>🔯 자미두수 정통 명반</h2><p>{ziwei}</p></div>
<div class="card"><h2>✨ 서양 점성술 실측 차트</h2><p>{astro}</p></div>
</div>
<div class="card"><h2>💞 만날 인연 아키타입 (정통 계산)</h2>{match}</div>
<div class="card"><h2>🏯 자미두수 12궁 풀이</h2>{palace12}</div>
</div>
<div id="tab-career" style="display:none">
<div class="card story"><h2>📖 직장 이야기</h2>{story_career}</div>
<div class="card score"><div class="ring" style="background:{ccolor}">{cscore}</div>
<div><h2 style="margin:0">오늘 직장운 한 줄</h2><p>{chead}</p></div></div>
<div class="card"><h2>📜 직장 근거</h2>{creasons}</div>
<div class="card"><h2>🏢 일의 바탕</h2>{cstars}</div>
<div class="card"><h2>💼 일의 팁</h2>{ctips}</div>
</div>
<div id="tab-money" style="display:none">
<div class="card story"><h2>📖 금전 이야기</h2>{story_money}</div>
<div class="card score"><div class="ring" style="background:{mcolor}">{mscore}</div>
<div><h2 style="margin:0">오늘 금전운 한 줄</h2><p>{mhead}</p></div></div>
<div class="card"><h2>📜 금전 근거</h2>{mreasons}</div>
<div class="card"><h2>💰 돈의 바탕</h2>{mstars}</div>
<div class="card"><h2>💵 돈의 팁</h2>{mtips}</div>
</div>
<div id="tab-life" style="display:none">
<div class="card story"><h2>📖 평생 이야기</h2>{story_life}</div>
<div class="card"><h2>🌱 타고난 바탕</h2>{lifeyong}</div>
<div class="card"><h2>🕰️ 시기별 흐름</h2>{lifeph}<h2>📍 지금 연대</h2><p>{lifecur}</p></div>
<div class="card"><h2>📊 연대별 타임라인</h2>{lifedec}</div>
<div class="card"><h2>🛤️ 대운 풀이</h2>{lifedayun}</div>
<div class="card"><h2>📅 연도별 타임라인</h2>{lifetable}</div>
</div>
<div class="card"><h2>💬 상담 에이전트와 채팅</h2>
<div id="chat"><div id="msgs"></div>
<div class="row"><input id="q" placeholder="예: 오늘 직장운 어때, 금전운 알려줘"><button onclick="send()">전송</button></div>
<details><summary>⚙️ LLM 연결 (선택, 미설정 시 로컬 에이전트)</summary>
<p>OpenAI 호환 엔드포인트를 입력하면 실제 LLM과 대화합니다. 키는 브라우저에만 저장됩니다.</p>
<label>Endpoint <input id="ep" placeholder="http://localhost:11434/v1"></label>
<label>API Key <input id="key" type="password" placeholder="(비워두면 로컬 에이전트)"></label>
<label>Model <input id="model" placeholder="gpt-4o-mini"></label>
<button onclick="saveCfg()">설정 저장(브라우저에만)</button></details></div></div>
<p><a href="/">← 처음으로</a></p></main>
<footer>정통 공식 기반 상세 해석.</footer>
<script>
function tab(n){{for(const t of ['total','love','career','money','life']){{
document.getElementById('tab-'+t).style.display=(t===n?'':'none');
document.getElementById('b-'+t).className='tab'+(t===n?' on':'');}}}}
const token="{token}";
const box=document.getElementById('msgs'), q=document.getElementById('q');
function bubble(t,cls){{const d=document.createElement('div');d.className='msg '+cls;
d.textContent=t;box.appendChild(d);box.scrollTop=box.scrollHeight;}}
bubble('안녕하세요! 오늘 리포트를 아는 상담 에이전트예요. 편하게 물어보세요. (정통 계산)','bot');
q.addEventListener('keydown',e=>{{if(e.key==='Enter')send();}});
function cfg(){{return {{endpoint:localStorage.getItem('llm_ep')||'',
api_key:localStorage.getItem('llm_key')||'',model:localStorage.getItem('llm_model')||''}};}}
function saveCfg(){{localStorage.setItem('llm_ep',document.getElementById('ep').value);
localStorage.setItem('llm_key',document.getElementById('key').value);
localStorage.setItem('llm_model',document.getElementById('model').value);alert('저장됐습니다(브라우저에만).');}}
(async()=>{{document.getElementById('ep').value=localStorage.getItem('llm_ep')||'';
document.getElementById('model').value=localStorage.getItem('llm_model')||'';}})();
let hist=[];
async function send(){{const m=q.value.trim();if(!m)return;q.value='';
bubble(m,'me');hist.push({{role:'user',content:m}});
bubble('생각 중…','bot');
try{{const r=await fetch('/api/chat',{{method:'POST',
headers:{{'Content-Type':'application/json'}},
body:JSON.stringify(Object.assign({{token,message:m,history:hist.slice(0,-1)}},cfg()))}});
const j=await r.json();box.lastChild.remove();
if(j.error){{bubble('오류: '+j.error+' (로컬 답변으로 대체할게요)','bot');}}
bubble(j.reply,'bot');hist.push({{role:'assistant',content:j.reply}});}}
catch(e){{box.lastChild.remove();bubble('연결 오류, 서버가 켜져 있는지 확인해 주세요.','bot');}}}}
</script></body></html>"""


MATCH_PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>두 사람 궁합 결과</title><style>{css}</style></head><body>
<header><h1>💞 두 사람 궁합</h1><p>{score}점 · {head}</p></header>
<main>
<div class="card score"><div class="ring" style="background:{color}">{score}</div>
<div><h2 style="margin:0">궁합 한 줄</h2><p>{head}</p>
<p style="font-size:.85em;color:#666">{disclaimer}</p>
<form method="post" action="/download"><input type="hidden" name="token" value="{token}">
<button type="submit">md 다운로드 (개인정보 제외)</button></form></div></div>
<div class="card"><h2>🧭 두 사람 바탕</h2><p>{a_line}</p><p>{b_line}</p></div>
<div class="card"><h2>👍 잘 맞는 점</h2>{strengths}</div>
<div class="card"><h2>⚠️ 조심할 점</h2>{cautions}</div>
<div class="card"><h2>📖 두 사람 이야기</h2>{story}</div>
<div class="card"><h2>💬 상담 에이전트와 채팅</h2>
<div id="chat"><div id="msgs"></div>
<div class="row"><input id="q" placeholder="예: 우리 궁합 어때"><button onclick="send()">전송</button></div>
<details><summary>⚙️ LLM 연결 (선택, 미설정 시 로컬 에이전트)</summary>
<p>OpenAI 호환 엔드포인트를 입력하면 실제 LLM과 대화합니다. 키는 브라우저에만 저장됩니다.</p>
<label>Endpoint <input id="ep" placeholder="http://localhost:11434/v1"></label>
<label>API Key <input id="key" type="password" placeholder="(비워두면 로컬 에이전트)"></label>
<label>Model <input id="model" placeholder="gpt-4o-mini"></label>
<button onclick="saveCfg()">설정 저장(브라우저에만)</button></details></div></div>
<p><a href="/">← 처음으로</a></p></main>
<footer>정통 공식 기반 상세 해석.</footer>
<script>
const token="{token}";
const box=document.getElementById('msgs'), q=document.getElementById('q');
function bubble(t,cls){{const d=document.createElement('div');d.className='msg '+cls;
d.textContent=t;box.scrollTop=box.scrollHeight;box.appendChild(d);box.scrollTop=box.scrollHeight;}}
bubble('안녕하세요! 두 사람 궁합을 아는 상담 에이전트예요. 편하게 물어보세요.','bot');
q.addEventListener('keydown',e=>{{if(e.key==='Enter')send();}});
function cfg(){{return {{endpoint:localStorage.getItem('llm_ep')||'',
api_key:localStorage.getItem('llm_key')||'',model:localStorage.getItem('llm_model')||''}};}}
function saveCfg(){{localStorage.setItem('llm_ep',document.getElementById('ep').value);
localStorage.setItem('llm_key',document.getElementById('key').value);
localStorage.setItem('llm_model',document.getElementById('model').value);alert('저장됐습니다(브라우저에만).');}}
(async()=>{{document.getElementById('ep').value=localStorage.getItem('llm_ep')||'';
document.getElementById('model').value=localStorage.getItem('llm_model')||'';}})();
let hist=[];
async function send(){{const m=q.value.trim();if(!m)return;q.value='';
bubble(m,'me');hist.push({{role:'user',content:m}});
bubble('생각 중…','bot');
try{{const r=await fetch('/api/chat',{{method:'POST',
headers:{{'Content-Type':'application/json'}},
body:JSON.stringify(Object.assign({{token,message:m,history:hist.slice(0,-1)}},cfg()))}});
const j=await r.json();box.lastChild.remove();
if(j.error){{bubble('오류: '+j.error+' (로컬 답변으로 대체할게요)','bot');}}
bubble(j.reply,'bot');hist.push({{role:'assistant',content:j.reply}});}}
catch(e){{box.lastChild.remove();bubble('연결 오류, 서버가 켜져 있는지 확인해 주세요.','bot');}}}}
</script></body></html>"""


PICK_PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>길일 고르기 결과</title><style>{css}</style></head><body>
<header><h1>📅 길일 고르기</h1><p>{range_text} · {dom_name} 기준</p></header>
<main>
<div class="card"><h2>🏆 상위 일자</h2>{toprows}</div>
<div class="card"><h2>📖 기간 이야기</h2>{pickstory}</div>
<div class="card"><h2>📊 전체 표</h2>{fulltable}</div>
<div class="card"><h2>💬 상담 에이전트와 채팅</h2>
<div id="chat"><div id="msgs"></div>
<div class="row"><input id="q" placeholder="예: 다음 주 좋은 날 알려줘"><button onclick="send()">전송</button></div>
<details><summary>⚙️ LLM 연결 (선택, 미설정 시 로컬 에이전트)</summary>
<p>OpenAI 호환 엔드포인트를 입력하면 실제 LLM과 대화합니다. 키는 브라우저에만 저장됩니다.</p>
<label>Endpoint <input id="ep" placeholder="http://localhost:11434/v1"></label>
<label>API Key <input id="key" type="password" placeholder="(비워두면 로컬 에이전트)"></label>
<label>Model <input id="model" placeholder="gpt-4o-mini"></label>
<button onclick="saveCfg()">설정 저장(브라우저에만)</button></details></div></div>
<p><a href="/">← 처음으로</a></p></main>
<footer>정통 공식 기반 상세 해석.</footer>
<script>
const token="{token}";
const box=document.getElementById('msgs'), q=document.getElementById('q');
function bubble(t,cls){{const d=document.createElement('div');d.className='msg '+cls;
d.textContent=t;box.appendChild(d);box.scrollTop=box.scrollHeight;}}
bubble('안녕하세요! 고른 날짜들을 아는 상담 에이전트예요. 편하게 물어보세요.','bot');
q.addEventListener('keydown',e=>{{if(e.key==='Enter')send();}});
function cfg(){{return {{endpoint:localStorage.getItem('llm_ep')||'',
api_key:localStorage.getItem('llm_key')||'',model:localStorage.getItem('llm_model')||''}};}}
function saveCfg(){{localStorage.setItem('llm_ep',document.getElementById('ep').value);
localStorage.setItem('llm_key',document.getElementById('key').value);
localStorage.setItem('llm_model',document.getElementById('model').value);alert('저장됐습니다(브라우저에만).');}}
(async()=>{{document.getElementById('ep').value=localStorage.getItem('llm_ep')||'';
document.getElementById('model').value=localStorage.getItem('llm_model')||'';}})();
let hist=[];
async function send(){{const m=q.value.trim();if(!m)return;q.value='';
bubble(m,'me');hist.push({{role:'user',content:m}});
bubble('생각 중…','bot');
try{{const r=await fetch('/api/chat',{{method:'POST',
headers:{{'Content-Type':'application/json'}},
body:JSON.stringify(Object.assign({{token,message:m,history:hist.slice(0,-1)}},cfg()))}});
const j=await r.json();box.lastChild.remove();
if(j.error){{bubble('오류: '+j.error+' (로컬 답변으로 대체할게요)','bot');}}
bubble(j.reply,'bot');hist.push({{role:'assistant',content:j.reply}});}}
catch(e){{box.lastChild.remove();bubble('연결 오류, 서버가 켜져 있는지 확인해 주세요.','bot');}}}}
</script></body></html>"""


def render_pick_page(r: dict, token: str) -> tuple[str, str]:
    """(html, chat_summary) 반환. 개인정보 없음."""
    dom_name = {"total": "총운", "love": "연애", "career": "직장", "money": "금전"}[r["domain"]]
    toprows = "".join(
        f"<p>{x['rank']}위: {html.escape(x['label'])} {html.escape(x['ganzhi'])} "
        f"(연애 {x['love']}·직장 {x['career']}·금전 {x['money']})</p>"
        for x in r["rows"][:5])
    fulltable = ("<table class='life'><tr><th>순위</th><th>날짜</th><th>간지</th>"
                 "<th>연애</th><th>직장</th><th>금전</th><th>십신</th></tr>" +
                 "".join(f"<tr><td>{x['rank']}</td><td>{html.escape(x['label'])}</td>"
                         f"<td>{html.escape(x['ganzhi'])}</td><td>{x['love']}</td>"
                         f"<td>{x['career']}</td><td>{x['money']}</td>"
                         f"<td>{html.escape(x['god'])}</td></tr>"
                         for x in r["rows"]) + "</table>")
    page = PICK_PAGE.format(
        css=CSS, token=token,
        range_text=html.escape(f"{r['start']}~{r['end']}"),
        dom_name=dom_name, toprows=toprows, fulltable=fulltable,
        pickstory="".join(f"<p>{html.escape(x)}</p>" for x in r["story"]))
    _toprows = []
    for x in r["rows"][:5]:
        _toprows.append(f"{x['label']} {x['ganzhi']} 연애{x['love']} "
                        f"직장{x['career']} 금전{x['money']}")
    summary = (
        f"택일 {r['start']}~{r['end']}({dom_name} 기준) / "
        f"상위 {'; '.join(_toprows)} / "
        f"이야기 {'; '.join(r['story'])}")
    return page, summary


def render_match_page(r: dict, token: str) -> tuple[str, str]:
    """(html, chat_summary) 반환. 개인정보 없음."""
    strengths = "".join(f"<p>· {html.escape(x)}</p>" for x in r["strengths"]) or \
        "<p>· 특별히 도드라지는 점 없이 잔잔하게 맞는 흐름</p>"
    cautions = "".join(f"<p>· {html.escape(x)}</p>" for x in r["cautions"]) or \
        "<p>· 크게 조심할 점 없이 편안한 흐름</p>"
    info = "".join(f"<p>· {html.escape(x)}</p>" for x in r["info"])
    story = "".join(f"<p>{html.escape(x)}</p>" for x in r["story"])
    a_line = (f"나: 일간 {r['a_ilgan']}, 일지 {r['a_day_branch']}, "
              f"띠 {r['a_animal']}, 명궁 {r['a_mingong']}, 태양 {r['a_sun']}")
    b_line = (f"상대: 일간 {r['b_ilgan']}, 일지 {r['b_day_branch']}, "
              f"띠 {r['b_animal']}, 명궁 {r['b_mingong']}, 태양 {r['b_sun']}")
    page = MATCH_PAGE.format(
        css=CSS, token=token, disclaimer=html.escape(DISCLAIMER),
        score=r["score"], color=score_color(r["score"]),
        head=html.escape(r["head"]), a_line=html.escape(a_line),
        b_line=html.escape(b_line), strengths=strengths,
        cautions=cautions + info, story=story)
    summary = (
        f"궁합 {r['score']}점({r['head']}) / "
        f"잘맞는점 {'; '.join(r['strengths'])} / "
        f"조심할점 {'; '.join(r['cautions'])} / "
        f"참고 {'; '.join(r['info'])} / "
        f"이야기 {'; '.join(r['story'])} / "
        f"나 일간 {r['a_ilgan']} 일지 {r['a_day_branch']} 띠 {r['a_animal']} "
        f"명궁 {r['a_mingong']} 태양 {r['a_sun']} / "
        f"상대 일간 {r['b_ilgan']} 일지 {r['b_day_branch']} 띠 {r['b_animal']} "
        f"명궁 {r['b_mingong']} 태양 {r['b_sun']}")
    return page, summary


def score_color(score: int) -> str:
    if score >= 85:
        return "#e5486f"
    if score >= 70:
        return "#f07f13"
    if score >= 55:
        return "#7c5cff"
    if score >= 40:
        return "#3a86ff"
    return "#6c757d"


def _paras(lines: list[str]) -> str:
    return "".join(f"<p>· {html.escape(r)}</p>" for r in lines)


def _after(line: str, head: str) -> str:
    return line.split(head, 1)[1].strip() if head in line else ""


def render_report_page(md: str, text: str, token: str, target: str) -> str:
    # md에서 필요한 조각 추출 (md는 PII 없음, 안전)
    lines = md.splitlines()
    secs: dict[str, list[str]] = {}
    order: list[str] = []
    cur = ""
    for l in lines:
        if l.startswith("## "):
            cur = l[3:]
            secs[cur] = []
            order.append(cur)
        elif cur and l.startswith("- "):
            secs[cur].append(l[2:])
        elif cur and l.startswith("  ") and l.strip() and secs.get(cur):
            secs[cur][-1] += " " + l.strip()

    def sec(prefix: str) -> tuple[str, list[str]]:
        for k in order:
            if k.startswith(prefix):
                return k, secs[k]
        return "", []

    def stories_of(prefix: str) -> str:
        for k in order:
            if k.startswith(prefix):
                return "".join(f"<p>{html.escape(r[6:])}</p>" for r in secs[k]
                                if r.startswith("[이야기] "))
        return ""

    story_total = stories_of("오늘 총운")
    story_love = stories_of("오늘 연애운")
    story_career = stories_of("오늘 직장운")
    story_money = stories_of("오늘 금전운")
    story_life = stories_of("평생 운세")

    import re
    total_lines = sec("오늘 총운")[1]
    tscore = 50
    thead = ""
    score_line = next((r for r in total_lines if "오늘 총운:" in r), "")
    if score_line:
        m = re.search(r"\*\*(\d+)점", score_line)
        if m:
            tscore = int(m.group(1))
        thead = _after(score_line, "), ") or _after(score_line, ", ")
    treasons = [r for r in total_lines
                if not r.startswith(("오늘의 키워드:", "[이야기] ", "오늘 총운:", "[일운] "))]
    tkeywords = _after(next((r for r in total_lines
                             if r.startswith("오늘의 키워드:")), ""), "오늘의 키워드: ")

    love_key, love_lines = sec("오늘 연애운")
    m = re.search(r"\((\d+)점\)", love_key)
    lscore = int(m.group(1)) if m else 50
    lhead = _after(next((r for r in love_lines if r.startswith("한 줄 총평:")), ""),
                   "한 줄 총평: ")
    lreasons = [r for r in love_lines
                if not r.startswith(("한 줄 총평:", "대화 팁:", "피할 것:", "[이야기] "))]
    talk_items = [r for r in love_lines if r.startswith(("대화 팁:", "피할 것:"))]

    def domain_block(prefix: str):
        key, dlines = sec(prefix)
        mm = re.search(r"\((\d+)점\)", key)
        sc = int(mm.group(1)) if mm else 50
        hd = _after(next((r for r in dlines if r.startswith("한 줄 총평:")), ""),
                    "한 줄 총평: ")
        stars = [r for r in dlines
                 if r.startswith(("관록궁", "원국 관성", "재백궁", "원국 재성",
                                   "현재 대운", "사주 대운"))]
        tips = [r for r in dlines if "팁:" in r or r.startswith("피할 것:")]
        rs = [r for r in dlines
              if not r.startswith(("한 줄 총평:", "관록궁", "원국 관성", "재백궁",
                                    "원국 재성", "현재 대운", "사주 대운", "[이야기] "))
              and "팁:" not in r and not r.startswith("피할 것:")]
        return sc, hd, rs, stars, tips

    cscore, chead, creasons, cstars, ctips = domain_block("오늘 직장운")
    mscore, mhead, mreasons, mstars, mtips = domain_block("오늘 금전운")

    lucky = _paras(secs.get("행운 요소", []))
    divi = _paras(secs.get("오늘의 점괘", []))
    # 사주 블록은 터미널 텍스트에서 추출
    saju_lines = [l for l in text.splitlines()
                  if l.strip().startswith(("-", "·")) and ("년:" in l or "월:" in l or "일:" in l
                      or "일간" in l or "일진" in l or "시:" in l)]
    saju = "".join(f"<p>{html.escape(l.strip())}</p>" for l in saju_lines[:7])
    # 장소/팁/피할 것 분리
    places, tips, avoid = "", "", ""
    for r in secs.get("행운 요소", []):
        if r.startswith("장소:"):
            places = "".join(f"<span class='tag'>{html.escape(p.strip())}</span>"
                             for p in r[3:].split(","))
        elif r.startswith("대화 팁:"):
            tips = "".join(f"<p>· {html.escape(p.strip())}</p>" for p in r[5:].split(";"))
        elif r.startswith("피할 것:"):
            avoid = html.escape(r[5:])
    ziwei_lines = secs.get("자미두수·사주운·점성술", [])
    ziwei = "".join(f"<p>· {html.escape(r)}</p>" for r in ziwei_lines
                    if r.startswith(("음력", "오행국", "부처궁", "생년사화",
                                      "현재 대운", "올해 유년")))
    astro = "".join(f"<p>· {html.escape(r)}</p>" for r in ziwei_lines
                    if not r.startswith(("음력", "오행국", "부처궁", "생년사화",
                                          "현재 대운", "올해 유년")))
    match = "".join(f"<p>· {html.escape(r)}</p>"
                    for r in secs.get("만날 인연 아키타입 (정통 계산)", []))
    palace12 = "".join(f"<p>· {html.escape(r)}</p>"
                       for r in secs.get("자미두수 12궁 풀이", []))
    gloss = "".join(
        f"<p><b>{html.escape(r.split(':', 1)[0])}</b>: "
        f"{html.escape(r.split(':', 1)[1].strip())}</p>" if ":" in r
        else f"<p>· {html.escape(r)}</p>"
        for r in secs.get("용어 풀이", []))
    life_lines = sec("평생 운세")[1]
    lifeph = "".join(f"<p>· {html.escape(r)}</p>" for r in life_lines
                     if not r.startswith(("[연대]", "[해]", "[이야기] "))
                     and not r.startswith("지금 연대:"))
    lifecur = html.escape(_after(next((r for r in life_lines
                                       if r.startswith("지금 연대:")), ""), "지금 연대: "))
    dec_blocks = []
    for r in life_lines:
        if r.startswith("[연대] "):
            chunks = [c.strip() for c in r[5:].split(" / ")]
            body = "".join(f"<p>· {html.escape(c)}</p>" for c in chunks[1:])
            dec_blocks.append(
                f"<details><summary>{html.escape(chunks[0])}</summary>"
                f"{body}</details>")
    lifedec = "".join(dec_blocks)
    rows = []
    for r in life_lines:
        if r.startswith("[해] "):
            cells = [html.escape(c.strip()) for c in r[4:].split(" | ")]
            while len(cells) < 9:
                cells.append("")
            rows.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells[:9]) + "</tr>")
    lifetable = ("<details><summary>연도별 표 펼치기"
                 f" ({len(rows)}년)</summary><table class='life'>"
                 "<tr><th>연도</th><th>나이</th><th>간지</th>"
                 "<th>유년궁</th><th>사화</th><th>목성</th><th>토성</th><th>소운</th><th>비고</th></tr>"
                 + "".join(rows) + "</table></details>") if rows else ""
    irows = []
    for r in total_lines:
        if r.startswith("[일운] "):
            cells = [html.escape(c.strip()) for c in r[5:].split(" | ")]
            while len(cells) < 7:
                cells.append("")
            irows.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells[:7]) + "</tr>")
    iluntable = ("<details><summary>일운 30일 표 펼치기"
                 f" ({len(irows)}일)</summary><table class='life'>"
                 "<tr><th>날짜</th><th>간지</th><th>연애</th><th>직장</th>"
                 "<th>금전</th><th>십신</th><th>으뜸</th></tr>"
                 + "".join(irows) + "</table></details>") if irows else ""
    irows = []
    for r in total_lines:
        if r.startswith("[일운] "):
            cells = [html.escape(c.strip()) for c in r[5:].split(" | ")]
            while len(cells) < 7:
                cells.append("")
            irows.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells[:7]) + "</tr>")
    iluntable = ("<details><summary>일운 30일 표 펼치기"
                 f" ({len(irows)}일)</summary><table class='life'>"
                 "<tr><th>날짜</th><th>간지</th><th>연애</th><th>직장</th>"
                 "<th>금전</th><th>십신</th><th>으뜸</th></tr>"
                 + "".join(irows) + "</table></details>") if irows else ""
    lifeyong = "".join(f"<p>· {html.escape(r[5:])}</p>" for r in life_lines
                       if r.startswith("[바탕] "))
    lifedayun = "".join(f"<p>· {html.escape(r[5:])}</p>" for r in life_lines
                        if r.startswith("[대운] "))
    talk = "".join(f"<p>· {html.escape(r)}</p>" for r in talk_items)
    return REPORT_PAGE.format(
        css=CSS, target=html.escape(target), token=token,
        disclaimer=html.escape(DISCLAIMER),
        tscore=tscore, tcolor=score_color(tscore), thead=html.escape(thead),
        treasons=_paras(treasons), tkeywords=html.escape(tkeywords),
        lucky=lucky, divi=divi, saju=saju, gloss=gloss, ilun=iluntable,
        lscore=lscore, lcolor=score_color(lscore), lhead=html.escape(lhead),
        lreasons=_paras(lreasons), talk=talk, ziwei=ziwei, astro=astro, match=match,
        palace12=palace12,
        cscore=cscore, ccolor=score_color(cscore), chead=html.escape(chead),
        creasons=_paras(creasons), cstars=_paras(cstars), ctips=_paras(ctips),
        mscore=mscore, mcolor=score_color(mscore), mhead=html.escape(mhead),
        mreasons=_paras(mreasons), mstars=_paras(mstars), mtips=_paras(mtips),
        lifeph=lifeph, lifecur=lifecur, lifedec=lifedec, lifetable=lifetable,
        lifeyong=lifeyong, lifedayun=lifedayun,
        story_total=story_total, story_love=story_love,
        story_career=story_career, story_money=story_money,
        story_life=story_life)


# ---------------- JSON API (SPA 셸용, 개인정보 제외) ----------------

def api_report_data(birth: date, hour: int | None, minute: int,
                    sex: str, city: str, target: date) -> dict:
    """SPA 렌더용 구조화 데이터. PII 없음."""
    import re as _re
    from .lifetime import MAIN14
    from .narrate import narrate_palace
    from .rules import headline, love_score
    from .manseryuk import four_pillars, day_pillar
    from .advise import build_advice
    from .synthesis import detailed_reading
    md, text, summary = agent_context(birth, hour, minute, sex, city, target)
    _natal = four_pillars(birth, hour, minute, city)
    _ts, _tb = day_pillar(target)
    _br = [s for _, s in (_natal["pillars"][k]
                          for k in ("year", "month", "day", "hour"))
           if s is not None]
    _, _, _today_elem = love_score(_natal["ilgan_stem"], _br, _ts, _tb,
                                   target.isoformat())
    _love_sc, _love_reasons, _ = love_score(_natal["ilgan_stem"], _br, _ts,
                                            _tb, target.isoformat())
    _adv = build_advice(_natal["ilgan"], _today_elem, target, birth)
    ma = detailed_reading(birth, hour, minute, sex, city, target)
    ast = ma["astro"]
    zw = ma["ziwei"]
    if zw is None:
        ziwei = None
    else:
        pals = []
        for p in zw["palaces"]:
            mains = [s for s in p["stars"] if s in MAIN14]
            pals.append({"name": p["name"],
                         "ganzhi": f"{p['stem_kr']}{p['branch_kr']}",
                         "stars": list(p["stars"]),
                         "text": narrate_palace(p, mains, zw["xusui"])})
        ziwei = {"main": ma["ziwei_main"], "detail": dict(ma["ziwei_detail"]),
                 "ming_main": ma["ming_main"], "peach": list(ma["peach"]),
                 "sihua": list(ma["sihua_lines"]),
                 "daxian": ma["daxian_line"], "liunian": ma["liunian_line"],
                 "guo": ma["guo_line"], "palaces": pals}
    ilun = []
    for r in ma["ilun"]:
        m = _re.search(r"연애 (\d+) \| 직장 (\d+) \| 금전 (\d+)", r["line"])
        l, c, n = map(int, m.groups()) if m else (0, 0, 0)
        y, mo, d = r["date"].split("-")
        ilun.append({"date": r["date"], "label": f"{int(mo)}/{int(d)}",
                     "ganzhi": r["ganzhi"], "love": l, "career": c,
                     "money": n})
    lt = ma["lifetime"]
    ys = ma["yongsin"]
    god_vd = ma["venus_detail"]
    return {
        "target": target.isoformat(), "md": md,
        "hour_unknown": ma["hour_unknown"], "time_notice": ma["time_notice"],
        "lunar": ma["lunar_line"],
        "pillars": dict(_natal["strings"]), "ilgan": _natal["ilgan"],
        "scores": {"total": {"score": ma["total"]["score"],
                             "head": ma["total"]["head"]},
                   "love": {"score": ma["total"]["love"],
                            "head": headline(ma["total"]["love"])},
                   "career": {"score": ma["career"]["score"],
                              "head": ma["career"]["head"]},
                   "money": {"score": ma["money"]["score"],
                             "head": ma["money"]["head"]}},
        "reasons": {"total": list(ma["total"]["reasons"]),
                    "love": list(_love_reasons),
                    "career": list(ma["career"]["reasons"]),
                    "money": list(ma["money"]["reasons"])},
        "keywords": list(ma["total"]["keywords"]),
        "stories": {k: list(v) for k, v in ma["stories"].items()},
        "career": {"guanlu_line": ma["career"]["guanlu_line"],
                   "guan_line": ma["career"]["guan_line"],
                   "tips": list(ma["career"]["tips"]),
                   "avoid": ma["career"]["avoid"],
                   "palaces": list(ma["career"]["palaces"]),
                   "extra": list(ma["career_extra"])},
        "money": {"caibo_line": ma["money"]["caibo_line"],
                  "cai_line": ma["money"]["cai_line"],
                  "tips": list(ma["money"]["tips"]),
                  "avoid": ma["money"]["avoid"],
                  "palaces": list(ma["money"]["palaces"]),
                  "extra": list(ma["money_extra"])},
        "dist": list(ma["dist"]),
        "luck": {"color": _adv.get("color", ""),
                 "number": _adv.get("number", ""),
                 "direction": _adv.get("direction", ""),
                 "time": _adv.get("time", ""),
                 "places": list(_adv.get("places", [])),
                 "talk": list(_adv.get("talk", [])),
                 "avoid": _adv.get("avoid", ""),
                 "tarot": _adv.get("tarot", ""),
                 "tarot_line": _adv.get("tarot_line", ""),
                 "gua": _adv.get("gua", ""),
                 "gua_line": _adv.get("gua_line", ""),
                 "omikuji": _adv.get("omikuji", ""),
                 "omikuji_line": _adv.get("omikuji_line", ""),
                 "life_path": _adv.get("life_path", ""),
                 "life_path_vibe": _adv.get("life_path_vibe", "")},
        "ziwei": ziwei,
        "astro": {"sun": ast["sun"]["sign"], "moon": ast["moon"]["sign"],
                  "venus": ast["venus"]["sign"],
                  "ascendant": ast["ascendant"], "mc": ast["mc"],
                  "houses_line": ma["houses_line"],
                  "aspects_line": ma["aspects_line"],
                  "asc_line": ma["asc_line"],
                  "aspects": list(ast["aspects"]),
                  "retro": list(ast["retro_notes"]),
                  "cusp": list(ast["cusp_notes"]),
                  "compat": ast["compat_line"]},
        "dayun": {"line": ma["dayun_line"], "full": list(ma["dayun_full"]),
                  "narr": list(ys["dayun_narr"])},
        "shensha": list(ma["shensha_lines"]),
        "yongsin": {"ilgang": ys["ilgang"],
                    "geguk": ys["analysis"]["geguk"],
                    "strong_label": ys["analysis"]["strong_label"],
                    "yongsin": ys["analysis"]["yongsin"]},
        "god": {"god": ma["god"], "side": ma["side"],
                "vibe": ma["god_vibe"], "tip": ma["god_tip"],
                "job": ma["god_job"], "star_line": ma["star_line"],
                "stage": ma["stage"], "stage_love": ma["stage_love"],
                "dohwa": list(ma["dohwa_lines"]), "hong": ma["hong_line"],
                "timing": ma["timing"], "meet_top3": list(ma["meet_top3"]),
                "venus": ma["venus"], "venus_style": god_vd["style"],
                "venus_ideal": god_vd["ideal"], "venus_how": god_vd["how"],
                "moon": ma["moon"], "moon_need": ma["moon_need"],
                "love_extra": list(ma["love_extra"])},
        "month_line": ma["month_line"], "ilun": ilun,
        "lifetime": {"phases": [{"name": p["name"], "line": p["line"]}
                                for p in lt["phases"]],
                     "current": {"range": list(lt["current"]["range"]),
                                 "short": lt["current"]["short"]},
                     "decades": [{"range": list(d["range"]),
                                  "saju": d["saju"], "ziwei": d["ziwei"],
                                  "parts": list(d["parts"])}
                                 for d in lt["decades"]],
                     "years": [{"year": y["year"], "age": y["age"],
                                "line": y["line"]} for y in lt["years"]]},
        "summary": summary,
    }


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


def api_pick_data(r: dict) -> dict:
    """택일 결과 JSON. PII 없음."""
    dom_name = {"total": "총운", "love": "연애", "career": "직장",
                "money": "금전"}[r["domain"]]
    return {"start": r["start"], "end": r["end"], "domain": r["domain"],
            "dom_name": dom_name, "story": list(r["story"]),
            "rows": [{"rank": x["rank"], "label": x["label"],
                      "ganzhi": x["ganzhi"], "love": x["love"],
                      "career": x["career"], "money": x["money"],
                      "god": x["god"]} for x in r["rows"]]}


# ---------------- SPA 셸 (CSS) ----------------
APP_CSS = """
:root{
  --paper:#0f0d0b; --card:#1a1613; --card2:#242019;
  --ink:#f0e9da; --muted:#a89a83; --faint:#7d7261;
  --line:#342a1f; --accent:#d1543a; --accent-hi:#e0684f;
  --accent-soft:rgba(209,84,58,.16); --ease:cubic-bezier(.23,1,.32,1); --r:12px;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);
  font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;
  font-size:16px;line-height:1.6}
.serif{font-family:Batang,'Noto Serif KR',serif}
.top{position:sticky;top:0;z-index:20;display:grid;
  grid-template-columns:64px 1fr 64px;align-items:center;
  padding:.55rem .6rem;background:rgba(15,13,11,.94);
  backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.top .title{text-align:center;font-weight:800;font-size:1.02rem}
.backbtn{background:none;border:0;color:var(--ink);font-size:1rem;
  min-height:44px;min-width:44px;cursor:pointer;font-weight:700}
.backbtn.hide{visibility:hidden}
.homebtn{background:none;border:1px solid var(--line);border-radius:9px;
  color:var(--ink);font-size:.82rem;min-height:40px;cursor:pointer}
main{max-width:720px;margin:0 auto;padding:1rem 1rem 3rem}
.view{display:none}
.view.on{display:block;animation:fade .22s var(--ease)}
@keyframes fade{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.hero{display:flex;gap:1rem;align-items:center;padding:1.6rem .4rem .8rem}
.stamp{flex:none;width:64px;height:64px;border-radius:14px;background:var(--accent);
  color:#fff;display:flex;align-items:center;justify-content:center;
  font-size:1.3rem;font-weight:800}
.hero h1{font-size:clamp(1.4rem,5vw,1.8rem);line-height:1.3;margin:0;
  text-wrap:balance}
.hero p{margin:.3rem 0 0;color:var(--muted);font-size:.9rem}
.group{font-size:.8rem;font-weight:800;letter-spacing:.06em;color:var(--muted);
  margin:1.4rem .2rem .55rem}
.menu{background:var(--card);border:1px solid var(--line);border-radius:var(--r);
  overflow:hidden}
.menu button{display:flex;width:100%;text-align:left;gap:.9rem;align-items:center;
  background:none;border:0;border-bottom:1px solid var(--line);
  padding:.95rem 1.1rem;min-height:60px;cursor:pointer;color:var(--ink)}
.menu button:last-child{border-bottom:0}
.menu button:active{background:var(--card2)}
.menu .no{flex:none;width:30px;height:30px;border-radius:50%;background:var(--accent-soft);
  color:var(--accent-hi);font-weight:800;display:flex;align-items:center;
  justify-content:center;font-size:.9rem}
.menu .tx{flex:1}
.menu .tx b{display:block;font-size:1rem}
.menu .tx span{font-size:.83rem;color:var(--muted)}
.menu .arr{color:var(--faint);font-size:1.1rem}
.card{background:var(--card);border:1px solid var(--line);
  border-radius:var(--r);padding:1.1rem 1.15rem;margin:0 0 .9rem}
.card h2{font-size:1.08rem;margin:0 0 .7rem}
.card h2 .num{font-family:Batang,serif;color:var(--accent);margin-right:.45rem}
.card p{margin:.5rem 0}
.muted{color:var(--muted)} .small{font-size:.85rem}
.chips{display:flex;flex-wrap:wrap;gap:.45rem;margin:.6rem 0}
.chip{background:var(--card2);border:1px solid var(--line);border-radius:999px;
  padding:.3rem .8rem;font-size:.82rem}
form.grid{display:grid;gap:.7rem}
label.f{display:grid;gap:.3rem;font-size:.85rem;color:var(--muted)}
input,select{background:#221c16;border:1px solid var(--line);
  border-radius:10px;color:var(--ink);padding:.65rem .8rem;font-size:1rem;
  min-height:44px;width:100%}
input:focus-visible,select:focus-visible,button:focus-visible,
  summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.row2{display:grid;grid-template-columns:1fr 1fr;gap:.7rem}
.check{display:flex;align-items:center;gap:.5rem;font-size:.9rem;color:var(--ink)}
.check input{width:auto;min-height:22px}
button.go{background:var(--accent);border:0;border-radius:10px;color:#fff;
  font-weight:800;font-size:1rem;padding:.8rem;min-height:48px;cursor:pointer;width:100%}
button.go:active{transform:scale(.97)}
button.go:disabled{opacity:.55;cursor:wait}
button.ghost{background:var(--card);border:1px solid var(--line);
  border-radius:10px;color:var(--ink);padding:.65rem 1rem;min-height:44px;cursor:pointer}
button.ghost:active{transform:scale(.97)}
.btnrow{display:grid;grid-template-columns:1fr 1fr;gap:.6rem;margin:.9rem 0}
.scorebig{display:flex;gap:1rem;align-items:center}
.bignum{font-family:Batang,serif;font-size:3rem;line-height:1;color:var(--accent-hi)}
.bars{display:grid;gap:.45rem;margin-top:.9rem}
.bar-row{display:grid;grid-template-columns:52px 1fr 40px;gap:.6rem;align-items:center;font-size:.85rem}
.bar{height:10px;border-radius:99px;background:var(--card2);border:1px solid var(--line);overflow:hidden}
.bar i{display:block;height:100%;width:0;background:var(--accent);border-radius:99px;
  transition:width .7s var(--ease)}
.bar-row b{text-align:right}
.dtabs{display:flex;gap:.4rem;overflow-x:auto;padding:.4rem .1rem .7rem;
  position:sticky;top:57px;z-index:10;background:var(--paper)}
.dtab{flex:none;background:var(--card);border:1px solid var(--line);
  color:var(--muted);border-radius:999px;padding:.5rem 1rem;font-size:.9rem;
  min-height:44px;cursor:pointer}
.dtab.on{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:700}
.dsec{display:none} .dsec.on{display:block;animation:fade .22s var(--ease)}
ul.tight{margin:.4rem 0;padding-left:1.1rem}
ul.tight li{margin:.3rem 0}
table.grid{border-collapse:collapse;width:100%;font-size:.82rem}
table.grid td,table.grid th{border:1px solid var(--line);padding:.35rem .45rem;text-align:center}
table.grid th{background:var(--card2)}
details.acc{border:1px solid var(--line);border-radius:10px;margin:.45rem 0;background:var(--card2)}
details.acc summary{padding:.7rem .9rem;cursor:pointer;min-height:44px;font-weight:700}
details.acc .body{padding:0 .9rem .8rem}
details.acc .body p{margin:.4rem 0;font-size:.92rem}
.chatbox{display:flex;flex-direction:column;gap:.5rem}
.msgs{display:flex;flex-direction:column;gap:.5rem;max-height:320px;overflow-y:auto}
.msg{padding:.6rem .85rem;border-radius:12px;font-size:.92rem;line-height:1.55;max-width:92%;
  background:var(--card2);border:1px solid var(--line)}
.msg.me{align-self:flex-end;background:var(--card2)}
.msg.bot{align-self:flex-start;background:var(--accent-soft);border-color:var(--accent)}
.chatrow{display:flex;gap:.5rem}
.chatrow input{flex:1}
.chatrow button{flex:none;width:auto;padding:.6rem 1.1rem}
.err{background:#f9e4dc;border:1px solid var(--accent);
  border-radius:10px;padding:.7rem .9rem;font-size:.9rem}
.spin{text-align:center;color:var(--muted);padding:1.4rem}
#sheet{position:fixed;left:0;right:0;bottom:0;z-index:40;display:none;
  background:var(--card);border-top:1px solid var(--line);border-radius:16px 16px 0 0;
  padding:1.1rem 1.2rem 2rem;max-height:60vh;overflow-y:auto}
#sheet.on{display:block;animation:fade .22s var(--ease)}
#sheet h3{margin:.2rem 0 .5rem}
.scrim{position:fixed;inset:0;z-index:35;background:rgba(0,0,0,.4);display:none}
.scrim.on{display:block}
footer.site{max-width:720px;margin:0 auto;padding:0 1rem 2.5rem;color:var(--faint);font-size:.8rem}
@media print{.top,.chatbox,button.go,button.ghost,.dtabs,.btnrow{display:none}main{padding:0}body{background:#fff}.card{break-inside:avoid}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""

# ---------------- SPA 셸 (HTML) ----------------
APP_BODY = """
<header class="top">
<button class="backbtn hide" id="backBtn" aria-label="뒤로 가기">&lt; 뒤로</button>
<div class="title" id="topTitle">종합 사주</div>
<button class="homebtn" id="homeBtn">처음</button>
</header>
<main id="main">
<section id="v-home" class="view on">
  <div class="hero">
    <div class="stamp serif">오늘</div>
    <div><h1 class="serif">어떤 운세를 볼까요</h1>
    <p>생년월일만 입력하면 바로 결과를 봅니다. 입력값은 저장되지 않습니다.</p></div>
  </div>
  <div class="group">오늘의 운세</div>
  <div class="menu">
    <button data-go="v-fortune"><span class="no serif">1</span>
      <span class="tx"><b>오늘의 운세 보기</b><span>총운, 연애, 직장, 금전, 평생 흐름까지</span></span><span class="arr">&gt;</span></button>
  </div>
  <div class="group">애정과 궁합</div>
  <div class="menu">
    <button data-go="v-match"><span class="no serif">2</span>
      <span class="tx"><b>두 사람 궁합 보기</b><span>잘 맞는 점과 조심할 점을 대칭으로</span></span><span class="arr">&gt;</span></button>
  </div>
  <div class="group">날짜 고르기</div>
  <div class="menu">
    <button data-go="v-pick"><span class="no serif">3</span>
      <span class="tx"><b>길일 고르기</b><span>기간 안에서 목적별 좋은 날 순위</span></span><span class="arr">&gt;</span></button>
  </div>
  <div class="group">알아보기</div>
  <div class="menu">
    <button id="glossOpen"><span class="no serif">?</span>
      <span class="tx"><b>용어 풀이</b><span>도화, 충, 대운, 무슨 뜻일까</span></span><span class="arr">&gt;</span></button>
  </div>
  <div class="card" id="glossCard" style="display:none;margin-top:.9rem"><h2><span class="num">?</span>용어 풀이</h2>
    <form class="grid" id="glossForm"><label class="f">궁금한 말
    <input id="glossQ" placeholder="예: 도화, 충, 대운"></label>
    <button class="go" type="submit">뜻 보기</button></form>
    <div id="glossOut" style="margin-top:.6rem"></div>
  </div>
</section>
<section id="v-fortune" class="view">
  <div class="card"><h2><span class="num">1</span>오늘의 운세 보기</h2>
    <form class="grid" id="fFortune">
      <label class="f">양력 생년월일<input name="birth" type="date" value="1995-02-28" required></label>
      <div class="row2">
        <label class="f">태어난 시간<input name="birth_time" type="time" value="12:00"></label>
        <label class="check"><input name="unknown_time" type="checkbox" value="1"> 모름</label>
      </div>
      <div class="row2">
        <label class="f">성별<select name="sex"><option value="male">남자</option><option value="female">여자</option></select></label>
        <label class="f">태어난 도시<input name="city" value="부산"></label>
      </div>
      <label class="check"><input name="tomorrow" type="checkbox" value="1"> 내일 운세 보기</label>
      <button class="go" type="submit">운세 보기</button>
    </form></div>
  <div id="rFortune"></div>
</section>
<section id="v-match" class="view">
  <div class="card"><h2><span class="num">2</span>두 사람 궁합 보기</h2>
    <form class="grid" id="fMatch">
      <div class="row2">
        <label class="f">내 생년월일<input name="birth" type="date" value="1995-02-28" required></label>
        <label class="f">상대 생년월일<input name="birth2" type="date" value="1997-06-15" required></label>
      </div>
      <div class="row2">
        <label class="f">내가 태어난 시간<input name="birth_time" type="time" value="12:00"></label>
        <label class="f">상대가 태어난 시간<input name="birth2_time" type="time" value="12:00"></label>
      </div>
      <div class="row2">
        <label class="check"><input name="unknown_time" type="checkbox" value="1"> 내 시간 모름</label>
        <label class="check"><input name="unknown_time2" type="checkbox" value="1"> 상대 시간 모름</label>
      </div>
      <div class="row2">
        <label class="f">내 성별<select name="sex"><option value="male">남자</option><option value="female">여자</option></select></label>
        <label class="f">상대 성별<select name="sex2"><option value="female">여자</option><option value="male">남자</option></select></label>
      </div>
      <div class="row2">
        <label class="f">내가 태어난 도시<input name="city" value="부산"></label>
        <label class="f">상대가 태어난 도시<input name="city2" value="서울"></label>
      </div>
      <button class="go" type="submit">궁합 보기</button>
    </form></div>
  <div id="rMatch"></div>
</section>
<section id="v-pick" class="view">
  <div class="card"><h2><span class="num">3</span>길일 고르기</h2>
    <form class="grid" id="fPick">
      <label class="f">양력 생년월일<input name="birth" type="date" value="1995-02-28" required></label>
      <div class="row2">
        <label class="f">태어난 시간<input name="birth_time" type="time" value="12:00"></label>
        <label class="check"><input name="unknown_time" type="checkbox" value="1"> 모름</label>
      </div>
      <div class="row2">
        <label class="f">성별<select name="sex"><option value="male">남자</option><option value="female">여자</option></select></label>
        <label class="f">태어난 도시<input name="city" value="부산"></label>
      </div>
      <div class="row2">
        <label class="f">시작일<input name="from_date" type="date" value="2026-10-01" required></label>
        <label class="f">끝일<input name="to_date" type="date" value="2026-10-31" required></label>
      </div>
      <label class="f">목적<select name="domain"><option value="total">총운</option><option value="love">연애</option><option value="career">직장</option><option value="money">금전</option></select></label>
      <button class="go" type="submit">길일 보기</button>
    </form></div>
  <div id="rPick"></div>
</section>
</main>
<footer class="site">정통 공식 기반 상세 해석. 단정적 예언이 아니라 흐름으로 읽습니다.</footer>
<div class="scrim" id="scrim"></div>
<div id="sheet"><h3 id="sheetTitle"></h3><div id="sheetBody"></div>
<button class="ghost" id="sheetClose" style="margin-top:.8rem;width:100%">닫기</button></div>
"""

# ---------------- SPA 셸 (JS) ----------------
APP_JS = """
const $=id=>document.getElementById(id);
const esc=s=>String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
  .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const li=a=>(a||[]).map(x=>'<li>'+esc(x)+'</li>').join('');
const paras=a=>(a||[]).map(x=>'<p>'+esc(x)+'</p>').join('');
const card=(num,title,inner)=>'<div class="card"><h2><span class="num">'+esc(num)+
  '</span>'+esc(title)+'</h2>'+inner+'</div>';
const TITLES={'v-home':'종합 사주','v-fortune':'오늘의 운세','v-match':'궁합 보기','v-pick':'길일 고르기'};
function showView(id){
  document.querySelectorAll('.view').forEach(v=>v.classList.toggle('on',v.id===id));
  $('topTitle').textContent=TITLES[id]||'종합 사주';
  $('backBtn').classList.toggle('hide',id==='v-home');
  window.scrollTo(0,0);
}
function nav(id,push){
  if(push===undefined) push=true;
  if(push){ location.hash='#/'+id.slice(2); return; }
  showView(id);
}
window.addEventListener('hashchange',()=>{
  const id='v-'+(location.hash.replace('#/','')||'home');
  if(TITLES[id]) showView(id);
});
(function init(){
  const id='v-'+(location.hash.replace('#/','')||'home');
  showView(TITLES[id]?id:'v-home');
})();
$('backBtn').addEventListener('click',()=>{
  if(window.history.length>1){ window.history.back(); }
  else{ nav('v-home'); }
});
$('homeBtn').addEventListener('click',()=>nav('v-home'));
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>nav(b.dataset.go)));
async function postJSON(url,obj){
  const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(obj)});
  if(!r.ok) throw new Error('서버 응답 '+r.status);
  return r.json();
}
function formObj(form){
  const o={};
  new FormData(form).forEach((v,k)=>{o[k]=v;});
  return o;
}
function downloadMd(token){
  const f=document.createElement('form');
  f.method='post'; f.action='/download';
  const i=document.createElement('input');
  i.type='hidden'; i.name='token'; i.value=token;
  f.appendChild(i); document.body.appendChild(f); f.submit(); f.remove();
}
function navBtns(token,outId){
  return '<div class="btnrow"><button class="ghost" data-retry="'+outId+'">다시 입력</button>'+
    '<button class="ghost" data-dl="'+token+'">md 저장</button></div>'+
    '<button class="ghost" style="width:100%" data-home="1">처음으로</button>';
}
document.addEventListener('click',e=>{
  const r=e.target.closest('[data-retry]');
  if(r){ $(r.dataset.retry).innerHTML=''; window.scrollTo({top:0,behavior:'smooth'}); return; }
  const d=e.target.closest('[data-dl]');
  if(d){ downloadMd(d.dataset.dl); return; }
  if(e.target.closest('[data-home]')){ nav('v-home'); return; }
});
function chatCard(token,boxId,inputId){
  return '<div class="card"><h2><span class="num">문</span>상담 에이전트에게 묻기</h2>'+
  '<div class="chatbox"><div class="msgs" id="'+boxId+'"></div>'+
  '<div class="chatrow"><input id="'+inputId+'" placeholder="예: 오늘 직장운 어때" maxlength="200">'+
  '<button class="go" style="width:auto" data-chat="'+token+'|'+boxId+'|'+inputId+'">전송</button></div>'+
  '<p class="muted small">리포트를 아는 로컬 에이전트가 답합니다. 단정적 예언은 하지 않습니다.</p></div></div>';
}
document.addEventListener('click',async e=>{
  const b=e.target.closest('[data-chat]');
  if(!b) return;
  const parts=b.dataset.chat.split('|');
  const box=$(parts[1]);
  const input=$(parts[2]);
  const msg=input.value.trim();
  if(!msg) return;
  input.value='';
  box.insertAdjacentHTML('beforeend','<div class="msg me">'+esc(msg)+'</div>');
  box.insertAdjacentHTML('beforeend','<div class="msg bot" data-tmp="1">생각 중...</div>');
  box.scrollTop=box.scrollHeight;
  try{
    const j=await postJSON('/api/chat',{token:parts[0],message:msg});
    box.querySelector('[data-tmp]').outerHTML='<div class="msg bot">'+esc(j.reply)+'</div>';
  }catch(err){
    box.querySelector('[data-tmp]').outerHTML='<div class="msg bot">연결 오류, 서버가 켜져 있는지 확인해 주세요.</div>';
  }
  box.scrollTop=box.scrollHeight;
});
let GLOSS=null;
async function getGloss(){
  if(GLOSS) return GLOSS;
  const r=await fetch('/api/glossary');
  GLOSS=await r.json();
  return GLOSS;
}
function openSheet(title,body){
  $('sheetTitle').textContent=title;
  $('sheetBody').innerHTML=body;
  $('sheet').classList.add('on'); $('scrim').classList.add('on');
}
function closeSheet(){
  $('sheet').classList.remove('on'); $('scrim').classList.remove('on');
}
$('sheetClose').addEventListener('click',closeSheet);
$('scrim').addEventListener('click',closeSheet);
$('glossOpen').addEventListener('click',()=>{
  const c=$('glossCard');
  c.style.display=c.style.display==='none'?'block':'none';
  if(c.style.display==='block') c.scrollIntoView({behavior:'smooth',block:'center'});
});
$('glossForm').addEventListener('submit',async e=>{
  e.preventDefault();
  const q=$('glossQ').value.trim();
  if(!q) return;
  const g=await getGloss();
  const keys=Object.keys(g).sort((a,b)=>b.length-a.length);
  const hit=keys.find(k=>k.length>=2&&q.includes(k))||keys.find(k=>q.includes(k));
  $('glossOut').innerHTML=hit?'<p><b>'+esc(hit)+'</b>: '+esc(g[hit])+'</p>'
    :'<p class="muted">뜻을 찾지 못했어요. 다른 말로 물어보세요.</p>';
});
function dtabsHTML(){
  return '<div class="dtabs">'+
    '<button class="dtab on" data-d="total">총운</button>'+
    '<button class="dtab" data-d="love">연애</button>'+
    '<button class="dtab" data-d="career">직장</button>'+
    '<button class="dtab" data-d="money">금전</button>'+
    '<button class="dtab" data-d="life">평생</button></div>';
}
document.addEventListener('click',e=>{
  const t=e.target.closest('.dtab');
  if(!t) return;
  const wrap=t.closest('[data-dtabs]');
  wrap.querySelectorAll('.dtab').forEach(x=>x.classList.toggle('on',x===t));
  wrap.querySelectorAll('.dsec').forEach(s=>s.classList.toggle('on',s.dataset.s===t.dataset.d));
});
function barsHTML(scores){
  const rows=[['총운',scores.total.score],['연애',scores.love.score],
    ['직장',scores.career.score],['금전',scores.money.score]];
  return '<div class="bars">'+rows.map(r=>'<div class="bar-row"><span>'+r[0]+
    '</span><span class="bar"><i data-w="'+r[1]+'"></i></span><b>'+r[1]+'</b></div>').join('')+'</div>';
}
function animBars(root){
  root.querySelectorAll('.bar i').forEach(el=>{
    requestAnimationFrame(()=>requestAnimationFrame(()=>{el.style.width=el.dataset.w+'%';}));
  });
}
function renderFortune(d,token){
  const S=d.scores;
  let h=card('◎','오늘 한눈에','<div class="scorebig"><div class="bignum serif">'+S.total.score+
    '<span style="font-size:1rem">점</span></div><div><p style="margin:0">'+esc(S.total.head)+'</p>'+
    '<p class="muted small">'+esc(d.target)+' / '+esc(d.lunar)+'</p></div></div>'+
    barsHTML(S)+
    '<div class="chips">'+d.keywords.map(k=>'<span class="chip">'+esc(k)+'</span>').join('')+'</div>');
  if(d.hour_unknown) h+='<p class="muted small">'+esc(d.time_notice)+'</p>';
  const secTotal=card('1','총운 흐름',paras(d.stories.total)+'<ul class="tight">'+li(d.reasons.total)+'</ul>'+
    '<p class="small">'+esc(d.month_line)+'</p>');
  const secLove=card('2','연애',paras(d.stories.love)+'<ul class="tight">'+li(d.reasons.love)+'</ul>'+
    '<p>배우자 자리에는 <b>'+esc(d.god.god)+'</b> 기운. '+esc(d.god.side)+'</p>'+
    '<p class="small">'+esc(d.god.vibe)+'</p><p class="small">팁: '+esc(d.god.tip)+'</p>'+
    '<p class="small">직업군: '+esc(d.god.job)+'</p><p class="small">'+esc(d.god.star_line)+'</p>'+
    '<p class="small">일주 운성 '+esc(d.god.stage)+': '+esc(d.god.stage_love)+'</p>'+
    paras(d.god.dohwa)+'<p class="small">'+esc(d.god.hong)+'</p>'+
    '<p class="small">'+esc(d.god.timing)+'</p>'+
    '<p class="small">TOP3: '+esc(d.god.meet_top3.join(', '))+'</p>'+
    paras(d.god.love_extra));
  const secCareer=card('3','직장',paras(d.stories.career)+'<ul class="tight">'+li(d.reasons.career)+'</ul>'+
    '<p class="small">'+esc(d.career.guanlu_line)+'</p><p class="small">'+esc(d.career.guan_line)+'</p>'+
    '<p class="small">팁: '+esc(d.career.tips.join(', '))+' / 피할 것: '+esc(d.career.avoid)+'</p>'+
    '<ul class="tight">'+li(d.career.palaces.concat(d.career.extra))+'</ul>');
  const secMoney=card('4','금전',paras(d.stories.money)+'<ul class="tight">'+li(d.reasons.money)+'</ul>'+
    '<p class="small">'+esc(d.money.caibo_line)+'</p><p class="small">'+esc(d.money.cai_line)+'</p>'+
    '<p class="small">팁: '+esc(d.money.tips.join(', '))+' / 피할 것: '+esc(d.money.avoid)+'</p>'+
    '<ul class="tight">'+li(d.money.palaces.concat(d.money.extra))+'</ul>');
  let life='<ul class="tight">'+li(d.lifetime.phases.map(p=>p.line))+'</ul>'+
    '<p class="small">'+esc(d.lifetime.current.short)+'</p>'+
    '<p class="small">기질: '+esc(d.yongsin.ilgang)+
    ' / '+esc(d.yongsin.geguk)+', '+esc(d.yongsin.strong_label)+
    ' / 용신 '+esc(d.yongsin.yongsin)+'</p>'+
    d.lifetime.decades.map(x=>'<details class="acc"><summary>'+esc(x.range[0])+'~'+esc(x.range[1])+'세</summary><div class="body">'+paras(x.parts)+'</div></details>').join('')+
    '<details class="acc"><summary>연도별 표</summary><div class="body"><ul class="tight">'+li(d.lifetime.years.map(y=>y.line))+'</ul></div></details>'+
    '<details class="acc"><summary>사주 대운 전체</summary><div class="body"><ul class="tight">'+li(d.dayun.full.concat(d.dayun.narr))+'</ul></div></details>';
  const secLife=card('5','평생 흐름',paras(d.stories.life)+life);
  let mid='';
  mid+=card('6','행운 요소','<p>색 '+esc(d.luck.color)+' / 번호 '+esc(d.luck.number)+
    ' / 방향 '+esc(d.luck.direction)+' / 시간 '+esc(d.luck.time)+'</p>'+
    '<p class="small">장소: '+esc(d.luck.places.join(', '))+'</p>'+
    '<p class="small">대화: '+esc(d.luck.talk.join(' / '))+' / 피할 것: '+esc(d.luck.avoid)+'</p>'+
    '<p class="small">타로 '+esc(d.luck.tarot)+': '+esc(d.luck.tarot_line)+'</p>'+
    '<p class="small">주역 '+esc(d.luck.gua)+': '+esc(d.luck.gua_line)+'</p>'+
    '<p class="small">오미쿠지 '+esc(d.luck.omikuji)+': '+esc(d.luck.omikuji_line)+'</p>'+
    '<p class="small">생명수 '+esc(d.luck.life_path)+': '+esc(d.luck.life_path_vibe)+'</p>');
  mid+=card('7','기운 분포','<ul class="tight">'+li(d.dist)+'</ul>');
  if(d.ziwei){
    const z=d.ziwei;
    mid+=card('8','자미두수 명반','<p>부처궁 주성 <b>'+esc(z.main)+'</b></p>'+
      '<p class="small">'+esc(z.guo)+'</p><p class="small">'+esc(z.daxian)+'</p>'+
      '<p class="small">'+esc(z.liunian)+'</p><ul class="tight">'+li(z.sihua)+'</ul>'+
      z.palaces.map(p=>'<details class="acc"><summary>'+esc(p.name)+' ('+esc(p.ganzhi)+')</summary><div class="body"><p>'+esc(p.text)+'</p><p class="muted small">'+esc(p.stars.join(', '))+'</p></div></details>').join(''));
  }else{
    mid+=card('8','자미두수 명반','<p class="muted">시간 미상이라 명반 배치 제외, 사주 대운으로 봐.</p>');
  }
  mid+=card('9','점성술 차트','<p>태양 '+esc(d.astro.sun)+' / 달 '+esc(d.astro.moon)+' / 금성 '+esc(d.astro.venus)+'</p>'+
    '<p class="small">'+esc(d.astro.asc_line)+'</p><p class="small">'+esc(d.astro.houses_line)+'</p>'+
    '<p class="small">'+esc(d.astro.aspects_line)+'</p><p class="small">'+esc(d.astro.compat)+'</p>');
  mid+=card('10','신살','<ul class="tight">'+li(d.shensha)+'</ul>');
  mid+=card('11','일운 30일','<table class="grid"><tr><th>날짜</th><th>간지</th><th>연애</th><th>직장</th><th>금전</th></tr>'+
    d.ilun.map(r=>'<tr><td>'+esc(r.label)+'</td><td>'+esc(r.ganzhi)+'</td><td>'+r.love+'</td><td>'+r.career+'</td><td>'+r.money+'</td></tr>').join('')+'</table>');
  return h+
    '<div data-dtabs>'+dtabsHTML()+
    '<div class="dsec on" data-s="total">'+secTotal+'</div>'+
    '<div class="dsec" data-s="love">'+secLove+'</div>'+
    '<div class="dsec" data-s="career">'+secCareer+'</div>'+
    '<div class="dsec" data-s="money">'+secMoney+'</div>'+
    '<div class="dsec" data-s="life">'+secLife+'</div></div>'+mid+
    chatCard(token,'boxF','inF')+navBtns(token,'rFortune');
}
function renderMatch(d,token){
  let h=card('◎','두 사람 궁합','<div class="scorebig"><div class="bignum serif">'+d.score+
    '<span style="font-size:1rem">점</span></div><div><p style="margin:0">'+esc(d.head)+'</p></div></div>');
  h+=card('1','두 사람 이야기',paras(d.story));
  h+=card('2','잘 맞는 점',paras(d.strengths.length?d.strengths:['특별히 도드라지는 점 없이 잔잔하게 맞는 흐름']));
  h+=card('3','조심할 점',paras(d.cautions.length?d.cautions:['크게 조심할 점 없이 편안한 흐름'])+paras(d.info));
  h+=card('4','두 사람 바탕','<p>나: 일간 '+esc(d.a.ilgan)+', 일지 '+esc(d.a.branch)+', 띠 '+esc(d.a.animal)+', 명궁 '+esc(d.a.mingong)+', 태양 '+esc(d.a.sun)+'</p>'+
    '<p>상대: 일간 '+esc(d.b.ilgan)+', 일지 '+esc(d.b.branch)+', 띠 '+esc(d.b.animal)+', 명궁 '+esc(d.b.mingong)+', 태양 '+esc(d.b.sun)+'</p>');
  return h+chatCard(token,'boxM','inM')+navBtns(token,'rMatch');
}
function renderPick(d,token){
  let h=card('◎','길일 고르기','<p>'+esc(d.start)+' ~ '+esc(d.end)+' ('+esc(d.dom_name)+' 기준)</p>'+paras(d.story));
  h+=card('1','상위 일자','<table class="grid">'+
    '<tr><th>순위</th><th>날짜</th><th>간지</th><th>연애</th><th>직장</th><th>금전</th><th>십신</th></tr>'+
    d.rows.map(r=>'<tr><td>'+r.rank+'</td><td>'+esc(r.label)+'</td><td>'+esc(r.ganzhi)+'</td><td>'+r.love+'</td><td>'+r.career+'</td><td>'+r.money+'</td><td>'+esc(r.god)+'</td></tr>').join('')+'</table>');
  return h+chatCard(token,'boxP','inP')+navBtns(token,'rPick');
}
async function submitForm(formId,outId,url,render){
  const form=$(formId);
  form.addEventListener('submit',async e=>{
    e.preventDefault();
    const out=$(outId);
    out.innerHTML='<div class="spin">계산 중...</div>';
    const btn=form.querySelector('button.go');
    btn.disabled=true;
    try{
      const j=await postJSON(url,formObj(form));
      out.innerHTML=render(j.data,j.token);
      animBars(out);
      out.scrollIntoView({block:'start'});
    }catch(err){
      out.innerHTML='<div class="err">불러오지 못했어요. 입력값(날짜 형식)을 확인해 주세요.</div>';
    }
    btn.disabled=false;
  });
}
submitForm('fFortune','rFortune','/api/report',renderFortune);
submitForm('fMatch','rMatch','/api/match',renderMatch);
submitForm('fPick','rPick','/api/pick',renderPick);
"""

def app_page() -> str:
    """SPA 셸 한 장. 개인정보 없음."""
    return ("<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>종합 사주</title><style>" + APP_CSS + "</style></head><body>"
            + APP_BODY + "<script>" + APP_JS + "</script></body></html>")


# ---------------- HTTP 서버 ----------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # 개인정보가 로그에 남지 않도록
        pass

    def _send(self, body: bytes, ctype: str, disp: str = ""):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        if disp:
            self.send_header("Content-Disposition", disp)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self._send(app_page().encode("utf-8"),
                       "text/html; charset=utf-8")
        elif self.path == "/healthz":
            body = b'{"ok":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/glossary":
            from .glossary import TERMS
            body = json.dumps(TERMS, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def _fields(self):
        n = int(self.headers.get("Content-Length", 0))
        ctype = self.headers.get("Content-Type", "")
        raw = self.rfile.read(n)
        if "application/json" in ctype:
            return json.loads(raw.decode("utf-8") or "{}")
        from urllib.parse import parse_qs
        return {k: v[0] for k, v in
                parse_qs(raw.decode("utf-8")).items()}

    def do_POST(self):  # noqa: C901
        try:
            q = self._fields()
        except Exception:
            self.send_error(400, "요청 형식 오류")
            return
        if self.path == "/report":
            from .cli import _parse_hm
            try:
                birth = datetime.strptime(q.get("birth", ""), "%Y-%m-%d").date()
                bt = "모름" if q.get("unknown_time") else (q.get("birth_time", "12:00") or "12:00")
                hh, mm = _parse_hm(bt)
                sex = q.get("sex", "male")
                city = q.get("city", "서울") or "서울"
            except ValueError:
                self.send_error(400, "입력 형식 오류")
                return
            target = date.today() + (timedelta(days=1) if q.get("tomorrow") else timedelta(0))
            md, text, summary = agent_context(birth, hh, mm, sex, city, target)
            token = secrets.token_hex(8)
            _CONTEXTS[token] = {"md": md, "summary": summary,
                                "target": target.isoformat(), "created": time.time()}
            page = render_report_page(md, text, token, target.isoformat())
            self._send(page.encode("utf-8"), "text/html; charset=utf-8")
        elif self.path == "/match":
            from .matchmaking import compatibility
            from .cli import build_match_report, _parse_hm
            try:
                birth = datetime.strptime(q.get("birth", ""), "%Y-%m-%d").date()
                bt = "모름" if q.get("unknown_time") else (q.get("birth_time", "12:00") or "12:00")
                hh, mm = _parse_hm(bt)
                sex = q.get("sex", "male")
                city = q.get("city", "서울") or "서울"
                birth2 = datetime.strptime(q.get("birth2", ""), "%Y-%m-%d").date()
                bt2 = "모름" if q.get("unknown_time2") else (q.get("birth2_time", "12:00") or "12:00")
                hh2, mm2 = _parse_hm(bt2)
                sex2 = q.get("sex2", "female")
                city2 = q.get("city2", "서울") or "서울"
            except ValueError:
                self.send_error(400, "입력 형식 오류")
                return
            r = compatibility(birth, hh, mm, sex, city,
                              birth2, hh2, mm2, sex2, city2)
            _text, md = build_match_report(birth, hh, mm, sex, city,
                                           birth2, hh2, mm2, sex2, city2, r)
            token = secrets.token_hex(8)
            page, summary = render_match_page(r, token)
            _CONTEXTS[token] = {"md": md, "summary": summary,
                                "target": date.today().isoformat(), "created": time.time()}
            self._send(page.encode("utf-8"), "text/html; charset=utf-8")
        elif self.path == "/pick":
            from .taekil import pick_dates
            from .cli import build_pick_report, _parse_hm
            try:
                birth = datetime.strptime(q.get("birth", ""), "%Y-%m-%d").date()
                bt = "모름" if q.get("unknown_time") else (q.get("birth_time", "12:00") or "12:00")
                hh, mm = _parse_hm(bt)
                sex = q.get("sex", "male")
                city = q.get("city", "서울") or "서울"
                start = datetime.strptime(q.get("from_date", ""), "%Y-%m-%d").date()
                end = datetime.strptime(q.get("to_date", ""), "%Y-%m-%d").date()
                domain = q.get("domain", "total") or "total"
                if domain not in ("total", "love", "career", "money"):
                    domain = "total"
            except ValueError:
                self.send_error(400, "입력 형식 오류")
                return
            try:
                r = pick_dates(birth, hh, mm, sex, city, start, end, domain)
            except ValueError as e:
                self.send_error(400, str(e))
                return
            _text, md = build_pick_report(birth, hh, mm, sex, city,
                                          start, end, domain, 5, r)
            token = secrets.token_hex(8)
            page, summary = render_pick_page(r, token)
            _CONTEXTS[token] = {"md": md, "summary": summary,
                                "target": start.isoformat(), "created": time.time()}
            self._send(page.encode("utf-8"), "text/html; charset=utf-8")
        elif self.path == "/api/report":
            from .cli import _parse_hm
            try:
                birth = datetime.strptime(q.get("birth", ""), "%Y-%m-%d").date()
                bt = "모름" if q.get("unknown_time") else (q.get("birth_time", "12:00") or "12:00")
                hh, mm = _parse_hm(bt)
                sex = q.get("sex", "male")
                city = q.get("city", "서울") or "서울"
            except ValueError:
                self.send_error(400, "입력 형식 오류")
                return
            target = date.today() + (timedelta(days=1) if q.get("tomorrow") else timedelta(0))
            try:
                data = api_report_data(birth, hh, mm, sex, city, target)
            except Exception:
                self.send_error(500, "계산 오류")
                return
            token = secrets.token_hex(8)
            _CONTEXTS[token] = {"md": data["md"], "summary": data["summary"],
                                "target": target.isoformat(), "created": time.time()}
            body = json.dumps({"token": token, "data": data},
                              ensure_ascii=False).encode("utf-8")
            self._send(body, "application/json; charset=utf-8")
        elif self.path == "/api/match":
            from .matchmaking import compatibility
            from .cli import _parse_hm
            try:
                birth = datetime.strptime(q.get("birth", ""), "%Y-%m-%d").date()
                hh, mm = _parse_hm("모름" if q.get("unknown_time") else (q.get("birth_time", "12:00") or "12:00"))
                sex = q.get("sex", "male")
                city = q.get("city", "서울") or "서울"
                birth2 = datetime.strptime(q.get("birth2", ""), "%Y-%m-%d").date()
                hh2, mm2 = _parse_hm("모름" if q.get("unknown_time2") else (q.get("birth2_time", "12:00") or "12:00"))
                sex2 = q.get("sex2", "female")
                city2 = q.get("city2", "서울") or "서울"
            except ValueError:
                self.send_error(400, "입력 형식 오류")
                return
            r = compatibility(birth, hh, mm, sex, city,
                              birth2, hh2, mm2, sex2, city2)
            from .cli import build_match_report
            _text, md = build_match_report(birth, hh, mm, sex, city,
                                           birth2, hh2, mm2, sex2, city2, r)
            token = secrets.token_hex(8)
            page, summary = render_match_page(r, token)
            _CONTEXTS[token] = {"md": md, "summary": summary,
                                "target": date.today().isoformat(), "created": time.time()}
            body = json.dumps({"token": token, "data": api_match_data(r)},
                              ensure_ascii=False).encode("utf-8")
            self._send(body, "application/json; charset=utf-8")
        elif self.path == "/api/pick":
            from .taekil import pick_dates
            from .cli import build_pick_report, _parse_hm
            try:
                birth = datetime.strptime(q.get("birth", ""), "%Y-%m-%d").date()
                hh, mm = _parse_hm("모름" if q.get("unknown_time") else (q.get("birth_time", "12:00") or "12:00"))
                sex = q.get("sex", "male")
                city = q.get("city", "서울") or "서울"
                start = datetime.strptime(q.get("from_date", ""), "%Y-%m-%d").date()
                end = datetime.strptime(q.get("to_date", ""), "%Y-%m-%d").date()
                domain = q.get("domain", "total") or "total"
                if domain not in ("total", "love", "career", "money"):
                    domain = "total"
            except ValueError:
                self.send_error(400, "입력 형식 오류")
                return
            try:
                r = pick_dates(birth, hh, mm, sex, city, start, end, domain)
            except ValueError as e:
                self.send_error(400, str(e))
                return
            _text, md = build_pick_report(birth, hh, mm, sex, city,
                                          start, end, domain, 5, r)
            token = secrets.token_hex(8)
            page, summary = render_pick_page(r, token)
            _CONTEXTS[token] = {"md": md, "summary": summary,
                                "target": start.isoformat(), "created": time.time()}
            body = json.dumps({"token": token, "data": api_pick_data(r)},
                              ensure_ascii=False).encode("utf-8")
            self._send(body, "application/json; charset=utf-8")
        elif self.path == "/download":
            ctx = _CONTEXTS.get(q.get("token", ""))
            if not ctx:
                self.send_error(404, "만료된 리포트입니다. 다시 조회해 주세요.")
                return
            body = ctx["md"].encode("utf-8")
            self._send(body, "text/markdown; charset=utf-8",
                       f"attachment; filename=report_{ctx['target'].replace('-', '')}.md")
        elif self.path == "/api/chat":
            ctx = _CONTEXTS.get(q.get("token", ""), {})
            summary = ctx.get("summary", "리포트 컨텍스트 없음. 일반적인 운세 상담으로 답할 것.")
            message = str(q.get("message", ""))[:1000]
            history = [h for h in q.get("history", []) if isinstance(h, dict)][:10]
            endpoint = str(q.get("endpoint", "") or "").strip()
            api_key = str(q.get("api_key", "") or "")
            model = str(q.get("model", "") or "gpt-4o-mini")
            if endpoint and api_key:
                try:
                    reply = llm_chat(endpoint, api_key, model, summary, history)
                    mode = "llm"
                except RuntimeError as e:
                    reply = (f"{e}\n\n대신 로컬 에이전트가 답할게요: "
                             + local_agent_reply(message, summary))
                    mode = "local-fallback"
            else:
                reply = local_agent_reply(message, summary)
                mode = "local"
            self._send(json.dumps({"reply": reply, "mode": mode},
                                  ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")
        else:
            self.send_error(404)


def serve(port: int = 8765):
    print(DISCLAIMER)
    print(f"홈페이지: http://localhost:{port} (종료: Ctrl+C)")
    try:
        webbrowser.open(f"http://localhost:{port}")
    except Exception:
        pass
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.daemon_threads = True
    server.serve_forever()
