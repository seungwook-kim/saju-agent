"""dotenv.py, 프로젝트 폴더의 .env 를 환경변수로 읽는다 (외부 패키지 없이).

- 이미 있는 환경변수는 덮어쓰지 않는다 (Render 등 서버 설정이 우선).
- KEY=VALUE 한 줄에 하나. # 로 시작하는 줄과 빈 줄은 건너뛴다. 값 양끝의 따옴표는 뗀다.
- 값이 빈 줄(KEY=)은 건너뛴다 (기본값을 그대로 쓴다).
- SAJU_DOTENV=0 이면 읽지 않는다 (시험용).
.env 는 저장소에 올리지 않는다 (.gitignore). 적는 법은 .env.example 에 있다.
"""
from __future__ import annotations

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load(path: Path = ENV_FILE) -> int:
    if os.environ.get("SAJU_DOTENV", "1") == "0" or not path.is_file():
        return 0
    n = 0
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip()
        # 값 양끝 따옴표는 뗀다. 한쪽만 붙은 따옴표(예: https://a.com")도 실수로 보고 뗀다
        val = val.strip("\"'").strip()
        if key and val and key not in os.environ:      # 빈 값은 안 쓴다는 뜻이라 건너뛴다
            os.environ[key] = val
            n += 1
    return n
