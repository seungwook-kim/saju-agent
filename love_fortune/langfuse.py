"""langfuse.py, AI 호출 기록을 Langfuse 로 보낸다 (외부 패키지 없이 HTTP 로).

- LANGFUSE_PUBLIC_KEY 와 LANGFUSE_SECRET_KEY 가 있을 때만 보낸다. 없으면 아무것도 안 한다.
- LANGFUSE_HOST: 기본 https://cloud.langfuse.com (미국 리전이면 https://us.cloud.langfuse.com)
- 한 번 부를 때마다 trace 하나와 generation 하나: 무슨 일(챕터·상담), 모델, 입력·출력, 토큰, 비용(달러), 걸린 시간, 오류.
- SAJU_LANGFUSE_CONTENT=0 이면 입력·출력 글은 빼고 숫자(토큰·비용·시간)만 보낸다.
- 입력은 AI 에 보낸 그대로가 아니라 가린 것을 보낸다 (redact). 사실표 값은 여러 칸을 맞춰 보면
  생년월일이 되살아나서(나이·네 기둥·일간·별자리), 기준일·성별·연령대·시간 앎과 칸 이름만 남긴다.
  상담은 리포트 요약을 빼고, 질문의 연도 붙은 날짜와 답의 '○○ 일주' 같은 기둥 이름을 가린다.
- userId: 브라우저 쿠키(cid)를 서버 비밀과 섞은 해시 (web 이 요청마다 set_user). 쿠키 원래 값·IP 는 보내지 않는다.
  사람 수를 세려고 (2026-10-16). 미리 만들기 일꾼은 작업을 넣은 요청의 값을 이어 받는다.
- visit: 결과를 열 때마다 AI 없이 남기는 기록 (저장된 풀이만 다시 본 방문도 세려고). 성별·연령대만 담는다.
- 기록 실패는 앱 동작에 영향을 주지 않는다. 키는 로그에 남기지 않는다.
"""
from __future__ import annotations

import base64
import contextvars
import json
import os
import re
import sys
import threading
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

TIMEOUT = 5


def enabled() -> bool:
    return bool(os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"))


def _iso(t: float) -> str:
    return datetime.fromtimestamp(t, tz=timezone.utc).isoformat().replace("+00:00", "Z")


_USER: contextvars.ContextVar[str | None] = contextvars.ContextVar("langfuse_user", default=None)


def set_user(uid: str | None) -> None:
    """지금 요청(스레드)의 익명 사용자 해시. 서버가 스레드를 다시 써도 요청마다 새로 넣는다."""
    _USER.set(uid)


def current_user() -> str | None:
    return _USER.get()


FACTS_HEAD = "[사실표]\n"
PII_MARK = "아래 컨텍스트에는 개인정보가 포함되어 있지 않다."     # web.USER_PII_NOTE, 이 뒤가 리포트 요약
_GANZHI = "|".join("갑을병정무기경신임계"[i % 10] + "자축인묘진사오미신유술해"[i % 12] for i in range(60))
_PILLAR = re.compile(rf"({_GANZHI})(\s*)(연주|년주|월주|일주|시주)")
_PILLAR_AFTER = re.compile(rf"(연주|년주|월주|일주|시주)([은는이가]?\s*)({_GANZHI})")
_DATE = re.compile(r"(?:19|20)?\d{2}\s*(?:년|[./-])\s*\d{1,2}\s*(?:월|[./-])\s*\d{1,2}\s*일?|(?<!\d)(?:19|20)?\d{6}(?!\d)")


def age_band(age) -> str | None:
    if not isinstance(age, int) or age < 0:
        return None
    if age < 10:
        return "10살 아래"
    part = "초반" if age % 10 < 4 else "중반" if age % 10 < 7 else "후반"
    return f"{age // 10 * 10}대 {part}"


def _mask(text: str | None) -> str | None:
    """사람 글·AI 답에서 생일을 되살릴 수 있는 조각을 가린다: 연도 붙은 날짜, '갑자 일주' 같은 기둥."""
    if not text:
        return text
    text = _DATE.sub("(날짜 가림)", text)
    text = _PILLAR.sub(r"○○\2\3", text)
    return _PILLAR_AFTER.sub(r"\1\2○○", text)


def redact(system: str, prompt: str) -> tuple[str, str]:
    """Langfuse 에 남길 지시문·입력. AI 에 실제로 보내는 글은 바꾸지 않는다."""
    if PII_MARK in system:
        cut = system.index(PII_MARK)
        system = system[:cut] + f"[리포트 요약 {len(system) - cut}자는 기록하지 않음]"
    if prompt.startswith(FACTS_HEAD):
        try:
            facts, end = json.JSONDecoder().raw_decode(prompt, len(FACTS_HEAD))
        except ValueError:
            return system, "[사실표는 기록하지 않음]"
        if isinstance(facts, dict):
            m = facts.get("meta") or {}
            kept = {"meta": {"target": m.get("target"), "sex": m.get("sex"),
                             "age_band": age_band(m.get("age")), "hour_known": m.get("hour_known")},
                    "keys": sorted(k for k in facts if k != "meta"), "note": "사실표 값은 기록하지 않음"}
            return system, FACTS_HEAD + json.dumps(kept, ensure_ascii=False, indent=1) + prompt[end:]
        return system, "[사실표는 기록하지 않음]"
    return system, _mask(prompt)


def _post(batch: list[dict]) -> None:
    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com").strip().rstrip("/")
    auth = base64.b64encode((os.environ["LANGFUSE_PUBLIC_KEY"] + ":" + os.environ["LANGFUSE_SECRET_KEY"]).encode()).decode()
    req = urllib.request.Request(host + "/api/public/ingestion", method="POST",
                                 data=json.dumps({"batch": batch}, ensure_ascii=False).encode("utf-8"),
                                 headers={"Authorization": "Basic " + auth, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            r.read()
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"[Langfuse] 기록 실패: {type(e).__name__} {getattr(e, 'code', '')}".rstrip(), file=sys.stderr)


def log_generation(name: str, model: str, system: str, prompt: str, output: str | None,
                   start: float, end: float, usage: dict | None = None, cost: float | None = None,
                   error: str | None = None, meta: dict | None = None) -> None:
    """AI 한 번 부른 기록. 서버리스(Vercel)는 답을 보낸 뒤 뒤에서 도는 일이 멈출 수 있어 바로 보내고,
    그 밖에는 뒤에서 보내 응답을 늦추지 않는다."""
    if not enabled():
        return
    content = os.environ.get("SAJU_LANGFUSE_CONTENT", "1") != "0"
    trace_id, gen_id = str(uuid.uuid4()), str(uuid.uuid4())
    meta = {**(meta or {}), "backend": os.environ.get("SAJU_AI_BACKEND") or "cli"}
    system, prompt = redact(system, prompt)
    inp = [{"role": "system", "content": system}, {"role": "user", "content": prompt}] if content else None
    out = _mask(output) if content else None
    gen: dict = {"id": gen_id, "traceId": trace_id, "name": name, "model": model,
                 "startTime": _iso(start), "endTime": _iso(end), "input": inp, "output": out, "metadata": meta}
    u = usage or {}
    pin = u.get("prompt_tokens", u.get("input_tokens"))
    pout = u.get("completion_tokens", u.get("output_tokens"))
    if pin is not None or pout is not None:
        gen["usageDetails"] = {k: v for k, v in (("input", pin), ("output", pout)) if isinstance(v, int)}
    if isinstance(cost, (int, float)):
        gen["costDetails"] = {"total": float(cost)}
    if error:
        gen["level"], gen["statusMessage"] = "ERROR", error[:300]
    now = _iso(end)
    batch = [
        {"id": str(uuid.uuid4()), "type": "trace-create", "timestamp": now,
         "body": _with_user({"id": trace_id, "name": name, "timestamp": _iso(start), "metadata": meta,
                             "tags": ["saju", name], "input": prompt if content else None, "output": out})},
        {"id": str(uuid.uuid4()), "type": "generation-create", "timestamp": now, "body": gen},
    ]
    _send(batch)


def _with_user(body: dict) -> dict:
    uid = _USER.get()
    return {**body, "userId": uid} if uid else body


def _send(batch: list[dict]) -> None:
    if os.environ.get("VERCEL"):
        _post(batch)
    else:
        threading.Thread(target=_post, args=(batch,), daemon=True).start()


def log_visit(kind: str, facts: dict) -> None:
    """결과를 연 방문 하나 (AI 없음). 저장된 풀이만 다시 본 방문도 남는다. 성별·연령대·기준일만."""
    if not enabled():
        return
    import time
    m = facts.get("meta") or {}
    now = _iso(time.time())
    meta = {"kind": kind, "target": m.get("target"), "sex": m.get("sex"), "age_band": age_band(m.get("age")),
            "hour_known": m.get("hour_known")}
    _send([{"id": str(uuid.uuid4()), "type": "trace-create", "timestamp": now,
            "body": _with_user({"id": str(uuid.uuid4()), "name": "visit", "timestamp": now,
                                "metadata": meta, "tags": ["saju", "visit"]})}])
