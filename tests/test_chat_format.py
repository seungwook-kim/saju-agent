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
