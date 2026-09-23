"""gen_solar_terms.py, 24절기 입기 시각을 JPL 천체력으로 계산해 내장하는 개발용 도구.

앱에 들어 있는 간이 태양 공식은 절기 시각이 최대 10분 넘게 어긋났다
(겉보기 황경에 필요한 장동·광행차 보정이 없고 정밀도도 부족했다).
절입 시각 근처에 태어난 사람은 몇 분 차이로 연주·월주가 바뀌므로,
NASA JPL DE421 천체력으로 1899~2051년 절기 시각을 초 단위로 계산해 둔다.

    uv run --no-project --with skyfield python tools/gen_solar_terms.py

결과는 love_fortune/solar_terms_data.py (자동 생성)에 한국 표준시(UTC+9)로 쓴다.
"""
from __future__ import annotations

import os
import sys
from datetime import timedelta

from skyfield import almanac  # noqa: F401  (라이브러리 존재 확인)
from skyfield.api import Loader
from skyfield.framelib import ecliptic_frame
from skyfield.searchlib import find_discrete

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "love_fortune", "solar_terms_data.py")
CACHE = os.path.join(HERE, ".skyfield")
FIRST, LAST = 1899, 2051


def main() -> int:
    load = Loader(CACHE)
    ts = load.timescale()
    eph = load("de421.bsp")          # 1899-07 ~ 2053-10
    earth, sun = eph["earth"], eph["sun"]

    def term_index(t):
        # 겉보기 황경(그날의 황도 기준, 장동·광행차 포함)을 15도 칸 번호로
        lat, lon, _ = earth.at(t).observe(sun).apparent().frame_latlon(ecliptic_frame)
        return (lon.degrees // 15).astype(int) % 24

    term_index.step_days = 7
    t0 = ts.utc(FIRST, 7, 30)        # 천체력 시작 직후부터
    t1 = ts.utc(LAST + 1, 1, 1)
    times, idx = find_discrete(t0, t1, term_index)
    rows: dict[int, list[tuple[int, str]]] = {}
    for t, i in zip(times, idx):
        kst = (t.utc_datetime() + timedelta(hours=9)).replace(tzinfo=None, microsecond=0)
        lon = int(i) * 15
        rows.setdefault(kst.year, []).append((lon, kst.strftime("%Y-%m-%dT%H:%M:%S")))
    L = ['"""solar_terms_data.py, 자동 생성 파일. 손으로 고치지 말 것.',
         "",
         "tools/gen_solar_terms.py 로 만든다. NASA JPL DE421 천체력, 태양 겉보기 황경 기준.",
         "TERMS[한국표준시 연도] = [(황경, 'YYYY-MM-DDTHH:MM:SS' 한국 표준시), ...]",
         '"""', "", "TERMS = {"]
    for y in sorted(rows):
        L.append(f"    {y}: [")
        for lon, s in rows[y]:
            L.append(f"        ({lon}, {s!r}),")
        L.append("    ],")
    L.append("}")
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    print(f"wrote {OUT}: {sum(len(v) for v in rows.values())} terms, {min(rows)}~{max(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
