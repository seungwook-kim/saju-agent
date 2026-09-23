"""gen_calendar_data.py, 내장 달력 데이터를 다시 만드는 개발용 도구.

앱은 실행할 때 외부 패키지를 쓰지 않는다. 대신 이 도구로 한 번 뽑아
love_fortune/calendar_data.py 에 박아 둔다. 다시 만들 때만 아래처럼 돌린다.

    uv run --no-project --with korean-lunar-calendar --with tzdata \
        python tools/gen_calendar_data.py

- 음력표: korean-lunar-calendar (한국천문연구원 음력 자료 기반)
- 표준시·서머타임 이력: IANA tz 데이터베이스 (tzdata)
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from korean_lunar_calendar import KoreanLunarCalendar

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "love_fortune", "calendar_data.py")

FIRST_LY, LAST_LY = 1899, 2049
ZONES = [
    "Asia/Seoul", "Asia/Pyongyang", "Asia/Tokyo", "Asia/Shanghai",
    "Asia/Hong_Kong", "Asia/Taipei", "Asia/Singapore", "Asia/Bangkok",
    "Asia/Ho_Chi_Minh", "Asia/Manila", "Asia/Jakarta", "Asia/Dubai",
    "Australia/Sydney", "Australia/Melbourne", "Pacific/Auckland",
    "America/New_York", "America/Chicago", "America/Denver",
    "America/Los_Angeles", "Pacific/Honolulu", "America/Toronto",
    "America/Vancouver", "America/Sao_Paulo", "Europe/London",
    "Europe/Paris", "Europe/Berlin", "Europe/Moscow",
]


def lunar_rows() -> dict[int, list[int]]:
    cal = KoreanLunarCalendar()

    def solar_of(ly: int, lm: int, ld: int, leap: bool) -> date | None:
        if not cal.setLunarDate(ly, lm, ld, leap):
            return None
        return date(cal.solarYear, cal.solarMonth, cal.solarDay)

    rows = {}
    for ly in range(FIRST_LY, LAST_LY + 1):
        leap = next((m for m in range(1, 13) if solar_of(ly, m, 1, True)), 0)
        starts = []
        for m in range(1, 13):
            starts.append(solar_of(ly, m, 1, False))
            if m == leap:
                starts.append(solar_of(ly, m, 1, True))
        starts.append(solar_of(ly + 1, 1, 1, False))
        lens = [(b - a).days for a, b in zip(starts, starts[1:])]
        mask, leap_len, i = 0, 0, 0
        for m in range(1, 13):
            mask = (mask << 1) | (1 if lens[i] == 30 else 0)
            i += 1
            if m == leap:
                leap_len = lens[i]
                i += 1
        ny = starts[0]
        assert ny.year == ly
        rows[ly] = [ny.month * 100 + ny.day, leap, mask, leap_len]
    return rows


def zone_rows(name: str) -> list[tuple[int, int, int]]:
    """(적용 시작 UTC 초, UTC 오프셋 초, 서머타임 여부). 1899~2050 구간."""
    tz = ZoneInfo(name)
    out: list[tuple[int, int, int]] = []
    t = datetime(1899, 1, 1, tzinfo=timezone.utc)
    end = datetime(2051, 1, 1, tzinfo=timezone.utc)
    step = timedelta(minutes=30)
    last = None
    while t < end:
        loc = t.astimezone(tz)
        cur = (int(loc.utcoffset().total_seconds()), 1 if loc.dst() else 0)
        if cur != last:
            # 30분 격자로 찾은 경계를 1분 단위로 좁힌다
            lo = t - step if last is not None else t
            while (lo.astimezone(tz).utcoffset().total_seconds(),) != (cur[0],) \
                    or (1 if lo.astimezone(tz).dst() else 0) != cur[1]:
                lo += timedelta(minutes=1)
            out.append((int(lo.timestamp()), cur[0], cur[1]))
            last = cur
        t += step
    return out


def main() -> int:
    rows = lunar_rows()
    zones = {z: zone_rows(z) for z in ZONES}
    L = ['"""calendar_data.py, 자동 생성 파일. 손으로 고치지 말 것.',
         "",
         "tools/gen_calendar_data.py 로 만든다.",
         "- LUNAR: 한국천문연구원 음력 자료 기준 (korean-lunar-calendar)",
         "  음력년: [설날 MMDD, 윤달(0=없음), 평달 대소 마스크(12비트, 1=30일), 윤달 일수]",
         "- ZONES: IANA tz 데이터베이스 기준 표준시·서머타임 이력",
         "  지역: [(적용 시작 UTC 초, UTC 오프셋 초, 서머타임 여부), ...]",
         '"""', "", "LUNAR = {"]
    for ly, r in rows.items():
        L.append(f"    {ly}: {r},")
    L.append("}")
    L.append("")
    L.append("ZONES = {")
    for z, tr in zones.items():
        L.append(f"    {z!r}: [")
        for i in range(0, len(tr), 4):
            L.append("        " + " ".join(f"{t}," for t in tr[i:i + 4]))
        L.append("    ],")
    L.append("}")
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    print(f"wrote {OUT}: lunar {len(rows)} years, zones {len(zones)}, "
          f"transitions {sum(len(v) for v in zones.values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
