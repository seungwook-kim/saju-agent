"""상담 답 읽기 쉽게: 번호 목록·굵은 제목·이스케이프 (node 로 화면 함수를 그대로 돌린다)."""
import json
import re
import shutil
import subprocess

import pytest

from love_fortune import web


def test_prompt_asks_for_short_titled_items():
    p = web.SYSTEM_PROMPT
    assert "1. 짧은 제목: 설명" in p and "줄이지 말고" in p and "첫 줄에 결론" in p and "네 개를" not in p


@pytest.mark.skipif(not shutil.which("node"), reason="node 없음")
def test_fmt_msg_renders_list_and_escapes():
    js = (web.STATIC_DIR / "app.js").read_text(encoding="utf-8")
    m = re.search(r"function fmtMsg\(t\)\{.*?\n\}", js, re.S)
    esc = re.search(r"const esc=.*?;\n|function esc\(.*?\n\}", js, re.S)
    assert m and esc
    src = esc.group(0) + m.group(0) + "\nconsole.log(JSON.stringify(fmtMsg(process.argv[1])));"
    reply = "올해 연애는 반반이야.\n1. 좋은 점: 배우자성이 보여.\n2. 조심할 점: 화기(막힘 신호)가 있어. <b>x</b>"
    out = json.loads(subprocess.run(["node", "-e", src, reply], capture_output=True, text=True, encoding="utf-8").stdout)
    assert out.startswith("<p>올해 연애는 반반이야.</p><ol class=\"msg-ol\">")
    assert "<li><b>좋은 점</b> 배우자성이 보여.</li>" in out
    assert "&lt;b&gt;x&lt;/b&gt;" in out and "<b>x</b>" not in out


@pytest.mark.skipif(not shutil.which("node"), reason="node 없음")
def test_chapter_prose_readable_without_cutting():
    # 챕터 글: 한 문장 한 줄, 괄호 풀이는 옅게, '라벨: 내용' 은 라벨 줄 따로, 번호 줄은 목록. 글자는 하나도 안 줄인다
    js = (web.STATIC_DIR / "app.js").read_text(encoding="utf-8")
    esc = re.search(r"const esc=.*?;\n", js, re.S).group(0)
    fns = re.search(r"function sents\(s\).*?\nfunction prose\(s,L\)\{.*?\n\}", js, re.S).group(0)
    src = esc + fns + "\nconst L=s=>esc(s);console.log(JSON.stringify(prose(process.argv[1],L)));"
    body = ("모든 운에 함께 걸리는 것: 오늘은 기운이 세. 금성(사랑, 즐거움)이 목성과 만나. 대신 돈은 조심해.\n"
            "1. 좋은 점: 관록궁이 밝아.\n2. 조심할 점: 큰 지출은 미뤄.")
    out = json.loads(subprocess.run(["node", "-e", src, body], capture_output=True, text=True, encoding="utf-8").stdout)
    assert out.startswith('<p class="lbl"><b>모든 운에 함께 걸리는 것</b><br>오늘은 기운이 세.</p>')
    assert '<p>금성<span class="gl">(사랑, 즐거움)</span>이 목성과 만나.</p><p>대신 돈은 조심해.</p>' in out
    assert '<ol class="blk-ol"><li><b>좋은 점</b>관록궁이 밝아.</li>' in out
    plain = re.sub(r"<[^>]+>", "", out)
    for piece in ("오늘은 기운이 세.", "금성(사랑, 즐거움)이 목성과 만나.", "대신 돈은 조심해.", "큰 지출은 미뤄."):
        assert piece in plain                                       # 글자는 줄이지 않는다


def test_ground_keeps_numbered_lines_in_chapter_text():
    from love_fortune import chapters
    part = {"a": "관록 칠살 화기"}
    body = {"headline": "h", "lead": "", "closing": "",
            "blocks": [{"type": "text", "title": "t", "body": "요점이야.\n1. 일: 칠살이라 밀어붙여.\n2. 돈: 화기라 조심해."}]}
    out = chapters.ground(body, part)
    assert out["blocks"][0]["body"] == "요점이야.\n1. 일: 칠살이라 밀어붙여.\n2. 돈: 화기라 조심해."


def test_soft_font_loaded_with_fallbacks():
    # 글꼴은 외부 서버가 아니라 이 앱이 직접 준다 (Gowun Batang 700·Gowun Dodum 400 부분 글꼴, OFL). 못 받으면 기기 글꼴로
    css = (web.STATIC_DIR / "app.css").read_text(encoding="utf-8")
    html = (web.STATIC_DIR / "app.html").read_text(encoding="utf-8")
    fonts = (web.STATIC_DIR / "fonts" / "fonts-v1.css").read_text(encoding="utf-8")
    assert "pstatic.net" not in css + html and "fonts.googleapis" not in css + html
    assert '<link rel="stylesheet" href="/static/fonts/fonts-v1.css">' in html
    assert "--bat:'SajuBatang'" in css and "--dod:'SajuDodum','Apple SD Gothic Neo','Malgun Gothic'" in css
    for fam, w in (("SajuBatang", 700), ("SajuDodum", 400)):
        assert fonts.count(f"font-family:'{fam}';font-weight:{w}") == 2       # ks + 나머지 한글
    for name in web.FONT_FILES:
        assert (web.STATIC_DIR / name).exists(), name
    assert "SIL Open Font License" in fonts


def test_sticky_header_and_hanja_in_picker():
    html = (web.STATIC_DIR / "app.html").read_text(encoding="utf-8")
    css = (web.STATIC_DIR / "app.css").read_text(encoding="utf-8")
    js = (web.STATIC_DIR / "app.js").read_text(encoding="utf-8")
    a, b = html.index('<div class="rhead" id="rhead">'), html.index('<div id="page"></div>')
    assert 'class="topbar"' in html[a:b] and 'class="tabbar"' in html[a:b]       # 상단과 탭 줄이 한 덩어리
    assert ".rhead{position:sticky;top:calc(-1 * var(--top-h,48px))" in css      # 탭 줄은 붙어 있고 맨 위 줄만 스크롤로 사라진다
    assert "String.fromCodePoint(x.cp)" in js                                    # 한자는 코드포인트로 그린다
    assert not re.search("[\u4e00-\u9fff]", js)                                  # 코드에 한자 글자는 없다
