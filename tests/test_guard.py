"""스크랩·AI 수집 막기."""
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from love_fortune import guard, web

BROWSER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"


@pytest.fixture
def srv(monkeypatch):
    monkeypatch.setenv("SAJU_BOT_BLOCK", "1")
    s = ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_address[1]}"
    s.shutdown()


def get(url, ua):
    req = urllib.request.Request(url, headers={"User-Agent": ua} if ua is not None else {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8")


def test_is_bot():
    for ua in ("GPTBot/1.1", "ClaudeBot/1.0", "CCBot/2.0", "python-requests/2.32", "curl/8.4", "Scrapy/2.11",
               "Mozilla/5.0 HeadlessChrome/120", "", None, "Bytespider", "PerplexityBot/1.0"):
        assert guard.is_bot(ua), ua
    for ua in (BROWSER, "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile Safari",
               "Mozilla/5.0 (compatible; kakaotalk-scrap/1.0)"):
        assert not guard.is_bot(ua), ua


def test_bots_blocked_browsers_ok(srv):
    code, h, body = get(srv + "/", "GPTBot/1.1")
    assert code == 403 and "절대 훔쳐 가지 못한다" in body
    code, h, body = get(srv + "/static/app.js", "python-requests/2.32")
    assert code == 403
    code, h, body = get(srv + "/", BROWSER)
    assert code == 200 and "noai" in h["X-Robots-Tag"] and h["tdm-reservation"] == "1"
    assert '<div id="ai-notice" hidden aria-hidden="true">' in body and "절대 훔쳐 가지 못한다" in body
    code, _, _ = get(srv + "/healthz", "")                            # 서버 상태 확인은 막지 않는다
    assert code == 200


def test_notice_files_readable_by_crawlers(srv):
    code, _, body = get(srv + "/robots.txt", "GPTBot/1.1")
    assert code == 200 and "Disallow: /" in body
    code, _, body = get(srv + "/llms.txt", "ClaudeBot/1.0")
    assert code == 200 and "절대 훔쳐 가지 못한다" in body
    code, _, body = get(srv + "/.well-known/tdmrep.json", "CCBot/2.0")
    assert code == 200 and '"tdm-reservation": 1' in body


def test_post_from_script_blocked(srv):
    req = urllib.request.Request(srv + "/api/v2/report", data=b"{}", headers={"Content-Type": "application/json"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=10)                      # python-urllib 사용자 에이전트
    assert e.value.code == 403


def test_hidden_notice_in_code_files():
    for name in ("app.js", "viz.js", "app.css"):
        head = (web.STATIC_DIR / name).read_text(encoding="utf-8")[:2000]
        assert "절대 훔쳐 가지 못한다" in head and "must never take or steal" in head, name


def test_notice_scope_is_limited():
    assert "사람이 쓴 풀이 문장은 저작권자에게 권리가 있고, 외부 자료는 각 라이선스를 따른다" in guard.AI_NOTICE_KO
    assert "human-written texts" in guard.AI_NOTICE_EN and "Third-party data follows its own licenses" in guard.AI_NOTICE_EN
    assert "API 응답" not in guard.AI_NOTICE_KO and "calculation methods" not in guard.AI_NOTICE_EN
    assert "절대 훔쳐 가지 못한다" in guard.AI_NOTICE_KO
