"""ai.py, AI 모델 호출 (상담 채팅·챕터 풀이 공용).

두 가지 방식 중 하나를 쓴다 (환경변수 LOVE_FORTUNE_AI_BACKEND):
- cli (기본): 이 PC 에 로그인된 구독 AI 를 로컬 CLI 명령으로 부른다.
  도구는 전부 끄고(--tools ""), 대화는 저장하지 않는다(--no-session-persistence).
  시스템 프롬프트는 임시 파일로, 본문은 표준입력으로 넘긴다 (명령줄 길이 제한 회피).
- openrouter: OpenRouter API(https://openrouter.ai/api/v1/chat/completions)로 부른다.
  OPENROUTER_API_KEY 와 LOVE_FORTUNE_OPENROUTER_MODEL(예: 제공사/모델 이름)을 넣어야 켜진다.
  서비스로 공개할 때 쓰는 방식이다.
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

BACKEND = os.environ.get("LOVE_FORTUNE_AI_BACKEND", "cli").strip().lower()
AI_CLI = os.environ.get("LOVE_FORTUNE_AI_CLI", "claude")          # 실행할 명령 이름 (cli)
OPENROUTER_URL = os.environ.get("LOVE_FORTUNE_OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")
OPENROUTER_MODEL = os.environ.get("LOVE_FORTUNE_OPENROUTER_MODEL", "").strip()
# 챕터 풀이 저장 키에도 들어가서, 모델을 바꾸면 풀이를 새로 만든다
AI_MODEL = (OPENROUTER_MODEL if BACKEND == "openrouter"
            else os.environ.get("LOVE_FORTUNE_AI_MODEL", "claude-sonnet-5"))
LABEL = "AI 모델" if BACKEND == "openrouter" else "구독 AI 모델"      # 화면에 보이는 이름
AI_TIMEOUT = 180
PARALLEL = max(1, int(os.environ.get("LOVE_FORTUNE_AI_PARALLEL", "3")))
_SLOTS = threading.BoundedSemaphore(PARALLEL)


# 한 시간에 실제로 부르는 AI 횟수 상한 (공개 서버에서 요금 폭탄을 막는다). 0 이면 제한 없음.
# OpenRouter(유료)는 기본 300번, 로컬 구독 CLI 는 기본 제한 없음. 넘으면 부르는 쪽이 계산 풀이로 대신한다.
PER_HOUR = int(os.environ.get("LOVE_FORTUNE_AI_PER_HOUR", "300" if BACKEND == "openrouter" else "0"))
_CALLS: list[float] = []
_CALLS_LOCK = threading.Lock()


def _take_budget() -> None:
    if PER_HOUR <= 0:
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
    return shutil.which(AI_CLI) is not None


# 한 번에 받는 답의 길이 상한 (토큰). 챕터 풀이는 평균 950, 가장 긴 것 1,700 정도라 2,000 이면 넉넉하다.
# 상한이 없으면 모델이 길게 쓰는 만큼 요금이 나간다.
MAX_TOKENS = int(os.environ.get("LOVE_FORTUNE_AI_MAX_TOKENS", "2000"))


def _run_openrouter(system: str, prompt: str, timeout: int, max_tokens: int = MAX_TOKENS) -> str:
    import urllib.error
    import urllib.request
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key or not OPENROUTER_MODEL:
        raise RuntimeError("OpenRouter 키나 모델 이름이 없어")
    body = json.dumps({"model": OPENROUTER_MODEL, "max_tokens": max_tokens,
                       "messages": [{"role": "system", "content": system},
                                    {"role": "user", "content": prompt}]}).encode("utf-8")
    req = urllib.request.Request(OPENROUTER_URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "X-Title": os.environ.get("LOVE_FORTUNE_APP_NAME", "love-fortune")})
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
    return out


def run(system: str, prompt: str, timeout: int = AI_TIMEOUT, max_tokens: int = MAX_TOKENS) -> str:
    """답 문자열. 실패하면 RuntimeError (부르는 쪽이 대신 문장을 쓴다)."""
    _take_budget()
    if BACKEND == "openrouter":
        return _run_openrouter(system, prompt, timeout, max_tokens)
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
    return out


def run_json(system: str, prompt: str, timeout: int = AI_TIMEOUT) -> dict:
    """JSON 객체로 답을 받는다. 코드 울타리나 앞뒤 설명이 붙어 와도 가장 바깥 {...} 만 읽는다."""
    text = run(system, prompt, timeout)
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
