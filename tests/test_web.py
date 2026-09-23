"""tests for web.py, 로컬 채팅 에이전트 + 개인정보 제외 검증."""
from datetime import date

from love_fortune.web import agent_context, local_agent_reply, render_report_page


def _ctx():
    md, text, summary = agent_context(
        date(1995, 2, 28), 12, 0, "male", "부산", date(2026, 9, 20))
    return md, text, summary


def test_agent_context_has_no_pii():
    md, text, summary = _ctx()
    for blob in (md, summary):
        for pii in ("1995-02-28", "부산", "male"):
            assert pii not in blob, f"PII 유출: {pii}"
    assert "1995" not in summary


def test_local_agent_answers_places():
    _, _, summary = _ctx()
    reply = local_agent_reply("오늘 만날 장소 추천해줘", summary)
    assert "장소" in reply
    assert "할 것이다" not in reply  # 단정적 예언 금지


def test_local_agent_answers_tips():
    _, _, summary = _ctx()
    reply = local_agent_reply("대화 팁 알려줘", summary)
    assert "대화" in reply or "팁" in reply


def test_local_agent_sensitive_topic():
    _, _, summary = _ctx()
    reply = local_agent_reply("헤어져야 할까?", summary)
    assert "109" in reply or "전문" in reply  # 도움말 연결


def test_local_agent_daily_lookup():
    _, _, summary = agent_context(
        date(1995, 2, 28), 12, 0, "male", "부산", date(2026, 9, 20))
    assert "일운표" in summary
    r1 = local_agent_reply("내일 운세 어때", summary)
    assert "9월 21일" in r1 and "으뜸" in r1
    r2 = local_agent_reply("모레는 어때", summary)
    assert "9월 22일" in r2
    r3 = local_agent_reply("5일 뒤 운세", summary)
    assert "9월 25일" in r3
    r4 = local_agent_reply("100일 뒤는 어때", summary)
    assert "30일 표 밖에" in r4
    r5 = local_agent_reply("이번 주 좋은 날 알려줘", summary)
    assert "이번 주 좋은 날 top3" in r5


def test_local_agent_full_answers():
    _, _, summary = _ctx()
    r = local_agent_reply("오늘 직장운 어때", summary)
    assert "직장운" in r and "흐름" in r and len(r) > 200
    r = local_agent_reply("금전운 알려줘", summary)
    assert "금전운" in r and len(r) > 200
    r = local_agent_reply("평생 흐름이 궁금해", summary)
    assert "평생" in r and len(r) > 200
    r = local_agent_reply("오늘 연애운 어때", summary)
    assert len(r) > 200 and "이야기" not in r and "근거:" not in r
    for reply in (r, local_agent_reply("오늘 총운 어때", summary)):
        assert "할 것이다" not in reply


def test_local_agent_month_lookup():
    from love_fortune.synthesis import detailed_reading
    ma = detailed_reading(date(1995, 2, 28), 12, 0, "male", "부산", date(2026, 9, 20))
    assert "평균" in ma["month_line"] and "가장 좋은 날" in ma["month_line"]
    assert len(ma["dohwa_lines"]) >= 1  # 없으면 안내문
    _, _, summary = _ctx()
    r = local_agent_reply("이번달 운세 어때", summary)
    assert "이번 달 전체 흐름은요" in r and "평균" in r


def test_api_report_data_clean():
    from love_fortune.web import api_report_data, api_match_data, api_pick_data, app_page
    import json
    d = api_report_data(date(1995, 2, 28), 12, 0, "male", "부산", date(2026, 9, 20))
    blob = json.dumps(d, ensure_ascii=False)
    for pii in ("1995-02-28", "부산", "male"):
        assert pii not in blob, pii
    assert "1995" not in d["summary"]
    for k in ("scores", "stories", "career", "money", "ziwei", "astro",
              "lifetime", "ilun", "luck", "god", "month_line"):
        assert k in d, k
    assert len(d["ilun"]) == 30 and len(d["ziwei"]["palaces"]) == 12
    d2 = api_report_data(date(1995, 2, 28), None, 0, "male", "부산", date(2026, 9, 20))
    assert d2["hour_unknown"] is True and d2["ziwei"] is None
    page = app_page()
    assert "v-fortune" in page and "/api/report" in page
    assert "—" not in page  # 폼 기본값(예시 날짜)은 의도된 플레이스홀더


def test_report_page_renders_without_pii():
    md, text, _ = _ctx()
    page = render_report_page(md, text, "tok123", "2026-09-20")
    assert "tok123" in page
    for pii in ("1995", "부산"):
        assert pii not in page
