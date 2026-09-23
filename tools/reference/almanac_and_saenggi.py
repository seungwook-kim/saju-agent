import json, re, html, sys
from datetime import date, timedelta
from lunar_python import Solar
T = json.load(open("tools/data/almanac_terms.json", encoding="ascii"))
HAN_B = "子丑寅卯辰巳午未申酉戌亥"
off = {}; spi = {}; mans = []
d = date(2000, 1, 1)
while d < date(2004, 1, 1):
    l = Solar.fromYmd(d.year, d.month, d.day).getLunar()
    mb, db = HAN_B.index(l.getMonthZhi()), HAN_B.index(l.getDayZhi())
    off[f"{mb},{db}"] = T["officer"][l.getZhiXing()][0]
    spi[f"{mb},{db}"] = T["spirit"][l.getDayTianShen()][0]
    if d < date(2000, 3, 1): mans.append([d.isoformat(), T["mansion"][l.getXiu()]])
    d += timedelta(days=1)
json.dump({"source": "lunar-python 1.4.8 (6tail, MIT). 월지는 절기가 든 날부터 그 달",
           "officer": off, "spirit": spi, "mansion": mans},
          open("tests/data/almanac_lunar_python.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(len(off), len(spi), len(mans))
# 생기복덕 조견표 (궁합닷컴): 나이 행 8개 뒤에 열 단위로 8칸씩 8열
b = open(sys.argv[1], "rb").read().decode("cp949", errors="replace")
txt = html.unescape(re.sub(r"<[^>]+>", "|", b)); txt = re.sub(r"\|\s*(\|\s*)+", "|", txt); txt = re.sub(r"\s+", " ", txt)
out = {}
for sex, key in (("male", "남자|"), ("female", "여자|")):
    seg = txt[txt.index(key) + len(key):]
    cells = [c.strip() for c in seg.split("|")]
    ages = [c.replace("--", "").strip() for c in cells[:8]]
    vals = cells[8:8 + 64]
    cols = ["생기", "천의", "절체", "유혼", "화해", "복덕", "절명", "귀혼"]
    rows = []
    for r in range(8):
        rows.append({"ages": [int(a) for a in ages[r].split(",")],
                     "cells": {cols[c]: vals[c * 8 + r].replace(" ", "").split(",") for c in range(8)}})
    out[sex] = rows
json.dump({"source": "궁합닷컴 생기복덕 조견표 (gunghap.com/taekil/saenggi_p.php3), 세는나이 기준", "table": out},
          open("tests/data/saenggi_table.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(out["male"][0], out["female"][7]["ages"][:3])
