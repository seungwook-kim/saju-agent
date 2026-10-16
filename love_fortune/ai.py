"""ai.py, AI 모델 호출 (상담 채팅·챕터 풀이 공용).

세 가지 방식 중 하나를 쓴다 (환경변수 SAJU_AI_BACKEND):
- cli (기본): 이 PC 에 로그인된 구독 AI 를 로컬 CLI 명령으로 부른다.
  도구는 전부 끄고(--tools ""), 대화는 저장하지 않는다(--no-session-persistence).
  시스템 프롬프트는 임시 파일로, 본문은 표준입력으로 넘긴다 (명령줄 길이 제한 회피).
- openrouter: OpenRouter API(https://openrouter.ai/api/v1/chat/completions)로 부른다.
  OPENROUTER_API_KEY 와 SAJU_OPENROUTER_MODEL(예: 제공사/모델 이름)을 넣어야 켜진다.
  2026-10-16 까지 공개 서비스가 쓰던 방식이다 (qwen/qwen3.7-flash).
- anthropic: Claude API(https://api.anthropic.com/v1/messages)로 직접 부른다. ANTHROPIC_API_KEY 가 있어야 켜진다.
  모델은 SAJU_ANTHROPIC_MODEL (기본 claude-haiku-5-5, 2026-10-16 사용자 결정: 같은 사실표 4장 비교에서
  말투·구성·거름망 통과가 Qwen 보다 나아서). 생각(thinking)은 끈다 (켜 두면 길이 상한을 생각으로 다 써서 빈 답이 왔다).
어느 쪽이든 보내는 것은 개인정보를 뺀 계산 결과와 요청뿐이고, 동시에 도는 호출 수를 제한한다.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time

BACKEND = os.environ.get("SAJU_AI_BACKEND", "cli").strip().lower()
AI_CLI = os.environ.get("SAJU_AI_CLI", "claude")          # 실행할 명령 이름 (cli)
OPENROUTER_URL = os.environ.get("SAJU_OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")
OPENROUTER_MODEL = os.environ.get("SAJU_OPENROUTER_MODEL", "").strip()
ANTHROPIC_URL = os.environ.get("SAJU_ANTHROPIC_URL", "https://api.anthropic.com/v1/messages")
ANTHROPIC_MODEL = os.environ.get("SAJU_ANTHROPIC_MODEL", "").strip() or "claude-haiku-5-5"
PAID = BACKEND in ("openrouter", "anthropic")           # 부를 때마다 돈이 나가는 방식
# 챕터 풀이 저장 키에도 들어가서, 모델을 바꾸면 풀이를 새로 만든다
AI_MODEL = (OPENROUTER_MODEL if BACKEND == "openrouter" else ANTHROPIC_MODEL if BACKEND == "anthropic"
            else os.environ.get("SAJU_AI_MODEL", "claude-sonnet-5"))
LABEL = "AI 모델" if PAID else "구독 AI 모델"      # 화면에 보이는 이름
AI_TIMEOUT = 180
PARALLEL = max(1, int(os.environ.get("SAJU_AI_PARALLEL", "3")))
_SLOTS = threading.BoundedSemaphore(PARALLEL)


# 한 시간에 실제로 부르는 AI 횟수 상한 (공개 서버에서 요금 폭탄을 막는다). 0 이면 제한 없음.
# OpenRouter(유료)는 기본 600번(2026-10-15 사용자 결정, 전에는 300번), 로컬 구독 CLI 는 기본 제한 없음. 넘으면 부르는 쪽이 계산 풀이로 대신한다.
PER_HOUR = int(os.environ.get("SAJU_AI_PER_HOUR", "600" if PAID else "0"))
_CALLS: list[float] = []
_CALLS_LOCK = threading.Lock()


def _take_budget() -> None:
    if PER_HOUR <= 0:
        return
    from . import content_store                     # Supabase 가 있으면 서버 여러 대의 사용량을 함께 센다
    shared = content_store.ai_budget_take(PER_HOUR)
    if shared is False:
        raise RuntimeError("이번 시간 AI 사용량이 다 찼어")
    if shared is True:
        return
    now = time.time()
    with _CALLS_LOCK:
        while _CALLS and now - _CALLS[0] > 3600:
            _CALLS.pop(0)
        if len(_CALLS) >= PER_HOUR:
            raise RuntimeError("이번 시간 AI 사용량이 다 찼어")
        _CALLS.append(now)


def available() -> bool:
    if BACKEND == "openrouter":
        return bool(os.environ.get("OPENROUTER_API_KEY") and OPENROUTER_MODEL)
    if BACKEND == "anthropic":
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    return shutil.which(AI_CLI) is not None


# 한 번에 받는 답의 길이 상한 (토큰). 챕터 풀이는 평균 950, 가장 긴 것 1,700 정도라 2,000 이면 넉넉하다.
# Claude 는 같은 한국어도 토큰을 더 쓰고 더 길게 써서 3,000 (2026-10-16 비교: 원국 장이 2,000 중 1,931).
# 넘으면 JSON 이 잘려 통째로 못 쓴다. 상한이 없으면 모델이 길게 쓰는 만큼 요금이 나간다 (요금은 실제로 쓴 만큼만).
MAX_TOKENS = int(os.environ.get("SAJU_AI_MAX_TOKENS", "3000" if BACKEND == "anthropic" else "2000"))
# Claude 요금 (달러, 100만 토큰당 입력·출력). Langfuse 비용 기록용. Haiku 5.5 기본, 다른 모델이면 SAJU_ANTHROPIC_PRICE=입력,출력
_PRICE = os.environ.get("SAJU_ANTHROPIC_PRICE", "0.10,0.50")


# 요금 설정 (2026-09-27, 추천 모델 qwen/qwen3.7-flash 기준)
# - 생각(reasoning) 끄기: 생각하는 모델은 생각한 글도 출력 요금으로 나가고, 답 길이 상한을 생각으로 다 써 버려
#   빈 답이 올 수 있다. SAJU_OPENROUTER_REASONING=on 이면 켠다.
# - 같은 모델이면 가장 싼 제공사로 (provider.sort=price). SAJU_OPENROUTER_SORT 를 비우면 OpenRouter 기본 배분.
# - 챕터 풀이는 JSON 모드(response_format)로 받아 깨진 JSON 때문에 다시 부르는 일을 줄인다.
def _openrouter_extra(json_mode: bool) -> dict:
    extra: dict = {}
    if os.environ.get("SAJU_OPENROUTER_REASONING", "off").strip().lower() not in ("on", "1", "true"):
        extra["reasoning"] = {"enabled": False}
    sort = os.environ.get("SAJU_OPENROUTER_SORT", "price").strip()
    if sort:
        extra["provider"] = {"sort": sort}
    if json_mode:
        extra["response_format"] = {"type": "json_object"}
    return extra


def _run_openrouter(system: str, prompt: str, timeout: int, max_tokens: int = MAX_TOKENS,
                    json_mode: bool = False) -> str:
    import urllib.error
    import urllib.request
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key or not OPENROUTER_MODEL:
        raise RuntimeError("OpenRouter 키나 모델 이름이 없어")
    body = json.dumps({"model": OPENROUTER_MODEL, "max_tokens": max_tokens,
                       "messages": [{"role": "system", "content": system},
                                    {"role": "user", "content": prompt}],
                       "usage": {"include": True},        # 답에 토큰·비용(달러)을 같이 받는다 (Langfuse 기록용)
                       **_openrouter_extra(json_mode)}).encode("utf-8")
    req = urllib.request.Request(OPENROUTER_URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "X-Title": os.environ.get("SAJU_APP_NAME", "saju-agent")})
    with _SLOTS:
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"AI 호출 실패 (HTTP {e.code})") from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise RuntimeError(f"AI 연결 실패: {e}") from None
        except json.JSONDecodeError:
            raise RuntimeError("AI 응답을 읽지 못했어") from None
    try:
        out = str(data["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(f"AI 응답 형식 오류: {str(data)[:200]}") from None
    if not out:
        raise RuntimeError("AI 가 빈 답을 보냈어")
    u = data.get("usage") or {}
    _LAST.usage, _LAST.cost, _LAST.model = u, u.get("cost"), data.get("model") or OPENROUTER_MODEL
    return out


def _anthropic_cost(u: dict) -> float | None:
    try:
        pin, pout = (float(x) for x in _PRICE.split(","))
        return (u.get("input_tokens", 0) * pin + u.get("output_tokens", 0) * pout) / 1e6
    except (ValueError, TypeError):
        return None


def _run_anthropic(system: str, prompt: str, timeout: int, max_tokens: int = MAX_TOKENS,
                   json_mode: bool = False) -> str:
    import urllib.error
    import urllib.request
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("Claude API 키가 없어")
    body = json.dumps({"model": ANTHROPIC_MODEL, "max_tokens": max_tokens, "system": system,
                       "messages": [{"role": "user", "content": prompt}],
                       "thinking": {"type": "disabled"}}).encode("utf-8")
    req = urllib.request.Request(ANTHROPIC_URL, data=body, method="POST", headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with _SLOTS:
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"AI 호출 실패 (HTTP {e.code})") from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise RuntimeError(f"AI 연결 실패: {e}") from None
        except json.JSONDecodeError:
            raise RuntimeError("AI 응답을 읽지 못했어") from None
    u = data.get("usage") or {}
    _LAST.usage, _LAST.cost, _LAST.model = u, _anthropic_cost(u), data.get("model") or ANTHROPIC_MODEL
    try:
        out = "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text").strip()
    except (KeyError, TypeError, AttributeError):
        raise RuntimeError(f"AI 응답 형식 오류: {str(data)[:200]}") from None
    if json_mode and data.get("stop_reason") == "max_tokens":
        raise RuntimeError("AI 답이 길이 상한에서 잘렸어")
    if not out:
        raise RuntimeError("AI 가 빈 답을 보냈어")
    return out


_LAST = threading.local()          # 방금 부른 호출의 토큰·비용·모델 (Langfuse 기록용)


def run(system: str, prompt: str, timeout: int = AI_TIMEOUT, max_tokens: int = MAX_TOKENS,
        json_mode: bool = False, name: str = "ai", meta: dict | None = None) -> str:
    """답 문자열. 실패하면 RuntimeError (부르는 쪽이 대신 문장을 쓴다).
    Langfuse 키가 있으면 부를 때마다 기록한다 (name: chapter·chat, meta: 탭·챕터 등)."""
    _take_budget()
    from . import langfuse
    _LAST.usage, _LAST.cost, _LAST.model = None, None, AI_MODEL
    start = time.time()
    try:
        out = _run_backend(system, prompt, timeout, max_tokens, json_mode)
    except RuntimeError as e:
        langfuse.log_generation(name, _LAST.model, system, prompt, None, start, time.time(),
                                _LAST.usage, _LAST.cost, error=str(e), meta=meta)
        raise
    langfuse.log_generation(name, _LAST.model, system, prompt, out, start, time.time(),
                            _LAST.usage, _LAST.cost, meta=meta)
    return out


def _run_backend(system: str, prompt: str, timeout: int, max_tokens: int, json_mode: bool) -> str:
    if BACKEND == "openrouter":
        return _run_openrouter(system, prompt, timeout, max_tokens, json_mode)
    if BACKEND == "anthropic":
        return _run_anthropic(system, prompt, timeout, max_tokens, json_mode)
    exe = shutil.which(AI_CLI)
    if not exe:
        raise RuntimeError("AI 명령을 찾지 못했어")
    fd, sys_path = tempfile.mkstemp(prefix="lf_sys_", suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(system)
        cmd = [exe, "-p", "--model", AI_MODEL, "--output-format", "json",
               "--system-prompt-file", sys_path, "--tools", "",
               "--no-session-persistence", "--strict-mcp-config"]
        with _SLOTS:
            try:
                proc = subprocess.run(
                    cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=timeout, cwd=tempfile.gettempdir(),
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except subprocess.TimeoutExpired:
                raise RuntimeError(f"AI 응답이 {timeout}초 안에 오지 않았어") from None
            except OSError as e:
                raise RuntimeError(f"AI 실행 실패: {e}") from None
    finally:
        try:
            os.remove(sys_path)
        except OSError:
            pass
    if proc.returncode != 0:
        raise RuntimeError(f"AI 호출 실패 (종료코드 {proc.returncode})")
    try:
        env = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError("AI 응답을 읽지 못했어") from None
    if env.get("is_error"):
        raise RuntimeError(f"AI 오류: {str(env.get('result', ''))[:200]}")
    out = str(env.get("result", "")).strip()
    if not out:
        raise RuntimeError("AI 가 빈 답을 보냈어")
    _LAST.usage, _LAST.cost = env.get("usage") or {}, env.get("total_cost_usd")
    return out


def run_json(system: str, prompt: str, timeout: int = AI_TIMEOUT, name: str = "ai", meta: dict | None = None) -> dict:
    """JSON 객체로 답을 받는다. 코드 울타리나 앞뒤 설명이 붙어 와도 가장 바깥 {...} 만 읽는다."""
    text = run(system, prompt, timeout, json_mode=True, name=name, meta=meta)
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.S)
    if m:
        text = m.group(1)
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        raise RuntimeError("AI 답이 JSON 이 아니야")
    try:
        obj = json.loads(text[a:b + 1])
    except json.JSONDecodeError as e:
        raise RuntimeError(f"AI 답 JSON 오류: {e}") from None
    if not isinstance(obj, dict):
        raise RuntimeError("AI 답이 객체가 아니야")
    return obj
