"""iztro 명반 일부를 테스트 데이터로 저장 (한중 음력이 같은 날만)."""
import json, random, subprocess, sys, os
sys.path.insert(0, os.getcwd())
from love_fortune.lunar import _months, lunar_to_solar
IZ = sys.argv[1]; random.seed(2026); cases = []
while len(cases) < 150:
    ly = random.randint(1900, 2049); m, leap, days = random.choice(_months(ly)); d = random.randint(1, days)
    cases.append({"lunar": f"{ly}-{m}-{d}", "leap": leap, "hb": random.randint(0, 11), "sex": random.choice(["male", "female"])})
out = json.loads(subprocess.run(["node", os.path.join(IZ, "dump.js")], input=json.dumps(cases), capture_output=True, text=True, encoding="utf-8", cwd=IZ).stdout)
KEEP = {"홍란","천희","천요","함지","천형","화개","고진","과숙","태보","봉고","천재","천수","삼태","팔좌","은광","천귀","천공","천곡","천허","용지","봉각","절로","공망"}
fx = []
for c, z in zip(cases, out):
    ly, m, d = map(int, c["lunar"].split("-")); sd = lunar_to_solar(ly, m, d, c["leap"])
    if z is None or z["solar"] != f"{sd.year}-{sd.month}-{sd.day}": continue
    fx.append({"lunar": [ly, m, d, c["leap"]], "hb": c["hb"], "sex": c["sex"], "five": z["five"], "soul": z["soul"], "body": z["body"],
               "palaces": {p["branch"]: {"name": p["name"], "stem": p["stem"], "major": p["major"], "minor": p["minor"],
                                         "adj": sorted(set(p["adj"]) & KEEP), "range": p["range"], "cs": p["cs"], "bs": p["bs"]}
                           for p in z["palaces"]}})
    if len(fx) == 120: break
json.dump({"source": "iztro 2.x (npm), 한중 음력이 같은 날만", "charts": fx},
          open("tests/data/iztro_charts.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(len(fx), os.path.getsize("tests/data/iztro_charts.json"))
