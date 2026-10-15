"""화면 글꼴 부분 파일 만들기 (개발할 때만 쓴다. 앱 실행에는 외부 패키지를 쓰지 않는다).

Gowun Batang 700 · Gowun Dodum 400 (SIL OFL 1.1, Google Fonts 저장소 ofl/gowunbatang, ofl/gowundodum) 을 받아
- ks  : KS X 1001 완성형 한글 2,350자 + 영숫자·문장부호 (거의 모든 화면 글자)
- rest: 나머지 한글 음절·자모 (드물게 나오는 글자만, 그 글자가 화면에 있을 때만 브라우저가 받는다)
두 파일로 나눠 love_fortune/static/fonts 에 둔다. 한자는 넣지 않는다 (이름 풀이 한자 칸은 기기 글꼴로 그린다).

실행 (저장소에 의존성을 더하지 않고 그때만 받아 쓴다):
  uv run --no-project --with fonttools --with brotli python tools/build_fonts.py
"""
from __future__ import annotations

import sys
import tempfile
import urllib.request
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "love_fortune" / "static" / "fonts"
VER = "v1"
SRC = {
    ("GowunBatang", 700): "https://raw.githubusercontent.com/google/fonts/main/ofl/gowunbatang/GowunBatang-Bold.ttf",
    ("GowunDodum", 400): "https://raw.githubusercontent.com/google/fonts/main/ofl/gowundodum/GowunDodum-Regular.ttf",
}
FAMILY = {"GowunBatang": "SajuBatang", "GowunDodum": "SajuDodum"}

KS_HANGUL = [c for c in range(0xAC00, 0xD7A4) if len(chr(c).encode("euc-kr", "ignore")) == 2]
BASIC = list(range(0x20, 0x7F)) + [0xA0, 0xB7, 0x2013, 0x2018, 0x2019, 0x201C, 0x201D, 0x2026, 0x2039, 0x203A,
                                   0x2190, 0x2192, 0x25B2, 0x25BC, 0x25CB, 0x25CF, 0x3001, 0x3002, 0x300C, 0x300D]
KS = sorted(set(KS_HANGUL + BASIC))
REST_RANGES = [(0xAC00, 0xD7A3), (0x1100, 0x11FF), (0x3131, 0x318E)]
# rest 규칙은 한글 전체 범위로 적고 앞에 둔다. ks 규칙이 뒤에 있어 ks 글자는 ks 파일이 먼저 맡는다.
REST_CSS = ",".join(f"U+{a:X}-{b:X}" for a, b in REST_RANGES)


def ranges(cps: list[int]) -> str:
    out, start, prev = [], None, None
    for c in cps:
        if start is None:
            start = prev = c
        elif c == prev + 1:
            prev = c
        else:
            out.append((start, prev))
            start = prev = c
    out.append((start, prev))
    return ",".join(f"U+{a:X}" if a == b else f"U+{a:X}-{b:X}" for a, b in out)


def cut(src: Path, cps: list[int], dest: Path):
    o = subset.Options()
    o.flavor = "woff2"
    o.layout_features = ["*"]
    o.name_IDs = ["*"]                        # 저작권·라이선스 이름표를 남긴다 (OFL)
    o.notdef_outline = True
    f = TTFont(src)
    s = subset.Subsetter(o)
    s.populate(unicodes=cps)
    s.subset(f)
    f.flavor = "woff2"
    f.save(dest)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="saju-fonts-"))
    css = ["/* 종합 사주 글꼴: Gowun Batang 700, Gowun Dodum 400 (SIL Open Font License 1.1, Copyright 2021 The Gowun Batang / Gowun Dodum Project Authors).",
           "   tools/build_fonts.py 로 만든 부분 글꼴. rest 는 ks 에 없는 한글만 담고, 그 글자가 화면에 있을 때만 받는다.",
           "   같은 글자를 두 규칙이 덮으면 뒤에 적힌 규칙(ks)이 먼저 쓰인다. */"]
    for (name, weight), url in SRC.items():
        ttf = tmp / (name + ".ttf")
        urllib.request.urlretrieve(url, ttf)
        all_cps = set(TTFont(ttf).getBestCmap())
        rest = sorted(c for a, b in REST_RANGES for c in range(a, b + 1) if c in all_cps and c not in KS)
        ks_file = f"{name}-{weight}-ks-{VER}.woff2"
        rest_file = f"{name}-{weight}-rest-{VER}.woff2"
        cut(ttf, [c for c in KS if c in all_cps], OUT / ks_file)
        cut(ttf, rest, OUT / rest_file)
        fam = FAMILY[name]
        css.append(f"@font-face{{font-family:'{fam}';font-weight:{weight};font-style:normal;font-display:swap;"
                   f"src:url(/static/fonts/{rest_file}) format('woff2');unicode-range:{REST_CSS}}}")
        css.append(f"@font-face{{font-family:'{fam}';font-weight:{weight};font-style:normal;font-display:swap;"
                   f"src:url(/static/fonts/{ks_file}) format('woff2');unicode-range:{ranges([c for c in KS if c in all_cps])}}}")
        print(name, weight, (OUT / ks_file).stat().st_size, (OUT / rest_file).stat().st_size)
    (OUT / f"fonts-{VER}.css").write_text("\n".join(css) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
