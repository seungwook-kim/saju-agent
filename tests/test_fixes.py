"""2026-09-23 정밀 점검에서 고친 문제들이 다시 생기지 않게 막는 테스트."""
import json
import threading
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

import pytest

from love_fortune import astronomy as A
from love_fortune.lunar import (solar_to_lunar, lunar_to_solar, parse_birth_date,
                                birth_moment, city_info, zone_offset, CITIES, MIN_YEAR, MAX_YEAR)
from love_fortune.calendar_data import ZONES
from love_fortune.manseryuk import (four_pillars, dayun, normalize_sex, time_notes,
                                    year_pillar)
from love_fortune.ziwei import ziwei_chart, ziwei_position, chart_from_lunar, KUI_YUE
from love_fortune.rules import love_score


# ---------------------------------------------------------------- 음력 (한국 기준)


@pytest.mark.parametrize("solar,lunar", [
    ((1997, 2, 8), (1997, 1, 1, False)),     # 한국 설날. 중국은 2월 7일
    ((2027, 2, 7), (2027, 1, 1, False)),     # 한국 설날. 중국은 2월 6일
    ((2026, 10, 10), (2026, 8, 30, False)),  # 예전 표(중국)는 9월 1일로 봤다
    ((2028, 1, 26), (2027, 12, 30, False)),  # 중국 설날이지만 한국은 아직 섣달
    ((1995, 2, 28), (1995, 1, 29, False)),
    ((2023, 3, 22), (2023, 2, 1, True)),     # 윤2월
])
def test_korean_lunar_anchors(solar, lunar):
    assert solar_to_lunar(*solar) == lunar
    assert lunar_to_solar(*lunar) == date(*solar)


def test_lunar_round_trip_every_day():
    d = date(MIN_YEAR, 1, 1)
    while d <= date(MAX_YEAR, 12, 31):
        ly, lm, ld, leap = solar_to_lunar(d.year, d.month, d.day)
        assert lunar_to_solar(ly, lm, ld, leap) == d
        d += timedelta(days=1)


def test_january_1900_does_not_crash():
    assert solar_to_lunar(1900, 1, 15)[0] == 1899


def test_lunar_input_errors_are_explained():
    with pytest.raises(ValueError, match="윤3월이 없어"):
        lunar_to_solar(2023, 3, 1, True)
    with pytest.raises(ValueError, match="일까지야"):
        lunar_to_solar(2026, 2, 30)          # 2026년 음력 2월은 29일까지
    assert parse_birth_date("1995-01-29", "lunar") == date(1995, 2, 28)
    assert parse_birth_date("2023-02-01", "음력", leap=True) == date(2023, 3, 22)
    with pytest.raises(ValueError):
        parse_birth_date("1995-02-28", "solar", leap=True)


# ---------------------------------------------------------------- 절기·사주


def test_mangjong_is_75_degrees():
    t = A.solar_term_moment(2000, 75.0)
    assert (t.month, t.day) == (6, 5)
    # 소만(60도)과 망종(75도) 사이 출생은 여전히 사월(신사)이다
    assert four_pillars(date(2000, 5, 25), 12, 0, "서울")["strings"]["month"] == "신사"
    assert four_pillars(date(2000, 6, 6), 12, 0, "서울")["strings"]["month"] == "임오"


def test_year_boundary_uses_absolute_moment():
    lichun = A.solar_term_moment(2024, 315.0)       # 한국 표준시
    after = lichun + timedelta(minutes=15)
    fp = four_pillars(after.date(), after.hour, after.minute, "서울")
    # 진태양시(약 32분 이른 시각)로 비교하던 예전 방식은 계묘년으로 봤다
    assert fp["strings"]["year"] == "갑진"


def test_korean_summer_time_and_830_offset():
    b = birth_moment(1988, 7, 1, 12, 0, "서울")
    assert b["dst"] and b["offset_h"] == 10 and b["utc"] == datetime(1988, 7, 1, 2, 0)
    b = birth_moment(1958, 1, 10, 12, 0, "서울")
    assert not b["dst"] and b["offset_h"] == 8.5
    b = birth_moment(1958, 7, 10, 12, 0, "서울")
    assert b["dst"] and b["offset_h"] == 9.5
    b = birth_moment(1995, 2, 28, 12, 0, "서울")
    assert not b["dst"] and b["offset_h"] == 9
    notes = time_notes(four_pillars(date(1988, 7, 1), 12, 0, "서울"))
    assert any("서머타임" in x for x in notes)
    notes = time_notes(four_pillars(date(1958, 1, 10), 12, 0, "서울"))
    assert any("UTC+8:30" in x for x in notes)


def test_summer_time_changes_hour_pillar():
    # 1988-07-01 서울 벽시계 01:10 은 실제 표준시로 00:10, 진태양시로는 전날 23시대다
    fp = four_pillars(date(1988, 7, 1), 1, 10, "서울")
    assert fp["pillars"]["hour"][1] == 0          # 자시
    assert fp["night_zi"]


def test_zone_offsets_match_known_values():
    assert zone_offset(datetime(2000, 7, 1, 12), "America/New_York") == (-4 * 3600, True)
    assert zone_offset(datetime(2000, 1, 1, 12), "America/New_York") == (-5 * 3600, False)
    assert zone_offset(datetime(2016, 1, 1, 12), "Asia/Pyongyang")[0] == 8.5 * 3600
    for name, (_lon, _lat, zone) in CITIES.items():
        assert zone in ZONES, name


def test_city_lookup():
    assert city_info("경기도 수원시")["name"] == "수원"
    assert city_info("LA")["name"] == "로스앤젤레스"
    assert city_info("부산광역시")["name"] == "부산"
    miss = city_info("어딘가모를마을")
    assert not miss["matched"]
    assert any("찾지 못해" in x for x in time_notes(four_pillars(date(1995, 2, 28), 12, 0, "어딘가모를마을")))


def test_overseas_birth_uses_local_zone():
    fp = four_pillars(date(1990, 7, 4), 9, 0, "뉴욕")    # 서머타임 중인 뉴욕 오전 9시
    assert fp["dst"] and fp["offset_h"] == -4
    assert any("서머타임" in x for x in time_notes(fp))


# ---------------------------------------------------------------- 천문


@pytest.mark.parametrize("when,ref", [
    ((2000, 1, 1, 0.0), {"moon": 217.297, "jupiter": 25.236, "saturn": 40.407}),
    ((1988, 8, 8, 3.0), {"moon": 86.402, "jupiter": 62.655, "saturn": 266.317}),
    ((2026, 9, 20, 12.0), {"moon": 285.383, "jupiter": 137.641, "saturn": 12.377}),
])
def test_planets_against_pyephem(when, ref):
    dn = A.day_number(*when)
    got = {"moon": A.moon_position(dn)[0],
           "jupiter": A.planet_longitude(dn, "jupiter"),
           "saturn": A.planet_longitude(dn, "saturn")}
    for k, v in ref.items():
        assert abs((got[k] - v + 540) % 360 - 180) < 0.15, k


def test_day_number_exact_in_early_1900():
    assert A.day_number(1900, 1, 1) == (date(1900, 1, 1) - date(1999, 12, 31)).days


# ---------------------------------------------------------------- 자미두수


def test_mu_year_births_no_longer_crash():
    for d in (date(1988, 8, 8), date(1998, 6, 15), date(2008, 3, 3)):
        assert ziwei_chart(d, 10, 0, "female", "서울") is not None
    assert set(KUI_YUE) == set(range(10))
    assert KUI_YUE[4] == (1, 7) and KUI_YUE[5] == (0, 8)


@pytest.mark.parametrize("day,guo,branch", [
    (1, 2, 1),    # 수2국 초하루 → 축
    (3, 2, 2),    # 수2국 초사흘 → 인
    (1, 3, 4),    # 목3국 초하루 → 진
    (1, 6, 9),    # 화6국 초하루 → 유
    (30, 2, 4),   # 수2국 그믐 → 진
])
def test_ziwei_position_table(day, guo, branch):
    assert ziwei_position(day, guo) == branch


def test_daxian_starts_at_guo_age_and_palace_stems():
    z = ziwei_chart(date(1995, 2, 28), 12, 0, "male", "부산")
    ming = next(p for p in z["palaces"] if p["name"] == "명궁")
    assert z["guo"] == 2 and ming["daxian"] == (2, 11)
    ch = chart_from_lunar(1984, 1, 1, False, 0, "male")      # 갑자년
    stems = {p["branch_kr"]: p["stem_kr"] for p in ch["palaces"]}
    assert stems["인"] == "병" and stems["해"] == "을"
    assert stems["자"] == "병" and stems["축"] == "정"         # 해궁 다음으로 이어 센다


def test_liunian_ganzhi_is_consistent_before_seollal():
    z = ziwei_chart(date(1995, 2, 28), 12, 0, "male", "부산", today=date(2026, 1, 15))
    assert z["liunian"]["stem"] + z["liunian"]["branch"] == "을사"   # 음력으로는 아직 2025년
    z = ziwei_chart(date(1995, 2, 28), 12, 0, "male", "부산", today=date(2026, 3, 1))
    assert z["liunian"]["stem"] + z["liunian"]["branch"] == "병오"


def test_target_date_reaches_dayun_and_ziwei():
    a = dayun(date(1995, 2, 28), 12, 0, "male", "부산", today=date(2000, 1, 1))
    b = dayun(date(1995, 2, 28), 12, 0, "male", "부산", today=date(2040, 1, 1))
    assert a["age_now"] < 5 < 44 < b["age_now"]
    z = ziwei_chart(date(1995, 2, 28), 12, 0, "male", "부산", today=date(2040, 6, 1))
    assert z["xusui"] == 2040 - 1995 + 1


def test_empty_ming_palace_borrows_opposite_star():
    from love_fortune.cli import build_report
    z = ziwei_chart(date(1995, 2, 28), 12, 0, "male", "부산")
    assert z["ming_borrowed"] == "천기" and z["ming_main"] == "천기"
    text, md = build_report(date(1995, 2, 28), 12, 0, "male", "부산", date(2026, 9, 20))
    assert "에는 이 앉아" not in text and "에는 이 앉아" not in md
    assert "무주성" in text


# ---------------------------------------------------------------- 성별·연애운


def test_sex_is_validated():
    assert normalize_sex("여") == "female" and normalize_sex("남자") == "male"
    assert normalize_sex("F") == "female"
    with pytest.raises(ValueError):
        normalize_sex("여잔가")
    a = dayun(date(1995, 2, 28), 12, 0, "여", "부산")
    b = dayun(date(1995, 2, 28), 12, 0, "male", "부산")
    assert a["direction"] != b["direction"]


def test_love_score_depends_on_sex():
    # 일간 경(6) 기준 정(3) 날은 정관, 을(1) 날은 정재
    gwan_m, *_ = love_score(6, [0], 3, 5, "x", "male")
    gwan_f, *_ = love_score(6, [0], 3, 5, "x", "female")
    jae_m, *_ = love_score(6, [0], 1, 5, "x", "male")
    jae_f, *_ = love_score(6, [0], 1, 5, "x", "female")
    assert gwan_f > gwan_m and jae_m > jae_f
    _, reasons, _ = love_score(6, [0], 3, 5, "x", "female")
    assert any("관성(여성에게" in r for r in reasons)


# ---------------------------------------------------------------- 웹 서버


@pytest.fixture(scope="module")
def server():
    from http.server import ThreadingHTTPServer
    from love_fortune.web import Handler
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _post(base, path, obj):
    req = urllib.request.Request(base + path, data=json.dumps(obj).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def test_api_report_lunar_input(server):
    code, j = _post(server, "/api/v2/report", {"birth": "1995-01-29", "calendar": "lunar",
                                            "birth_time": "12:00", "sex": "male", "city": "부산"})
    assert code == 200 and j["token"]


def test_api_errors_are_readable(server):
    code, j = _post(server, "/api/v2/report", {"birth": "2023-03-01", "calendar": "lunar",
                                            "leap": "1", "sex": "male"})
    assert code == 400 and "윤3월" in j["error"]
    code, j = _post(server, "/api/v2/report", {"birth": "1995-02-28", "sex": "모름"})
    assert code == 400 and "성별" in j["error"]
    code, j = _post(server, "/api/v2/report", {"birth": "1995-02-28", "birth_time": "25:00"})
    assert code == 400


def test_api_report_mu_year(server):
    code, j = _post(server, "/api/v2/report", {"birth": "1998-06-15", "birth_time": "10:00",
                                            "sex": "female", "city": "서울"})
    assert code == 200


def test_form_error_is_readable(server):
    req = urllib.request.Request(server + "/api/v2/report", data="birth=abc".encode(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with pytest.raises(urllib.error.HTTPError) as ei:
        urllib.request.urlopen(req, timeout=30)
    assert ei.value.code == 400
    assert "YYYY-MM-DD" in ei.value.read().decode("utf-8")


def test_old_pages_are_gone(server):
    for path in ("/classic",):
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(server + path, timeout=30)
        assert e.value.code == 404
    for path in ("/report", "/match", "/pick", "/download", "/api/report"):
        req = urllib.request.Request(server + path, data=b"{}", headers={"Content-Type": "application/json"})
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req, timeout=30)
        assert e.value.code == 404, path


def test_birth_is_picked_not_typed():
    import re
    from love_fortune.web import STATIC_DIR
    h = (STATIC_DIR / "app.html").read_text(encoding="utf-8") + (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    # 생년월일은 글자·날짜 입력칸이 아니라 누르는 버튼 + 숨은 값이다
    assert not re.search(r'name="birth2?" type="(?:text|date)"', h)
    assert h.count('class="datebtn" data-dp=') == 2
    assert 'name="leap" type="checkbox"' not in h


def test_lunar_year_api(server):
    with urllib.request.urlopen(server + "/api/lunar-year?y=2023", timeout=30) as r:
        j = json.loads(r.read().decode("utf-8"))
    assert {"m": 2, "leap": True, "days": 29} in j["months"] and len(j["months"]) == 13
    with pytest.raises(urllib.error.HTTPError):
        urllib.request.urlopen(server + "/api/lunar-year?y=1800", timeout=30)


def test_chat_local_backend(server):
    code, j = _post(server, "/api/v2/report", {"birth": "1995-02-28", "sex": "male"})
    code, j = _post(server, "/api/chat", {"token": j["token"], "message": "오늘 연애운 어때",
                                          "backend": "local"})
    assert code == 200 and j["mode"] == "local" and j["reply"]


def test_llm_chat_sends_current_message(monkeypatch):
    from love_fortune import web
    seen = {}

    class R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "답"}}]}).encode()

    def fake_urlopen(req, timeout=0):
        seen["body"] = json.loads(req.data.decode("utf-8"))
        return R()

    monkeypatch.setattr(web.urllib.request, "urlopen", fake_urlopen)
    web.llm_chat("http://x/v1", "k", "m", "요약", [{"role": "user", "content": "앞 질문"}], "지금 질문")
    assert seen["body"]["messages"][-1] == {"role": "user", "content": "지금 질문"}


def test_llm_endpoint_scheme_is_restricted():
    from love_fortune import web
    with pytest.raises(RuntimeError, match="http"):
        web.llm_chat("file:///C:/Windows", "k", "m", "요약", [], "질문")


def test_cli_chat_command(monkeypatch):
    from love_fortune import web
    seen = {}

    class P:
        returncode = 0
        stdout = json.dumps({"is_error": False, "result": "흐름이 좋아"})

    def fake_run(cmd, **kw):
        seen["cmd"], seen["input"] = cmd, kw["input"]
        seen["system"] = open(cmd[cmd.index("--system-prompt-file") + 1], encoding="utf-8").read()
        return P()

    from love_fortune import ai
    monkeypatch.setattr(ai.shutil, "which", lambda _n: "ai-cli")
    monkeypatch.setattr(ai.subprocess, "run", fake_run)
    out = web.cli_chat("요약문", [{"role": "user", "content": "앞 질문"}], "지금 질문")
    assert out == "흐름이 좋아"
    assert seen["cmd"][seen["cmd"].index("--model") + 1] == ai.AI_MODEL
    assert seen["cmd"][seen["cmd"].index("--tools") + 1] == ""
    assert "지금 질문" in seen["input"] and "앞 질문" in seen["input"]
    assert "요약문" in seen["system"]


def test_contexts_expire_and_are_capped(monkeypatch):
    from love_fortune import web
    web._CONTEXTS.clear()
    monkeypatch.setattr(web, "CONTEXT_MAX", 3)
    toks = [web._remember("md", "s", "2026-01-01") for _ in range(5)]
    assert len(web._CONTEXTS) == 3 and toks[-1] in web._CONTEXTS
    web._CONTEXTS[toks[-1]]["created"] -= web.CONTEXT_TTL + 1
    assert web._context(toks[-1]) is None


def test_server_binds_localhost_by_default():
    import inspect
    from love_fortune.web import serve
    assert inspect.signature(serve).parameters["host"].default == "127.0.0.1"


def test_every_month_branch_gets_a_report():
    # 예전엔 월지가 진~해인 생일(절반)이 격국 계산에서 IndexError 로 죽었다
    from love_fortune.synthesis import detailed_reading
    for m in range(1, 13):
        r = detailed_reading(date(1993, m, 15), 12, 0, "male", "서울", date(2026, 9, 20))
        assert "격" in json.dumps(r, ensure_ascii=False, default=str)


def test_year_pillar_helper_still_accepts_datetime():
    assert year_pillar(datetime(2026, 9, 20, 12)) == (2, 6)   # 병오


def test_zi_mode_next_and_split():
    # 1995-02-28 서울 23:50 은 진태양시 23:05 (균시차 수정 후). lunar-python 정자시(1)·야자시(2) 결과와 같다
    from love_fortune.manseryuk import zi_mode
    with zi_mode("next"):
        fp = four_pillars(date(1995, 2, 28), 23, 50, "서울")
    assert (fp["strings"]["day"], fp["strings"]["hour"]) == ("신묘", "무자")
    with zi_mode("split"):
        fp = four_pillars(date(1995, 2, 28), 23, 50, "서울")
        z = ziwei_chart(date(1995, 2, 28), 23, 50, "male", "서울")
    assert (fp["strings"]["day"], fp["strings"]["hour"]) == ("경인", "무자")
    assert z["lunar"] == (1995, 1, 29, False)          # 야자시면 음력 날짜도 그날 그대로
    assert any("야자시" in x for x in time_notes(fp))
    fp = four_pillars(date(1995, 2, 28), 23, 50, "서울")   # 기본값은 다시 정자시
    assert fp["strings"]["day"] == "신묘"


def test_custom_llm_endpoint_is_off_by_default(server, monkeypatch):
    """요청이 준 주소로 서버가 요청을 보내지 않는다 (공개 서버 SSRF 방지). 켜려면 LOVE_FORTUNE_CUSTOM_LLM=1."""
    from love_fortune import web
    called = []
    monkeypatch.setattr(web, "llm_chat", lambda *a, **k: called.append(a) or "x")
    monkeypatch.setattr(web, "cli_available", lambda: False)      # 실제 AI 명령은 부르지 않는다
    monkeypatch.delenv("LOVE_FORTUNE_CUSTOM_LLM", raising=False)
    code, j = _post(server, "/api/chat", {"message": "안녕", "backend": "openai",
                                          "endpoint": "http://169.254.169.254/latest", "api_key": "k"})
    assert code == 200 and not called and j["mode"] != "llm"


def test_port_env_for_deploy(monkeypatch):
    from love_fortune.cli import parse_args
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setenv("HOST", "0.0.0.0")
    a = parse_args(["form"])
    assert a.port == 10000 and a.host == "0.0.0.0"
