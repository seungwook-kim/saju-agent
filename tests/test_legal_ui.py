"""법률 검토 후 화면 문구: 꼬리말 팝업, AI 없이 보기, 지우기 버튼, AI 안내."""
import re

from love_fortune import guard, web

H = (web.STATIC_DIR / "app.html").read_text(encoding="utf-8")
J = (web.STATIC_DIR / "app.js").read_text(encoding="utf-8")
C = (web.STATIC_DIR / "app.css").read_text(encoding="utf-8")
BAD = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]|\u2014")


def test_footer_on_both_views_and_links():
    assert H.count('class="foot"') == 2
    for k in ("privacy", "terms", "licenses"):
        assert f'data-legal="{k}"' in H
    assert H.count("&copy; 2026 종합 사주") == 2
    assert "무단 수집(스크랩)·복제·AI 학습을 금지해" not in H
    assert H.index('id="fb"') < H.index('class="foot"')           # 쪽지 칸이 꼬리말 바로 위


def test_dialog_accessibility():
    assert '<dialog id="legal" aria-labelledby="legalTitle">' in H
    assert 'aria-label="닫기"' in H and "legalClose" in H
    assert "showModal" in J and "e.target===dlg" in J
    assert "#legal::backdrop" in C and "calc(100vw - 32px)" in C


def test_policy_contents():
    for s in ("시행 2026-10-16", "Vercel Inc.", "Supabase Inc.", "Anthropic PBC", "Langfuse", "30일", "6시간", "90일",
              "AI 없이 계산 풀이만 보기", "만 14세 미만", "만 19세 미만", "이 링크 지우기", "/licenses.txt"):
        assert s in H, s
    assert "나무위키" not in H and "namu" not in H.lower()
    assert "@" not in re.search(r'<dialog id="legal".*?</dialog>', H, re.S).group(0)     # 이메일 없음


def test_noai_checkbox_and_requests():
    assert 'name="noai"' in H
    assert "{...q,noai:1}" in J and "{id:m[1],noai:1}" in J
    assert "chatOn:!!j.chat&&!noai" in J and "ai:!!j.ai&&!noai" in J


def test_share_delete_flow():
    assert "saju.sharedel" in J and "/api/v2/share_delete" in J and "지웠어. 이제 이 링크로는 열 수 없어." in J
    assert "j.del" in J and 'id="shDel"' in H
    assert "S.shareId=null" in J


def test_ai_notices():
    assert "AI에게 물어보기" in H and "AI에게 물어보기" in J
    assert "나는 사람이 아니라 생성형 AI 야" in J
    assert "해시로 바꿔 24시간 보관해" in H and "하루 동안 서버 메모리에만" not in H
    assert "링크에는 생년월일·이름·도시가 들어가지 않아" not in H
    assert "IP 주소를 90일 동안 보관했다가 지우고" in H and "익명으로 보내져" not in H
    assert "Anthropic Claude, 미국" in H


def test_rights_notice_scope_everywhere():
    for name in ("app.js", "viz.js", "app.css", "app.html"):
        t = (web.STATIC_DIR / name).read_text(encoding="utf-8")
        assert "사람이 쓴 풀이 문장은 저작권자에게 권리가 있고" in t and "API 응답, 계산 방식" not in t, name
        assert "절대 훔쳐 가지 못한다" in t, name


def test_no_hanja_kana_emdash_in_ui():
    assert "\u2014" not in H and "\u2014" not in C
    dlg = re.search(r'<dialog id="legal".*?</dialog>', H, re.S).group(0)
    assert not BAD.search(dlg)
