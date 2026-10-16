"""visit_stats.py, 하루 방문자·누적 방문자를 보여 준다 (운영 Supabase 에서 읽는다).

실행: uv run --no-project python tools/visit_stats.py [날수, 기본 30]
- 방문자 = 결과(사주 풀이)를 연 IP 수. 같은 IP 는 하루에 한 번, 누적에는 한 번만 센다 (IPv6 는 /64 로 묶는다).
  한 집 와이파이를 같이 쓰는 사람은 한 명으로, 휴대폰처럼 IP 가 바뀌면 다른 사람으로 세진다.
- 2026-10-16 배포부터 센다. 그 전 숫자는 남아 있지 않다.
- 어제보다 오래된 날은 날짜별 숫자(visit_count)로 합쳐 보관한다 (content_store.purge). 이 도구는 둘을 합쳐 보여 준다.
- .env 의 SUPABASE_URL·SUPABASE_SECRET_KEY 로 읽는다. 없으면 로컬 SQLite(이 컴퓨터에서 연 결과)를 보여 준다.
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SAJU_STORE", "supabase")     # 이 도구는 운영 숫자를 보려고 쓴다

from love_fortune import content_store as CS  # noqa: E402  (.env 도 이때 읽는다)
from love_fortune import web  # noqa: E402


def main() -> int:
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    if not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SECRET_KEY")):
        os.environ["SAJU_STORE"] = "sqlite"
    today = date.fromisoformat(web.visit_day())
    since = (today - timedelta(days=days - 1)).isoformat()
    try:
        st = CS.visit_stats(since)
    except Exception as e:  # noqa: BLE001
        code = getattr(e, "code", "")
        hint = " (표가 없으면 Supabase SQL Editor 에서 db/supabase.sql 을 실행해 줘)" if code == 404 else ""
        print(f"읽지 못했어: {type(e).__name__} {code}{hint}")
        return 1
    print(f"저장소: {CS.backend()}  기간: {since} ~ {today}")
    print(f"{'날짜':<12}{'방문자':>6}{'새로 온 사람':>10}")
    for r in st["days"]:
        print(f"{r['day']:<12}{r['visitors']:>6}{r['new']:>10}")
    t = next((r["visitors"] for r in st["days"] if r["day"] == today.isoformat()), 0)
    print(f"\n오늘 방문자 {t}명, 누적 방문자 {st['total']}명")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
