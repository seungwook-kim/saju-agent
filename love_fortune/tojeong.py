"""tojeong.py, 토정비결 작괘 (그해 괘 번호 세 자리 = 상괘·중괘·하괘).

작괘법 (만복가 자료실 '토정비결 작괘법'(김중순 『토정비결이란 무엇인가』 참조)의 표를 쓰고,
명문당 '토정비결 보는법'·CHUNUN 블로그의 계산 예시 6개 숫자와 모두 맞는지 대조했다. 2026-09 조사):
- 상괘(1~8) = (그해 세는나이 + 그해 태세수) 를 8로 나눈 나머지 (0 이면 8)
- 중괘(1~6) = (그해 음력 생월의 날수 29·30 + 그해 생월 월건수) 를 6으로 나눈 나머지 (0 이면 6)
- 하괘(1~3) = (음력 생일 날짜 + 그해 음력 생일의 일진수) 를 3으로 나눈 나머지 (0 이면 3)
태세·월건·일진수는 간지마다 천간수 + 지지수. 천간수는 셋 다 같고(갑기 9 을경 8 병신 7 정임 6 무계 5),
지지수는 표마다 다르다. 월건수 지지는 선천수(자오 9 축미 8 인신 7 묘유 6 진술 5 사해 4)와 같다.

다른 사이트 하나(시주를 더하는 '표준세트')는 표·괘사가 전통 판본과 달라 쓰지 않았다.
윤달생은 같은 번호의 평달로 본다. 그해 그달이 29일까지인데 생일이 30일이면 그달 말일의 일진을 쓴다
(원문 규정이 없어 이 앱이 정한 처리이며, 화면에 그렇게 적는다).
"""
from __future__ import annotations

from .lunar import lunar_month_days, lunar_to_solar, solar_to_lunar
from .manseryuk import BRANCHES_KR, STEMS_KR, day_pillar
from .tojeong_data import GUA

STEM_NUM = [9, 8, 7, 6, 5, 9, 8, 7, 6, 5]                              # 갑 을 병 정 무 기 경 신 임 계
TAESE_BRANCH = [11, 13, 10, 10, 13, 9, 9, 13, 12, 12, 13, 11]          # 자 축 인 묘 진 사 오 미 신 유 술 해
WOLGEON_BRANCH = [9, 8, 7, 6, 5, 4, 9, 8, 7, 6, 5, 4]
ILJIN_BRANCH = [9, 11, 8, 8, 11, 7, 7, 11, 10, 10, 11, 9]


def _mod(v: int, n: int) -> int:
    r = v % n
    return r or n


def year_ganzhi(y: int) -> tuple[int, int]:
    return (y - 4) % 10, (y - 4) % 12


def month_ganzhi(y: int, lm: int) -> tuple[int, int]:
    """음력 y 년 lm 월의 월건 (오호둔: 갑기년 병인월, 을경년 무인월, 병신년 경인월, 정임년 임인월, 무계년 갑인월)."""
    ys = (y - 4) % 10
    return (2 * (ys % 5) + 2 + (lm - 1)) % 10, (lm + 1) % 12


def gua(lunar_birth_year: int, lunar_month: int, lunar_day: int, target_year: int) -> dict:
    age = target_year - lunar_birth_year + 1                          # 그해 세는나이
    ys, yb = year_ganzhi(target_year)
    taese = STEM_NUM[ys] + TAESE_BRANCH[yb]
    upper = _mod(age + taese, 8)

    ms, mb = month_ganzhi(target_year, lunar_month)
    wolgeon = STEM_NUM[ms] + WOLGEON_BRANCH[mb]
    days = lunar_month_days(target_year, lunar_month, False)
    middle = _mod(days + wolgeon, 6)

    note = ""
    day = lunar_day
    if lunar_day > days:
        day = days
        note = f"{target_year}년 음력 {lunar_month}월은 {days}일까지라 말일의 일진으로 봤어."
    ds, db = day_pillar(lunar_to_solar(target_year, lunar_month, day, False))
    iljin = STEM_NUM[ds] + ILJIN_BRANCH[db]
    lower = _mod(lunar_day + iljin, 3)

    n = upper * 100 + middle * 10 + lower
    read, tone, mean = GUA[n]
    return {"year": target_year, "gua": n, "read": read, "tone": tone, "mean": mean,
            "steps": {"upper": f"세는나이 {age} + 태세수 {taese}({STEMS_KR[ys]}{BRANCHES_KR[yb]}) → 8로 나눈 나머지 {upper}",
                      "middle": f"그해 생월 날수 {days} + 월건수 {wolgeon}({STEMS_KR[ms]}{BRANCHES_KR[mb]}월) → 6으로 나눈 나머지 {middle}",
                      "lower": f"음력 생일 {lunar_day} + 일진수 {iljin}({STEMS_KR[ds]}{BRANCHES_KR[db]}일) → 3으로 나눈 나머지 {lower}"},
            "note": note}


def for_birth(birth_solar, target_year: int) -> dict:
    ly, lm, ld, _leap = solar_to_lunar(birth_solar.year, birth_solar.month, birth_solar.day)
    out = gua(ly, lm, ld, target_year)
    if _leap:
        out["note"] = (out["note"] + " " if out["note"] else "") + "윤달생이라 같은 번호의 평달로 봤어."
    return out
