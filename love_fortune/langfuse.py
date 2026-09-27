"""langfuse.py, AI 호출 기록을 Langfuse 로 보낸다 (외부 패키지 없이 HTTP 로).

- LANGFUSE_PUBLIC_KEY 와 LANGFUSE_SECRET_KEY 가 있을 때만 보낸다. 없으면 아무것도 안 한다.
- LANGFUSE_HOST: 기본 https://cloud.langfuse.com (미국 리전이면 https://us.cloud.langfuse.com)
- 한 번 부를 때마다 trace 하나와 generation 하나: 무슨 일(챕터·상담), 모델, 입력·출력, 토큰, 비용(달러), 걸린 시간, 오류.
- SAJU_LANGFUSE_CONTENT=0 이면 입력·출력 글은 빼고 숫자(토큰·비용·시간)만 보낸다.
  보내는 입력은 원래 AI 에 보내는 것과 같다: 개인정보를 뺀 사실표, 상담이면 사용자가 친 질문.
- 기록 실패는 앱 동작에 영향을 주지 않는다. 키는 로그에 남기지 않는다.
"""
from __future__ import annotations

import base64
import json
import os
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
    inp = [{"role": "system", "content": system}, {"role": "user", "content": prompt}] if content else None
    out = output if content else None
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
         "body": {"id": trace_id, "name": name, "timestamp": _iso(start), "metadata": meta,
                  "tags": ["saju", name], "input": prompt if content else None, "output": out}},
        {"id": str(uuid.uuid4()), "type": "generation-create", "timestamp": now, "body": gen},
    ]
    if os.environ.get("VERCEL"):
        _post(batch)
    else:
        threading.Thread(target=_post, args=(batch,), daemon=True).start()
