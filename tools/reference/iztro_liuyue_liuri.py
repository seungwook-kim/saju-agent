import json, random, subprocess, sys, os
from datetime import date, timedelta
from collections import Counter
sys.path.insert(0, os.getcwd())
from love_fortune.ziwei import chart_from_lunar
from love_fortune.lunar import _months, lunar_to_solar, solar_to_lunar
IZ = sys.argv[1]; random.seed(21); cases = []
while len(cases) < 1500:
    ly = random.randint(1940, 2015); m, leap, days = random.choice(_months(ly)); d = random.randint(1, days)
    t = date(2000, 1, 1) + timedelta(days=random.randint(0, 365 * 45))
    cases.append({"lunar": f"{ly}-{m}-{d}", "leap": leap, "hb": random.randint(0, 11), "sex": random.choice(["male", "female"]),
                  "target": f"{t.year}-{t.month}-{t.day}", "_t": [ly, m, d, leap, t.isoformat()]})
out = json.loads(subprocess.run(["node", os.path.join(IZ, "dump_md.js")], input=json.dumps(cases), capture_output=True, text=True, encoding="utf-8", cwd=IZ).stdout)
HAN = "\u3007\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341"
bad = Counter(); ex = {}; ok = skip = 0
for c, z in zip(cases, out):
    ly, m, d, leap, t = c["_t"]; t = date.fromisoformat(t); sd = lunar_to_solar(ly, m, d, leap)
    if "err" in z or z["solar"] != f"{sd.year}-{sd.month}-{sd.day}": skip += 1; continue
    tl = solar_to_lunar(t.year, t.month, t.day)
    if tl[3]: skip += 1; continue                      # 기준일이 윤달이면 건너뜀 (처리 방식이 갈림)
    ch = chart_from_lunar(ly, m, d, leap, c["hb"], c["sex"], t)
    # iztro 의 기준일 음력(중국)이 한국과 다르면 건너뜀
    zl = z["lunarTarget"]
    mm = zl.split("\u5e74")[1].split("\u6708")[0]; dd = zl.split("\u6708")[1]
    def cn(x):
        x = x.replace("\u521d", "").replace("\u5eff", "\u4e8c\u5341").replace("\u5345", "\u4e09\u5341").replace("\u6b63", "\u4e00").replace("\u814a", "\u5341\u4e8c").replace("\u51ac", "\u5341\u4e00")
        if x == "\u5341": return 10
        if x.startswith("\u5341"): return 10 + HAN.index(x[1])
        if "\u5341" in x: a, b = x.split("\u5341"); return HAN.index(a) * 10 + (HAN.index(b) if b else 0)
        return HAN.index(x)
    if "\u95f0" in mm or (cn(mm), cn(dd)) != (tl[1], tl[2]): skip += 1; continue
    ok += 1
    for key, zk in (("liuyue", "monthly"), ("liuri", "daily")):
        mine = ch[key]; theirs = z[zk]
        if mine["branch"] != theirs[0]: bad[key + " 궁"] += 1; ex.setdefault(key + " 궁", (c["_t"], c["hb"], mine["branch"], theirs[0]))
        if mine["ganzhi"] != theirs[1]: bad[key + " 간지"] += 1; ex.setdefault(key + " 간지", (c["_t"], mine["ganzhi"], theirs[1]))
        if [mine["sihua"][k] for k in "록권과기"] != theirs[2]: bad[key + " 사화"] += 1; ex.setdefault(key + " 사화", (c["_t"], mine["sihua"], theirs[2]))
print(f"{ok}건 대조 (건너뜀 {skip})")
for k, v in bad.items(): print(f"  {k}: {v}건 불일치  예) {ex[k]}")
if not bad: print("  전 항목 일치")
