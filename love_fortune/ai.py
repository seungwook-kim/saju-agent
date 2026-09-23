"""ai.py, 구독 AI 모델을 로컬 CLI 명령으로 부른다 (상담 채팅·챕터 풀이 공용).

- 도구는 전부 끄고(--tools ""), 대화는 저장하지 않는다(--no-session-persistence).
- 시스템 프롬프트는 임시 파일로, 본문은 표준입력으로 넘긴다 (명령줄 길이 제한 회피).
- 보내는 것은 개인정보를 뺀 계산 결과와 요청뿐이다.
- 동시에 도는 호출 수를 제한한다 (PC 부담·구독 사용량).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading

AI_CLI = os.environ.get("LOVE_FORTUNE_AI_CLI", "claude")          # 실행할 명령 이름
AI_MODEL = os.environ.get("LOVE_FORTUNE_AI_MODEL", "claude-sonnet-5")
AI_TIMEOUT = 180
_SLOTS = threading.BoundedSemaphore(int(os.environ.get("LOVE_FORTUNE_AI_PARALLEL", "3")))


def available() -> bool:
    return shutil.which(AI_CLI) is not None


def run(system: str, prompt: str, timeout: int = AI_TIMEOUT) -> str:
    """답 문자열. 실패하면 RuntimeError (부르는 쪽이 대신 문장을 쓴다)."""
    exe = shutil.which(AI_CLI)
    if not exe:
        raise RuntimeError("AI 명령을 찾지 못했어요")
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
                raise RuntimeError(f"AI 응답이 {timeout}초 안에 오지 않았어요") from None
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
        raise RuntimeError("AI 응답을 읽지 못했어요") from None
    if env.get("is_error"):
        raise RuntimeError(f"AI 오류: {str(env.get('result', ''))[:200]}")
    out = str(env.get("result", "")).strip()
    if not out:
        raise RuntimeError("AI 가 빈 답을 보냈어요")
    return out


def run_json(system: str, prompt: str, timeout: int = AI_TIMEOUT) -> dict:
    """JSON 객체로 답을 받는다. 코드 울타리나 앞뒤 설명이 붙어 와도 가장 바깥 {...} 만 읽는다."""
    text = run(system, prompt, timeout)
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.S)
    if m:
        text = m.group(1)
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        raise RuntimeError("AI 답이 JSON 이 아니에요")
    try:
        obj = json.loads(text[a:b + 1])
    except json.JSONDecodeError as e:
        raise RuntimeError(f"AI 답 JSON 오류: {e}") from None
    if not isinstance(obj, dict):
        raise RuntimeError("AI 답이 객체가 아니에요")
    return obj
