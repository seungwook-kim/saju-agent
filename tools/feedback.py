"""feedback.py, 익명 쪽지(불편한 점·의견)를 보고, 욕설·도배를 쓴 IP 를 막는다 (운영 Supabase).

실행: uv run --no-project python tools/feedback.py            최근 쪽지 30통
      uv run --no-project python tools/feedback.py 100        최근 100통
      uv run --no-project python tools/feedback.py block 12 욕설   12번 쪽지를 쓴 IP 를 막는다 (메모는 선택)
      uv run --no-project python tools/feedback.py unblock 12      다시 풀어 준다
- 막힌 IP 는 쪽지를 못 보낸다 ("이 주소에서는 쪽지를 보낼 수 없어"). 사주 보기·상담은 그대로 된다.
- IPv6 는 /64 로 묶어 막는다 (한 폰이 주소를 바꿔 가며 써서).
- 쪽지의 IP 는 90일이 지나면 비워지고(목록에 "(90일 지나 지움)"), 365일이 지나면 쪽지가 지워진다. 차단은 IP 해시로만 하고 차단 표에는 IP 를 두지 않는다.
- .env 의 SUPABASE_URL·SUPABASE_SECRET_KEY 로 읽는다. 없으면 로컬 SQLite.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SAJU_STORE", "supabase")     # 이 도구는 운영 쪽지를 보려고 쓴다

from love_fortune import content_store as CS  # noqa: E402  (.env 도 이때 읽는다)

KST = timezone(timedelta(hours=9))


def main(argv: list[str]) -> int:
    if not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SECRET_KEY")):
        os.environ["SAJU_STORE"] = "sqlite"
    if argv and argv[0] in ("block", "unblock"):
        if len(argv) < 2 or not argv[1].isdigit():
            print("쪽지 번호를 적어 줘. 예) block 12 욕설")
            return 1
        rows = {r["id"]: r for r in CS.feedback_list(1000)}
        r = rows.get(int(argv[1]))
        if not r:
            print(f"{argv[1]}번 쪽지가 없어 (최근 1000통 안에서 찾았어).")
            return 1
        on = argv[0] == "block"
        CS.feedback_block(r["k"], "", " ".join(argv[2:]), on=on)      # 해시(k)만으로 막는다. 차단 표에는 IP 를 두지 않는다
        print(f"{r['ip'] or '(90일 지나 지움)'} {'막음' if on else '풀어 줌'} ({argv[1]}번 쪽지)")
        return 0
    limit = int(argv[0]) if argv and argv[0].isdigit() else 30
    rows = CS.feedback_list(limit)
    if not rows:
        print("받은 쪽지가 없어.")
        return 0
    print(f"저장소: {CS.backend()}  최근 {len(rows)}통 (번호로 막기: block <번호>)")
    for r in rows:
        when = datetime.fromtimestamp(r["ts"], KST).strftime("%m-%d %H:%M")
        mark = " [막힘]" if r["blocked"] else ""
        print(f"\n#{r['id']}  {when}  {r['ip'] or '(90일 지나 지움)'}{mark}\n  " + r["body"].replace("\n", "\n  "))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except OSError as e:                              # urllib 오류도 OSError
        code = getattr(e, "code", "")
        hint = " (표가 없으면 Supabase SQL Editor 에서 db/supabase.sql 을 실행해 줘)" if code == 404 else ""
        print(f"읽지 못했어: {type(e).__name__} {code}{hint}")
        raise SystemExit(1)
