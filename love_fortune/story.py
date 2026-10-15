"""story.py, 탭별 이야기식 해설 (로컬·결정적).

처음 보는 사람도 술술 읽히도록 계산 결과를 문장으로 풀어 쓴다.
어려운 말은 처음 나올 때 괄호로 짧게 설명한다.
"""
from __future__ import annotations

from .josa import j

from .rules import headline as _headline
from .narrate import STAR_TALK, _eun


def build_stories(natal: dict, ma: dict, adv: dict, target) -> dict:
    ilgan = natal["ilgan"]
    elem = natal["ilgan_element"]
    t = ma["total"]
    c = ma["career"]
    m = ma["money"]
    love_head = _headline(t["love"])

    total = [
        f"오늘은 {target.isoformat()}일이다. "
        f"나는 일간 {ilgan}({elem} 기운), 즉 {ilgan}의 기질로 하루를 시작한다.",
        f"오늘 총운은 {t['score']}점이다. {t['head']}. "
        f"연애 {t['love']}점, 직장 {t['career']}점, 금전 {t['money']}점으로, "
        f"가장 높은 영역부터 먼저 손대면 하루가 가볍다.",
        # 색·장소·타로는 날짜 해시로 뽑는 재미 요소라 오늘 판단 문단에서 뺐다 ('재미로 보는 점괘')
        f"오늘의 키워드는 {', '.join(t['keywords'])}이다.",
    ]

    vd = ma["venus_detail"]
    if ma.get("hour_unknown"):
        love = [
            f"오늘 연애운은 {t['love']}점이다. {love_head} "
            f"일간 {ilgan}의 입장에서 오늘 일진(그날의 간지)과 사주 궁합을 셈한 결과다.",
            "시간 미상이라 부처궁(배우자를 보는 자리) 별 풀이는 제외, 사주 십성과 금성으로 봐.",
            f"금성은 {ma['venus']}에 있어 {vd['style']} "
            f"대화는 이렇게 풀어보자. {adv['talk'][0]} "
            f"그리고 {ma['timing']}",
        ]
    else:
        love = [
            f"오늘 연애운은 {t['love']}점이다. {love_head} "
            f"일간 {ilgan}의 입장에서 오늘 일진(그날의 간지)과 사주 궁합을 셈한 결과다.",
            f"눈에 띄는 건 부처궁(배우자를 보는 자리)에 {j(ma['ziwei_main'], '이')} 앉아 있다는 점이다. "
            f"{ma['ziwei_detail']['look']} "
            f"이런 상대와는 {ma['ziwei_detail']['tip']}",
            f"금성은 {ma['venus']}에 있어 {vd['style']} "
            f"대화는 이렇게 풀어보자. {adv['talk'][0]} "
            f"그리고 {ma['timing']}",
        ]

    career = [
        f"오늘 직장운은 {c['score']}점이다. {c['head']}",
        ("시간 미상이라 관록궁(직업을 보는 자리) 주성 풀이는 제외, 원국 관성과 대운으로 봐."
         if ma.get("hour_unknown") else
         f"관록궁(직업을 보는 자리)에는 {c['guanlu_main']}{_eun(c['guanlu_main'])} 앉아 있어. "
         f"{STAR_TALK.get(c['guanlu_main'], '자기 자리를 지키는 별이야')}"),
        f"{c['guan_line']}.",
        f"{ma['daxian_line']}.",
        f"실천 팁으로는 {c['tips'][0]}, {c['tips'][1]}{_eun(c['tips'][1])} 좋고, "
        f"{c['avoid']}{_eun(c['avoid'])} 오늘만 피해보자.",
    ]

    money = [
        f"오늘 금전운은 {m['score']}점이다. {m['head']}",
        ("시간 미상이라 재백궁(돈을 보는 자리) 주성 풀이는 제외, 원국 재성과 대운으로 봐."
         if ma.get("hour_unknown") else
         f"재백궁(돈을 보는 자리)에는 {m['caibo_main']}{_eun(m['caibo_main'])} 앉아 있어. "
         f"{STAR_TALK.get(m['caibo_main'], '자기 자리를 지키는 별이야')}"),
        f"{m['cai_line']}.",
        f"실천 팁으로는 {m['tips'][0]}, {m['tips'][1]}{_eun(m['tips'][1])} 좋고, "
        f"{m['avoid']}{_eun(m['avoid'])} 오늘만 피해보자.",
    ]

    lt = ma["lifetime"]
    cur = lt["current"]
    life = [
        ("시간 미상이라 사주 대운으로만 0세부터 89세까지 펼쳐보면, "
         if ma.get("hour_unknown") else
         "사주 명반과 자미 명반을 겹쳐 0세부터 89세까지 펼쳐보면, ")
        + f"지금({cur['range'][0]}~{cur['range'][1]}세)은 {cur['saju']} 시기야. "
        + ("" if ma.get("hour_unknown") else f"{cur['ziwei']} 시기가 겹치는 구간이다."),
    ]
    for p in lt["phases"]:
        life.append(f"{p['name']} 이야기로는 {p['line']}")
    life.append("올해를 포함한 전후 흐름은 연도별 표에서 확인할 수 있다.")

    return {"total": total, "love": love, "career": career,
            "money": money, "life": life}
