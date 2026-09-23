"""watchdog.py, 5분 스케줄러용 서버 감시 (표준라이브러리만).

동작: /healthz 확인 → 죽어 있으면 포트 점유 프로세스 정리 후 서버 재시작.
      삽화 서버(imagegen, 8766)도 같은 방식으로 살핀다 (imagegen 폴더에 모델이 준비돼 있을 때만).
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
IMAGE_PORT = 8766
IMAGE_DIR = os.path.join(HERE, "imagegen")
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


def healthy(port: int = PORT) -> bool:
    try:
        r = urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=10)
        return r.status == 200
    except Exception:
        return False


def kill_port(port: int = PORT) -> None:
    try:
        proc = subprocess.run(["netstat", "-ano"], capture_output=True, timeout=15)
        out = proc.stdout.decode("utf-8", errors="replace")
        for line in out.splitlines():
            if f":{port}" in line and "LISTENING" in line:
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


def start_image_server() -> None:
    """삽화 서버. 이 컴퓨터 안(127.0.0.1)에서만 열리고, 모델을 미리 올려 둔다(--warm)."""
    try:
        subprocess.Popen(
            [UV, "run", "python", "server.py", "--warm"],
            cwd=IMAGE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
        log("image server start requested")
    except Exception as e:
        log(f"image start failed: {e}")


def main() -> int:
    code = 0
    if healthy():
        log("OK alive")
    else:
        log("DOWN detected, restarting")
        kill_port()
        start_server()
        code = 1
    if os.path.isdir(IMAGE_DIR) and os.environ.get("LOVE_FORTUNE_IMAGES", "1") != "0":
        if healthy(IMAGE_PORT):
            log("OK image alive")
        else:
            log("image DOWN, restarting")
            kill_port(IMAGE_PORT)
            start_image_server()
            code = 1
    return code


if __name__ == "__main__":
    sys.exit(main())
