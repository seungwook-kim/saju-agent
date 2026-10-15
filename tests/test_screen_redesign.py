"""2026-10 새 디자인 적용, 화면 쪽 시험.

- 글꼴은 이 앱이 직접 준다 (판 번호 붙은 파일은 한 해 캐시, 화면 파일은 ETag 로 304)
- 길일: 화면이 그리는 점수 = 서버가 준 날별 score (옛 응답엔 평균으로)
- 탭 네 묶음, 사실표 새 칸(today.term·today.todo)이 없어도 화면이 깨지지 않게 그 줄만 숨긴다
- 이모지·손글씨 영문·원형 게이지·용어 팝업은 없다
"""
import json
import pathlib
import re
import shutil
import subprocess
import threading
import urllib.request
from datetime import date
from http.server import ThreadingHTTPServer

import pytest

from love_fortune import web

JS = (web.STATIC_DIR / "app.js").read_text(encoding="utf-8")
CSS = (web.STATIC_DIR / "app.css").read_text(encoding="utf-8")
HTML = (web.STATIC_DIR / "app.html").read_text(encoding="utf-8")
VIZ = (web.STATIC_DIR / "viz.js").read_text(encoding="utf-8")


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setenv("SAJU_AI", "0")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), b""


def test_fonts_served_with_long_cache(server):
    for name in web.FONT_FILES:
        code, h, body = _get(server + "/static/" + name)
        assert code == 200 and body, name
        assert h["Cache-Control"] == "public, max-age=31536000, immutable", name
        assert h["Content-Type"] == ("text/css; charset=utf-8" if name.endswith(".css") else "font/woff2")
    code, _, _ = _get(server + "/static/fonts/../web.py")
    assert code == 404


def test_static_etag_304(server):
    code, h, body = _get(server + "/static/app.js")
    assert code == 200 and h["Cache-Control"] == "no-cache" and h.get("ETag")
    code, h2, body2 = _get(server + "/static/app.js", {"If-None-Match": h["ETag"]})
    assert code == 304 and body2 == b"" and h2["ETag"] == h["ETag"]


def test_pick_rows_carry_score():
    r = {"start": "2026-10-15", "end": "2026-10-16", "domain": "total", "story": ["s"],
         "rows": [{"rank": 1, "label": "10/15(목)", "ganzhi": "임술", "love": 70, "career": 70, "money": 70,
                   "god": "식신", "score": 77}]}
    assert web.api_pick_data(r)["rows"][0]["score"] == 77


@pytest.mark.skipif(not shutil.which("node"), reason="node 없음")
def test_pick_view_uses_server_score():
    fn = re.search(r"function pickVal\(r,key\)\{.*?\}\n", JS).group(0)
    src = fn + """
const a={love:70,career:72,money:74,score:77},b={love:70,career:72,money:74};
console.log(JSON.stringify([pickVal(a,null),pickVal(b,null),pickVal(b,'love'),pickVal(a,'love')]));"""
    out = json.loads(subprocess.run(["node", "-e", src], capture_output=True, text=True, encoding="utf-8").stdout)
    assert out == [77, 72, 70, 77]                # 서버 점수가 있으면 그 값, 없으면 예전 식


def test_story_and_rows_share_pick_score(server):
    q = {"birth": "1990-05-05", "birth_time": "14:30", "sex": "female", "city": "서울",
         "from_date": "2026-10-15", "to_date": "2026-11-14", "domain": "total"}
    req = urllib.request.Request(server + "/api/pick", data=json.dumps(q).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read().decode("utf-8"))["data"]
    top = min(d["rows"], key=lambda x: x["rank"])
    assert top["score"] is not None and f"{top['score']}점" in d["story"][0]


@pytest.mark.skipif(not shutil.which("node"), reason="node 없음")
def test_term_and_todo_lines_hide_when_missing():
    # 사실표 새 칸이 없거나 비어 있어도 화면 함수가 깨지지 않고 그 줄만 빠진다
    pick = lambda name: re.search(r"function " + name + r"\(.*?\n\}\n", JS, re.S).group(0)
    src = ("const esc=s=>String(s==null?'':s);const DOM_WORD={love:'연애',career:'직장',money:'금전'};const WEEK=['일','월','화','수','목','금','토'];"
           + pick("mdDay") + pick("termText") + pick("todoList") + """
console.log(JSON.stringify([termText(null,'2026-10-15'),termText({name:'한로',date:'2026-10-08'},'2026-10-15'),
  termText({name:'한로',date:'2026-10-15'},'2026-10-15'),todoList('','',''),todoList(undefined,undefined,undefined),
  todoList('저축 자동이체 점검하기','money','메신저 장문 논쟁')]));""")
    out = json.loads(subprocess.run(["node", "-e", src], capture_output=True, text=True, encoding="utf-8").stdout)
    assert out[:5] == ["", "한로 지나", "한로 들어옴", "", ""]
    assert "해 볼 것" in out[5] and "금전" in out[5] and "조심할 것" in out[5] and "메신저 장문 논쟁" in out[5]


def test_groups_keep_every_tab():
    # 2026-10-15: 오늘 묶음에 학업, 오늘 옆에 내일 묶음 (다섯 묶음, 탭 17개)
    m = re.search(r"const GROUPS=(\[.*?\]);\n", JS, re.S).group(1)
    tabs = re.findall(r"'([a-z_]+)'", m)
    order = re.findall(r"'([a-z_]+)'", re.search(r"const TAB_ORDER=(\[.*?\]);", JS, re.S).group(1))
    assert sorted(tabs) == sorted(order) and len(order) == 17
    assert [g for g in ("오늘", "내일", "흐름", "둘이서", "고르기") if "'" + g + "'" in m] == ["오늘", "내일", "흐름", "둘이서", "고르기"]
    for t in ("study", "tomorrow", "tomorrow_love", "tomorrow_career", "tomorrow_money", "tomorrow_study"):
        assert t in order


@pytest.mark.skipif(not shutil.which("node"), reason="node 없음")
def test_study_and_tomorrow_hidden_without_new_facts():
    # 옛 공유 링크처럼 사실표에 학업·내일 칸이 없으면 그 탭과 내일 묶음은 숨기고, 있으면 보인다
    grab = lambda pat: re.search(pat, JS, re.S).group(0)
    src = ("const TOOLS={past:1,when:1,match:1,pick:1,name:1};const pad=n=>String(n).padStart(2,'0');let S={};"
           + grab(r"const GROUPS=\[.*?\]\];\n") + grab(r"const TAB_DAY=\{.*?\};\n")
           + grab(r"function dayKey\(tab\).*?\nfunction groupOf\(tab\)\{.*?\}\n") + """
const outline={};['today','love','career','money','study','tomorrow','tomorrow_love','tomorrow_career','tomorrow_money','tomorrow_study',
  'newyear','life'].forEach(t=>outline[t]={chapters:[]});
const day=(study)=>({heads:{total:'h'},scores:{total:50,love:50,career:50,money:50},domains:Object.assign({love:{},career:{},money:{}},study?{study:{}}:{})});
const out=[];
S={outline:{today:{},love:{},career:{},money:{},newyear:{},life:{}},facts:{meta:{target:'2026-10-15'},today:day(false)}};
out.push(groupsOK().map(g=>g[0]+':'+g[1].length).join(','));
S={outline,facts:{meta:{target:'2026-10-15'},today:day(true),tomorrow:day(true)}};
out.push(groupsOK().map(g=>g[0]+':'+g[1].length).join(','));
out.push(dayDate('tomorrow'),dayDate('love'));
S.facts.tomorrow.date='2026-10-16';out.push(dayDate('tomorrow_study'));
console.log(JSON.stringify(out));""")
    out = json.loads(subprocess.run(["node", "-e", src], capture_output=True, text=True, encoding="utf-8").stdout)
    assert out[0] == "오늘:4,흐름:3,둘이서:1,고르기:3"            # 학업·내일 없음
    assert out[1] == "오늘:5,내일:5,흐름:3,둘이서:1,고르기:3"
    assert out[2:] == ["2026-10-16", "2026-10-15", "2026-10-16"]


def test_five_groups_fit_phone_width():
    # 위 묶음 줄 다섯 칸이 390 폭(좌우 여백 포함 전체 폭)에 들어가고, 누르는 칸은 높이 48 이상
    assert ".groups{display:grid;grid-template-columns:repeat(4,1fr);height:48px;margin:0 -20px" in CSS   # 칸 수는 화면이 정한다
    assert "$('groups').style.gridTemplateColumns='repeat('+gs.length+',1fr)'" in JS
    assert re.search(r"\.grp\{[^}]*min-height:48px", CSS)
    assert 390 / 5 >= 44


def test_design_rules_in_screen_code():
    blob = HTML + CSS + JS + VIZ
    assert not re.search("[\\U0001F000-\\U0001FFFF\\u2600-\\u27bf\\u2014\\u3040-\\u30ff\\u4e00-\\u9fff]", blob)   # 이모지·em dash·가나·한자 없음
    assert "Segoe Script" not in blob and "class=\"hand\"" not in blob and "CHAPTER" not in JS     # 손글씨 영문·머리표 없음
    assert "linear-gradient(135deg,var(--accent)" not in CSS and "conic-gradient" not in CSS       # 버튼 그라데이션·원형 게이지 없음
    assert 'id="termTip"' not in HTML                                                              # 용어 팝업 없음 (괄호 풀이로)
    assert '<div id="ai-notice" hidden aria-hidden="true">' in HTML                               # AI 안내는 그대로
    assert "나의 네 개의 기둥 펼쳐 보기" in HTML and "내 네 기둥" not in blob
    assert "--accent:#A8322D" in CSS and all(f'body[data-theme="{t}"]' in CSS for t in ("wood", "fire", "earth", "metal", "water"))
    assert "el:v('--el')" in VIZ and "document.fonts.load" in VIZ and "W=1080,H=1920" in VIZ
    assert "Math.random" not in JS + VIZ                                                            # 같은 입력이면 같은 그림


def test_today_facts_feed_screen_contract():
    from love_fortune import facts
    f = facts.build(date(1990, 5, 5), 14, 30, "female", "서울", date(2026, 10, 15))
    t = f["today"]
    assert t["term"] is None or {"name", "date"} <= set(t["term"])
    assert t["todo"] is None or {"do", "avoid"} <= set(t["todo"])
    assert "almanac" in t and t["almanac"][0].startswith("음력 ")      # 날짜 줄의 음력은 여기서 읽는다


def test_chat_limit_is_ten_per_day_everywhere():
    # 2026-10-15 사용자 결정: 상담은 한 사람 하루 10번. 화면 안내 글도 같은 숫자여야 한다
    src = (pathlib.Path(__file__).parent.parent / "love_fortune" / "web.py").read_text(encoding="utf-8")
    assert '"SAJU_CHAT_PER_DAY", "10"' in src
    assert "하루 10번" in HTML and "하루 10번" in JS
    assert "하루 5번" not in HTML + JS


# ---------------------------------------------------------------- 학업·내일 (사실표 새 칸이 있을 때)

@pytest.fixture(scope="module")
def sheet_v3():
    from love_fortune import chapters, facts
    f = facts.build(date(1990, 5, 5), 14, 30, "female", "서울", date(2026, 10, 15))
    return f, chapters.outline()


def test_contract_fields_for_study_and_tomorrow(sheet_v3):
    f, outline = sheet_v3
    for day in ("today", "tomorrow"):
        t = f[day]
        assert t["scores"]["study"] is not None and "study" in t["domains"] and "study" in t["heads"]
    assert f["tomorrow"]["date"] == "2026-10-16"
    for tab in ("study", "tomorrow", "tomorrow_love", "tomorrow_career", "tomorrow_money", "tomorrow_study"):
        assert tab in outline and outline[tab]["chapters"], tab


@pytest.mark.skipif(not shutil.which("node"), reason="node 없음")
def test_screen_draws_study_and_tomorrow(sheet_v3):
    # 계약 칸이 있으면: 다섯 묶음이 다 보이고, 오늘·내일 총운은 붓 획 네 줄, 내일 날짜·공유 카드 문구는 내일 기준
    f, outline = sheet_v3
    grab = lambda pat: re.search(pat, JS, re.S).group(0)
    fn = lambda name: grab(r"function " + name + r"\(.*?\n\}\n")
    src = ("const esc=s=>String(s==null?'':s);const pad=n=>String(n).padStart(2,'0');const TOOLS={past:1,when:1,match:1,pick:1,name:1};"
           + grab(r"const GROUPS=\[.*?\]\];\n") + grab(r"const TAB_DAY=\{.*?\};\n") + grab(r"const DAY_WORD=\{.*?\};\n")
           + grab(r"const DOM_WORD=\{.*?\};\n") + grab(r"const WEEK=\[.*?\];\n")
           + grab(r"function dayKey\(tab\).*?\nfunction groupOf\(tab\)\{.*?\}\n")
           + fn("mdDay") + fn("termText") + fn("dateLine") + """
const S=JSON.parse(require('fs').readFileSync(0,'utf8'));S.tab='today';
const rows=d=>['love','career','money','study'].filter(k=>S.facts[d].scores[k]!=null).map(k=>DOM_WORD[k]);
console.log(JSON.stringify([groupsOK().map(g=>g[0]+':'+g[1].join('|')),rows('today'),rows('tomorrow'),
  dateLine(true,'tomorrow'),dateLine(true,'today'),dayFacts('tomorrow_study').scores.study]));""")
    arg = json.dumps({"facts": f, "outline": outline}, ensure_ascii=False)
    r = subprocess.run(["node", "-e", src], input=arg, capture_output=True, text=True, encoding="utf-8")   # 사실표가 커서 표준 입력으로
    out = json.loads(r.stdout or "null") if r.stdout else None
    assert out, r.stderr
    assert out[0][:2] == ["오늘:today|love|career|money|study", "내일:tomorrow|tomorrow_love|tomorrow_career|tomorrow_money|tomorrow_study"]
    assert [g.split(":")[0] for g in out[0]] == ["오늘", "내일", "흐름", "둘이서", "고르기"]
    assert out[1] == out[2] == ["연애", "직장", "금전", "학업"]
    assert out[3].startswith("10월 16일 금요일") and out[4].startswith("10월 15일 목요일")
    assert out[5] == f["tomorrow"]["scores"]["study"]
    assert "label:W+'의 한 줄'" in JS and "const td=TAB_DAY[tab];" in JS     # 공유 카드는 보는 날 기준


@pytest.mark.skipif(not shutil.which("node"), reason="node 없음")
def test_prefetch_order_today_then_tomorrow():
    # 화면 미리 받기: 지금 연 탭 먼저, 이어서 오늘 묶음 → 내일 묶음 (서버 outline 순서), 동시 3개, 서버에 없는 탭은 건너뛴다
    grab = lambda pat: re.search(pat, JS, re.S).group(0)
    src = ("const pad=n=>String(n).padStart(2,'0');const TOOLS={};"
           + grab(r"const TAB_DAY=\{.*?\};\n") + grab(r"function dayKey\(tab\).*?\nfunction groupOf\(tab\)\{.*?\}\n")
           + grab(r"function bgList\(\)\{.*?\n\}\nfunction pump\(\)\{.*?\n\}\n") + """
const outline={newyear:{chapters:[{id:'x'}]},today:{chapters:[{id:'a'},{id:'b'}]},tomorrow:{chapters:[{id:'a'}]},love:{chapters:[{id:'c'}]},
  tomorrow_love:{chapters:[{id:'c'}]}};
const day={heads:{total:'h'},scores:{},domains:{love:{}}};
const S={ai:true,outline,facts:{meta:{target:'2026-10-15'},today:day,tomorrow:day},token:'t',tab:'love',chapters:{},rules:{},
  queue:[['love','c']],bg:[],running:0,inflight:new Set()};
const calls=[];let peak=0;
function fillChapter(){}
function postJSON(url,q){calls.push(q.tab+'/'+q.chapter);peak=Math.max(peak,S.running);
  return new Promise((ok,no)=>setTimeout(()=>q.tab==='tomorrow_love'?no(new Error('없는 탭')):ok({source:'ai'}),5));}
S.bg=bgList();pump();
setTimeout(()=>console.log(JSON.stringify({calls,peak,left:S.bg.length+S.queue.length,running:S.running})),300);""")
    r = subprocess.run(["node", "-e", src], capture_output=True, text=True, encoding="utf-8")
    out = json.loads(r.stdout)
    assert out["calls"] == ["love/c", "today/a", "today/b", "tomorrow/a", "tomorrow_love/c"]
    assert out["peak"] == 3 and out["left"] == 0 and out["running"] == 0
