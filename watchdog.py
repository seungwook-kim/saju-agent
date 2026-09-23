"""watchdog.py, 5분 스케줄러용 서버 감시 (표준라이브러리만).

동작: /healthz 확인 → 죽어 있으면 포트 점유 프로세스 정리 후 서버 재시작.
기록: watchdog.log (10만 바이트 넘으면 자름).
등록: schtasks /create /tn LoveFortuneWatchdog /tr "..." /sc minute /mo 5
"""
from __future__ import annotations

import os
import subprocess
import sys
import urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "watchdog.log")
PORT = 8765
UV = os.path.expandvars(r"%USERPROFILE%\.local\bin\uv.exe")


def log(msg: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n"
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > 100000:
            with open(LOG, encoding="utf-8") as f:
                lines = f.readlines()[-100:]
            with open(LOG, "w", encoding="utf-8") as f:
                f.writelines(lines)
    except OSError:
        pass
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass
    print(line.strip())


def healthy() -> bool:
    try:
        r = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/healthz", timeout=10)
        return r.status == 200
    except Exception:
        return False


def kill_port() -> None:
    try:
        proc = subprocess.run(["netstat", "-ano"], capture_output=True, timeout=15)
        out = proc.stdout.decode("utf-8", errors="replace")
        for line in out.splitlines():
            if f":{PORT}" in line and "LISTENING" in line:
                pid = line.split()[-1]
                subprocess.run(["taskkill", "/F", "/PID", pid],
                               capture_output=True, timeout=15)
                log(f"killed pid {pid}")
    except Exception as e:
        log(f"kill failed: {e}")


def start_server() -> None:
    try:
        subprocess.Popen(
            # 휴대폰 등 같은 네트워크의 기기에서도 보도록 모든 주소로 연다 (사용자 요청)
            [UV, "run", "--python", "3.14", "python", "-m", "love_fortune", "form",
             "--host", "0.0.0.0"],
            cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
        log("server start requested")
    except Exception as e:
        log(f"start failed: {e}")


def main() -> int:
    if healthy():
        log("OK alive")
        return 0
    log("DOWN detected, restarting")
    kill_port()
    start_server()
    return 1


if __name__ == "__main__":
    sys.exit(main())
