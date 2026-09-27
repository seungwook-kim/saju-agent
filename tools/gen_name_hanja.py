"""gen_name_hanja.py, 이름 풀이용 인명용 한자표 만들기 (개발할 때만 돌린다).

입력 (내려받아 tools/.cache/ 에 둔다):
- Unicode Unihan 16.0 (Unihan.zip, https://www.unicode.org/Public/16.0.0/ucd/Unihan.zip, Unicode 라이선스)
  · kRSUnicode: 부수 번호.나머지 획수  · kTotalStrokes: 옥편 획수(필획)
- rutopio/Korean-Name-Hanja-Charset (MIT): data-gov.csv (대법원 인명용 한자 목록), data-naver.csv (훈음)

출력: love_fortune/name_hanja.json
  [{"cp": 코드포인트, "r": 음, "h": 훈음, "w": 원획, "p": 필획}, ...]
  한자를 코드에 두지 않는 규칙이라 글자 대신 코드포인트만 둔다.

원획 계산 (성명학 원획법):
- 강희 부수는 제 모양의 획수로 센다: 원획 = 부수 원래 획수 + 나머지 획수 (kRSUnicode).
  예) 삼수변(물 수, 부수 85)은 4획, 초두머리(부수 140)는 6획, 책받침(162)은 7획, 왼쪽 좌부변(170)은 8획, 오른쪽 우부방(163)은 7획,
  육달월이 고기 육(130)이면 6획, 구슬옥변이 구슬 옥(96)이면 5획. 한국작명교육협회·사주포럼 표와 같다.
- 숫자를 뜻하는 글자는 그 수로 센다: 한 일 1 … 넉 사 4, 다섯 오 5, 여섯 육 6, 일곱 칠 7, 여덟 팔 8, 아홉 구 9, 열 십 10 (한국작명교육협회, 홍정 작명론 대조).
- kRSUnicode 값이 둘이면 획수가 큰 쪽(강희자전 옛 모양)을 쓴다 (예: 벼슬 경 12획).
- 성명학에서 따로 세는 글자: 이룰 성 7획(옛 모양), 풍년 풍 18획(옛 글자와 같게 본다) (인터넷 한국작명연구원 '혼동하기 쉬운 변획수').
검증: 인터넷 한국작명연구원이 꼽은 틀리기 쉬운 글자 33자 + 물 하·넉 사·아홉 구가 모두 맞는다 (tests/test_naming.py).
"""
from __future__ import annotations

import csv
import json
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "tools" / ".cache"
OUT = ROOT / "love_fortune" / "name_hanja.json"

NUMERAL = {0x4E00: 1, 0x4E8C: 2, 0x4E09: 3, 0x56DB: 4, 0x4E94: 5, 0x516D: 6, 0x4E03: 7, 0x516B: 8, 0x4E5D: 9, 0x5341: 10}
SPECIAL = {0x6210: 7, 0x8C4A: 18}
RADICAL_GROUPS = ((6, 1), (29, 2), (60, 3), (94, 4), (117, 5), (146, 6), (166, 7), (175, 8), (186, 9),
                  (194, 10), (200, 11), (204, 12), (208, 13), (210, 14), (211, 15), (213, 16), (214, 17))


def radical_strokes(r: int) -> int:
    """강희 214 부수의 원래 획수 (부수 번호가 획수 순서로 매겨져 있다)."""
    return next(s for hi, s in RADICAL_GROUPS if r <= hi)


def wonhoek(cp: int, rs: str) -> int:
    if cp in NUMERAL:
        return NUMERAL[cp]
    if cp in SPECIAL:
        return SPECIAL[cp]
    best = 0
    for item in rs.split():
        rad, rest = item.split(".")
        best = max(best, radical_strokes(int(rad.rstrip("'\""))) + int(rest))
    return best


def load_unihan() -> dict[int, dict]:
    fields = defaultdict(dict)
    with zipfile.ZipFile(CACHE / "Unihan.zip") as z:
        for name in ("Unihan_IRGSources.txt",):
            for line in z.read(name).decode("utf-8").splitlines():
                if line.startswith("U+"):
                    cp, key, val = line.split("\t", 2)
                    if key in ("kRSUnicode", "kTotalStrokes"):
                        fields[int(cp[2:], 16)][key] = val
    return fields


def main() -> None:
    uni = load_unihan()
    hun, hun_any = {}, {}
    with open(CACHE / "data-naver.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cp, m = int(row["unicode"], 16), row["meaning"].strip()
            for r in row["hangul"].split(","):
                hun[(cp, r.strip())] = m
            hun_any.setdefault(cp, m)
    out, seen = [], set()
    with open(CACHE / "data-gov.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cp = int(row["unicode"], 16)
            if cp not in uni or "kRSUnicode" not in uni[cp]:
                continue
            u = uni[cp]
            for r in row["hangul"].split(","):          # '금,김' 처럼 음이 둘인 줄은 나눈다
                r = r.strip()
                if not r or (cp, r) in seen:
                    continue
                seen.add((cp, r))
                out.append({"cp": cp, "r": r, "h": hun.get((cp, r)) or hun_any.get(cp, ""),
                            "w": wonhoek(cp, u["kRSUnicode"]), "p": int(u.get("kTotalStrokes", "0").split()[0])})
    out.sort(key=lambda x: (x["r"], x["w"], x["cp"]))
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(out)}개 ({sum(1 for x in out if x['h'])}개 훈음) → {OUT}")


if __name__ == "__main__":
    main()
