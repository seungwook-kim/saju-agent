"""Langfuse 기록: 키가 있을 때만, 실제로 보내지 않고 보낼 내용만 본다."""
import base64
import json

import pytest

from love_fortune import ai, langfuse


@pytest.fixture
def sent(monkeypatch):
    got = []

    class R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"{}"

    def fake(req, timeout=0):
        got.append((req.full_url, dict(req.header_items()), json.loads(req.data)))
        return R()

    monkeypatch.setattr("urllib.request.urlopen", fake)
    monkeypatch.setenv("VERCEL", "1")                    # 바로 보내게 (뒤에서 보내면 시험이 기다려야 한다)
    return got


def test_no_keys_no_send(sent, monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    langfuse.log_generation("chapter", "m", "s", "p", "o", 0, 1)
    assert sent == []


def test_generation_payload(sent, monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-1")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-2")
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    langfuse.log_generation("chapter", "qwen/qwen3.7-flash", "sys", "사실표", "{}", 100.0, 102.5,
                            {"prompt_tokens": 2000, "completion_tokens": 950}, 0.0004, meta={"tab": "love"})
    url, headers, body = sent[0]
    assert url == "https://cloud.langfuse.com/api/public/ingestion"
    assert headers["Authorization"] == "Basic " + base64.b64encode(b"pk-lf-1:sk-lf-2").decode()
    kinds = [e["type"] for e in body["batch"]]
    assert kinds == ["trace-create", "generation-create"]
    gen = body["batch"][1]["body"]
    assert gen["model"] == "qwen/qwen3.7-flash" and gen["usageDetails"] == {"input": 2000, "output": 950}
    assert gen["costDetails"] == {"total": 0.0004} and gen["metadata"]["tab"] == "love"
    assert gen["traceId"] == body["batch"][0]["body"]["id"] and gen["input"][1]["content"] == "사실표"


def test_content_off_sends_numbers_only(sent, monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setenv("SAJU_LANGFUSE_CONTENT", "0")
    langfuse.log_generation("chat", "m", "sys", "내 질문", "답", 0, 1, {"prompt_tokens": 5, "completion_tokens": 3})
    raw = json.dumps(sent[0][2], ensure_ascii=False)
    assert "내 질문" not in raw and "답" not in raw.replace("usageDetails", "")


def test_send_failure_does_not_break(monkeypatch, capsys):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-secret-zz")
    monkeypatch.setenv("LANGFUSE_HOST", "http://127.0.0.1:9")
    monkeypatch.setenv("VERCEL", "1")
    langfuse.log_generation("chapter", "m", "s", "p", "o", 0, 1)
    err = capsys.readouterr().err
    assert "Langfuse" in err and "sk-secret-zz" not in err


def test_ai_run_logs_openrouter_usage_and_cost(sent, monkeypatch):
    # OpenRouter 답에 실린 토큰·비용이 그대로 기록된다 (실제 AI 는 부르지 않는다)
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setattr(ai, "BACKEND", "openrouter")
    monkeypatch.setattr(ai, "OPENROUTER_MODEL", "qwen/qwen3.7-flash")
    monkeypatch.setattr(ai, "PER_HOUR", 0)

    class R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"model": "qwen/qwen3.7-flash", "choices": [{"message": {"content": '{"a": 1}'}}],
                               "usage": {"prompt_tokens": 10, "completion_tokens": 4, "cost": 0.00001}}).encode()

    calls = []

    def fake(req, timeout=0):
        calls.append(json.loads(req.data))
        if "ingestion" in req.full_url:
            sent.append(calls[-1])
            return type("X", (), {"__enter__": lambda s: s, "__exit__": lambda s, *a: False, "read": lambda s: b"{}"})()
        return R()

    monkeypatch.setattr("urllib.request.urlopen", fake)
    assert ai.run_json("s", "p", name="chapter", meta={"tab": "love"}) == {"a": 1}
    assert calls[0]["usage"] == {"include": True}
    gen = sent[-1]["batch"][1]["body"]
    assert gen["usageDetails"] == {"input": 10, "output": 4} and gen["costDetails"] == {"total": 0.00001}
    assert gen["name"] == "chapter" and gen["metadata"]["tab"] == "love"


def test_redact_keeps_no_fact_values(sent, monkeypatch):
    # 사실표 값(나이·네 기둥·일간)은 Langfuse 로 가지 않는다. 기준일·성별·연령대·칸 이름만
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    facts = {"meta": {"target": "2026-10-15", "sex": "여성", "age": 27, "age_kr": 29, "hour_known": True},
             "natal.pillars": {"day": "갑자", "month": "을축"}, "natal.ilgan": "갑"}
    prompt = "[사실표]\n" + json.dumps(facts, ensure_ascii=False, indent=1) + "\n\n[탭] 오늘\n[요청] 풀어 줘"
    langfuse.log_generation("chapter", "m", "sys", prompt, "갑자 일주라서 좋아", 0, 1)
    raw = json.dumps(sent[0][2], ensure_ascii=False)
    for leak in ('"age": 27', "age_kr", "을축", '"갑"', "갑자"):
        assert leak not in raw
    assert "20대 후반" in raw and "natal.pillars" in raw and "[요청] 풀어 줘" in raw and "○○ 일주" in raw


def test_redact_chat_drops_summary_and_dates():
    from love_fortune import web
    assert langfuse.PII_MARK == web.USER_PII_NOTE           # 요약을 자르는 표시가 실제 지시문과 같아야 한다
    system, prompt = langfuse.redact("규칙\n" + web.USER_PII_NOTE + "\n대상일 2026-10-15 / 일간 갑(목)",
                                     "<질문>\n나 1998년 3월 5일생이고 980305 야. 10월 17일 시험 붙을까?\n</질문>")
    assert "일간" not in system and "기록하지 않음" in system
    assert "1998년" not in prompt and "980305" not in prompt and "10월 17일 시험" in prompt


def test_age_band():
    assert [langfuse.age_band(a) for a in (5, 20, 24, 27, 41)] == ["10살 아래", "20대 초반", "20대 중반", "20대 후반", "40대 초반"]
    assert langfuse.age_band(None) is None


def test_user_id_and_visit(sent, monkeypatch):
    # 사람 수 세기 (2026-10-16): 익명 해시만 userId 로, 방문은 AI 없이 성별·연령대만
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    langfuse.set_user("u-hash-1")
    try:
        langfuse.log_generation("chapter", "m", "s", "p", "o", 0, 1)
        langfuse.log_visit("report", {"meta": {"target": "2026-10-16", "sex": "여성", "age": 31, "age_kr": 33,
                                               "hour_known": True}, "natal": {"ilgan": "갑"}})
    finally:
        langfuse.set_user(None)
    assert sent[0][2]["batch"][0]["body"]["userId"] == "u-hash-1"
    visit = sent[1][2]["batch"]
    assert [e["type"] for e in visit] == ["trace-create"]
    body = visit[0]["body"]
    assert body["name"] == "visit" and body["userId"] == "u-hash-1"
    assert body["metadata"]["age_band"] == "30대 초반" and body["metadata"]["kind"] == "report"
    raw = json.dumps(visit, ensure_ascii=False)
    assert "age_kr" not in raw and "갑" not in raw and '"age": 31' not in raw


def test_web_sends_hashed_cookie_not_raw(monkeypatch):
    # 서버가 Langfuse 로 보내는 userId 는 쿠키를 서버 비밀과 섞은 해시라 쿠키 값과 다르다
    from love_fortune import web
    assert web._h("lf-user", "abcdefghijklmnop1234") != "abcdefghijklmnop1234"
    assert len(web._h("lf-user", "abcdefghijklmnop1234")) == 24


def test_prefetch_worker_keeps_submitter_user(monkeypatch):
    from love_fortune import prefetch
    langfuse.set_user("u-hash-2")
    try:
        job = prefetch.Job("today", "today", {}, 0)
    finally:
        langfuse.set_user(None)
    assert job.user == "u-hash-2"
