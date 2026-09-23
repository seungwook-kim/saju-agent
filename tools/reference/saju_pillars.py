import sys, os, random, json
from datetime import timedelta, date
sys.path.insert(0, os.getcwd())
from lunar_python import Solar
from love_fortune.manseryuk import STEMS_KR, BRANCHES_KR
from love_fortune.lunar import birth_moment
HAN_S = "\u7532\u4e59\u4e19\u4e01\u620a\u5df1\u5e9a\u8f9b\u58ec\u7678"; HAN_B = "\u5b50\u4e11\u5bc5\u536f\u8fb0\u5df3\u5348\u672a\u7533\u9149\u620c\u4ea5"
kr = lambda gz: STEMS_KR[HAN_S.index(gz[0])] + BRANCHES_KR[HAN_B.index(gz[1])]
random.seed(31); out = []
while len(out) < 240:
    d = date(1901, 1, 1) + timedelta(days=random.randint(0, 53000))
    if len(out) < 120 and d.month not in (12, 1, 2): continue    # 절반은 자월·축월 부근
    h, m = random.randint(0, 23), random.randint(0, 59)
    bm = birth_moment(d.year, d.month, d.day, h, m, "서울")
    cn = bm["utc"] + timedelta(hours=8)
    ec = Solar.fromYmdHms(cn.year, cn.month, cn.day, cn.hour, cn.minute, 0).getLunar().getEightChar()
    t = bm["true_solar"]
    ec2 = Solar.fromYmdHms(t.year, t.month, t.day, t.hour, t.minute, 0).getLunar().getEightChar(); ec2.setSect(1)
    out.append({"birth": d.isoformat(), "time": f"{h:02d}:{m:02d}", "city": "서울",
                "pillars": {"year": kr(ec.getYear()), "month": kr(ec.getMonth()), "day": kr(ec2.getDay()), "hour": kr(ec2.getTime())}})
json.dump({"source": "lunar-python 1.4.8 (6tail, MIT). 절기는 같은 순간을 중국 표준시로, 일·시는 진태양시로 넣어 계산", "cases": out},
          open("tests/data/saju_pillars.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(len(out))
