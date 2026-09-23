"""cli.py, 터미널 CLI + 하루 리포트 생성. 로컬 전용, PII는 메모리에만."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta

from .manseryuk import four_pillars, day_pillar, ganzhi_str, normalize_sex, time_notes
from .lunar import parse_birth_date
from .josa import j
from .rules import love_score, headline, branch_relation
from .advise import build_advice
from .synthesis import detailed_reading
from .narrate import (_rel_text as _rel_talk, ziwei_puli, astro_puli,
                      match_puli, narrate_palace, narrate_slice_row,
                      STAR_TALK, HUA_TALK, AUX_TALK, GUO_NAME, GOD_SHORT,
                      ming_seat_text)
from .lifetime import MAIN14
from .domains import CAREER_STAR, MONEY_STAR
from .narrate import _eun as _eun_word
from .glossary import TERMS

DISCLAIMER = ("[정통 계산] 사주·자미두수·점성술의 전통 공식 그대로 계산한 상세 해석입니다. "
              "생년월일 등 개인정보는 파일에 저장하지 않고 메모리에만 둡니다.")

DOMAINS = ("total", "love", "career", "money", "all")


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="love_fortune",
        description="종합 사주 (로컬·정통 계산). "
                    "인자 없이 실행하면 대화형 입력 모드, "
                    "`form` 서브커맨드로 브라우저 입력폼을 열 수 있다.")
    p.add_argument("--birth", help="생년월일 YYYY-MM-DD (기본 양력, --calendar lunar 면 음력)")
    p.add_argument("--calendar", default="solar", choices=["solar", "lunar"],
                   help="생년월일 달력: solar(양력, 기본) 또는 lunar(음력)")
    p.add_argument("--leap", action="store_true", help="음력 생일이 윤달이면 붙인다")
    p.add_argument("--birth-time", default="12:00",
                   help="태어난 시간 HH:MM, 모르면 '모름' (시주 제외·자미/하우스 제외하고 3기둥으로 계산)")
    p.add_argument("--sex", default="male", type=_sex_arg,
                   help="성별 male/female (남/여도 됨). 대운 방향과 연애운 해석에 쓴다")
    p.add_argument("--city", default="서울",
                   help="태어난 도시 (진태양시·당시 표준시·서머타임 보정에 쓴다, 해외 주요 도시 가능)")
    p.add_argument("--zi", default="next", choices=["next", "split"],
                   help="밤 11시~12시 출생 기준: next=다음날로(정자시, 기본), split=일주는 그날(야자시)")
    p.add_argument("--tomorrow", action="store_true", help="내일 리포트")
    p.add_argument("--date", help="기준일 YYYY-MM-DD (기본: 오늘, 테스트·재현용)")
    p.add_argument("--no-save", action="store_true", help="md 파일 저장 안 함")
    p.add_argument("--interactive", action="store_true", help="대화형 입력 모드")
    p.add_argument("--domain", default="all", choices=DOMAINS,
                   help="출력 영역: total(총운)·love(연애)·career(직장)·money(금전)·all(전체)")
    p.add_argument("--lifetime", action="store_true",
                   help="평생 운세 타임라인(연대별·연도별) 추가")
    sub = p.add_subparsers(dest="cmd")
    f = sub.add_parser("form", help="홈페이지식 로컬 웹 + 채팅 에이전트 열기 (localhost, 저장 없음)")
    f.add_argument("--port", type=int, default=8765)
    f.add_argument("--host", default="127.0.0.1",
                   help="서버를 열 주소 (기본 127.0.0.1 = 이 컴퓨터만. 다른 기기에서 보려면 0.0.0.0)")
    mm = sub.add_parser("match", help="두 사람 궁합 보기 (로컬 계산, 저장 없음)")
    mm.add_argument("--birth", required=True, help="내 생년월일 YYYY-MM-DD")
    mm.add_argument("--calendar", default="solar", choices=["solar", "lunar"])
    mm.add_argument("--leap", action="store_true", help="내 음력 생일이 윤달이면")
    mm.add_argument("--birth-time", default="12:00", help="모르면 '모름'")
    mm.add_argument("--sex", default="male", type=_sex_arg)
    mm.add_argument("--city", default="서울")
    mm.add_argument("--birth2", required=True, help="상대 생년월일 YYYY-MM-DD")
    mm.add_argument("--calendar2", default="solar", choices=["solar", "lunar"])
    mm.add_argument("--leap2", action="store_true", help="상대 음력 생일이 윤달이면")
    mm.add_argument("--birth2-time", default="12:00", help="모르면 '모름'")
    mm.add_argument("--sex2", default="female", type=_sex_arg)
    mm.add_argument("--city2", default="서울")
    mm.add_argument("--no-save", action="store_true")
    mm.add_argument("--zi", choices=["next", "split"], default=argparse.SUPPRESS,
                    help="밤 11시~12시 출생 기준 (next=정자시, split=야자시)")
    pk = sub.add_parser("pick", help="기간 내 길일 고르기 (로컬 계산)")
    pk.add_argument("--birth", required=True, help="생년월일 YYYY-MM-DD")
    pk.add_argument("--calendar", default="solar", choices=["solar", "lunar"])
    pk.add_argument("--leap", action="store_true", help="음력 생일이 윤달이면")
    pk.add_argument("--birth-time", default="12:00", help="모르면 '모름'")
    pk.add_argument("--sex", default="male", type=_sex_arg)
    pk.add_argument("--city", default="서울")
    pk.add_argument("--from", dest="from_date", required=True, help="시작일 YYYY-MM-DD")
    pk.add_argument("--to", dest="to_date", required=True, help="끝일 YYYY-MM-DD (최대 62일)")
    pk.add_argument("--domain", default="total", choices=("total", "love", "career", "money"),
                    help="목적별 정렬")
    pk.add_argument("--top", type=int, default=5, help="상위 몇 개 상세 표시")
    pk.add_argument("--no-save", action="store_true")
    pk.add_argument("--zi", choices=["next", "split"], default=argparse.SUPPRESS,
                    help="밤 11시~12시 출생 기준 (next=정자시, split=야자시)")
    return p.parse_args(argv)


def interactive_ask() -> dict:
    print(DISCLAIMER)
    cal = input("양력/음력 (Enter → 양력, 음력이면 '음력'): ").strip() or "양력"
    cal = "lunar" if cal in ("음력", "lunar", "l", "음") else "solar"
    leap = False
    birth = input(f"{'음력' if cal == 'lunar' else '양력'} 생년월일 (YYYY-MM-DD): ").strip()
    if cal == "lunar":
        leap = input("윤달이야? (y/N): ").strip().lower() in ("y", "yes", "예", "네", "응")
    bt = input("태어난 시간 (HH:MM, 모르면 '모름' 입력): ").strip() or "모름"
    while True:
        try:
            sex = normalize_sex(input("성별 (남/여): ").strip())
            break
        except ValueError as e:
            print(f"  {e}")
    city = input("태어난 도시 (Enter → 서울): ").strip() or "서울"
    return {"birth": birth, "calendar": cal, "leap": leap, "birth_time": bt,
            "sex": sex, "city": city}


def today_lines(ma: dict) -> list[tuple[str, str]]:
    """오늘 세 체계 종합을 (표시 머리, 문장) 목록으로. 터미널·md·웹 공용, 개인정보 없음."""
    t = ma["today"]
    out = [("종합", t["agreement"]), ("종합", t["focus"])]
    for s in t["systems"]:
        for line in s["lines"]:
            out.append((f"{s['name']}·{s['signal']}", line))
    for line in t["almanac"]["lines"]:
        out.append(("택일", line))
    return out


def build_report(birth: date, hour: int | None, minute: int, sex: str,
                 city: str, target: date, domain: str = "all",
                 lifetime: bool = False) -> tuple[str, str]:
    """(터미널 텍스트, md 텍스트) 반환. PII(생년월일·시간·성별·도시)는 포함하지 않음.

    순서: 사주 4기둥 → 오늘 세 체계 종합 → 오늘 총운·연애·직장·금전(오늘만)
    → 타고난 명식(원국·명반·출생 차트·인연) → 이번 달·올해 흐름 → 재미로 보는 점괘
    → 평생 운세 → 용어 풀이. 예전엔 오늘 운세 안에 30일·12개월 표와 출생 차트가 섞여 있었다.
    """
    natal = four_pillars(birth, hour, minute, city)
    ts, tb = day_pillar(target)
    ma = detailed_reading(birth, hour, minute, sex, city, target)
    t_all = ma["total"]
    adv = build_advice(natal["ilgan"], ma["today_elem"], target, birth)
    ast = ma["astro"]
    zw = ma["ziwei"]
    rels = branch_relation(natal["day_branch"], tb)
    show = lambda *ds: domain == "all" or domain in ds
    natal_all = domain in ("all", "total")

    L: list[str] = []
    M: list[str] = []

    # ---------------- 머리
    L += ["=" * 46, f"  종합 사주 ({target.isoformat()}), {city}의 흐름", DISCLAIMER, "=" * 46]
    M += [f"# 종합 사주 ({target.isoformat()})", "", "> " + DISCLAIMER,
          "> 이 파일에는 생년월일·태어난 시간·성별·도시를 저장하지 않습니다.", ""]
    L.append(f"\n[사주 4기둥] 일간(나): {natal['ilgan']} ({natal['ilgan_element']} 기운)")
    for k, v in natal["strings"].items():
        L.append(f"  - {k}: {v}")
    rel_txt = (f"내 일지와 오늘 일진은 {_rel_talk(rels)} 사이야" if rels
               else "내 일지와 오늘 일진은 특별히 부딪치지도 손잡지도 않아")
    L.append(f"  - 오늘 일진: {ganzhi_str(ts, tb)} / {rel_txt}")
    M += [f"- 일간(나): {natal['ilgan']} ({natal['ilgan_element']})",
          f"- 오늘 일진: {ganzhi_str(ts, tb)} / {rel_txt}", ""]
    if natal["hour_unknown"]:
        L.append("  · 시간 미상이라 진태양시 미표기 · 자시(23시 이후) 출생이면 일주가 하루 차이날 수 있어")
        L.append(f"  · 안내: {ma['time_notice']}")
    else:
        L.append(f"  · 진태양시 {natal['true_solar']} (보정 {natal['corr_min']}분)")
        for _note in time_notes(natal):
            L.append(f"  · {_note}")

    # ---------------- 오늘 세 체계 종합
    if show("total"):
        L.append("\n[오늘 세 체계 종합] 사주·자미두수·점성술·택일로 본 오늘")
        M.append("## 오늘 세 체계 종합")
        for head, line in today_lines(ma):
            L.append(f"  · [{head}] {line}")
            M.append(f"- [{head}] {line}")
        M.append("")

    # ---------------- 오늘 총운
    if show("total"):
        L.append(f"\n[오늘 총운] {t_all['score']}점 / 100점 "
                 f"(연애 {t_all['love']}·직장 {t_all['career']}·금전 {t_all['money']})")
        L.append(f"  한 줄 총평: {t_all['head']}")
        M.append("## 오늘 총운")
        if ma["hour_unknown"]:
            M.append(f"- 안내: {ma['time_notice']}")
        M.append(f"- 오늘 총운: **{t_all['score']}점 / 100점** (연애 {t_all['love']}·직장 {t_all['career']}"
                 f"·금전 {t_all['money']}), {t_all['head']}")
        for p in ma["stories"]["total"]:
            L.append(f"  {p}")
            M.append(f"- [이야기] {p}")
        for r in t_all["reasons"]:
            L.append(f"  · {r}")
            M.append(f"- {r}")
        L.append(f"  · 오늘의 키워드: {', '.join(t_all['keywords'])}")
        M.append(f"- 오늘의 키워드: {', '.join(t_all['keywords'])}")
        M.append("")

    # ---------------- 오늘 연애운
    if show("love"):
        lv = ma["love"]
        L.append(f"\n[오늘 연애운] {lv['score']}점 / 100점")
        L.append(f"  한 줄 총평: {lv['head']}")
        M.append(f"## 오늘 연애운 ({lv['score']}점)")
        for p in ma["stories"]["love"]:
            L.append(f"  {p}")
            M.append(f"- [이야기] {p}")
        for r in lv["reasons"]:
            L.append(f"  · {r}")
            M.append(f"- {r}")
        M.append(f"- 한 줄 총평: {lv['head']}")
        L.append("  · 데이트 대화 팁 3:")
        for x in adv["talk"]:
            L.append(f"    - {x}")
        L.append(f"  · 오늘 피할 것 1: {adv['avoid']}")
        M.append(f"- 대화 팁: {'; '.join(adv['talk'])}")
        M.append(f"- 피할 것: {adv['avoid']}")
        M.append("")

    # ---------------- 오늘 직장운
    if show("career"):
        c = ma["career"]
        L.append(f"\n[오늘 직장운] {c['score']}점 / 100점")
        L.append(f"  한 줄 총평: {c['head']}")
        M.append(f"## 오늘 직장운 ({c['score']}점)")
        for p in ma["stories"]["career"]:
            L.append(f"  {p}")
            M.append(f"- [이야기] {p}")
        M.append(f"- 한 줄 총평: {c['head']}")
        for r in c["reasons"]:
            L.append(f"  · {r}")
            M.append(f"- {r}")
        if ma["hour_unknown"]:
            L.append("  · 관록궁 주성 풀이는 시간 미상이라 제외, 원국 관성과 대운으로 봐.")
            M.append("- 관록궁 주성 풀이는 시간 미상이라 제외, 원국 관성과 대운으로 봐.")
        else:
            line = (f"관록궁 주성 {c['guanlu_main']}: 일을 보는 자리에 {j(c['guanlu_main'], '이')} 앉아 있어. "
                    f"{STAR_TALK.get(c['guanlu_main'], '자기 자리를 지키는 별이야')} {CAREER_STAR.get(c['guanlu_main'], '')}")
            L.append(f"  · {line}")
            M.append(f"- {line}")
        L.append(f"  · {c['guan_line']}")
        M.append(f"- {c['guan_line']}")
        L.append("  · 관록궁 삼방사정 (같은 명반 기반):")
        for x in c["palaces"]:
            L.append(f"    - {narrate_slice_row(x)}")
            M.append(f"- 관록궁 삼방: {narrate_slice_row(x)}")
        for line in ma["career_extra"]:
            L.append(f"  · {line}")
            M.append(f"- {line}")
        L.append("  · 일의 팁 3:")
        for x in c["tips"]:
            L.append(f"    - {x}")
        L.append(f"  · 오늘 피할 것 1: {c['avoid']}")
        M.append(f"- 일의 팁: {'; '.join(c['tips'])}")
        M.append(f"- 피할 것: {c['avoid']}")
        M.append("")

    # ---------------- 오늘 금전운
    if show("money"):
        m = ma["money"]
        L.append(f"\n[오늘 금전운] {m['score']}점 / 100점")
        L.append(f"  한 줄 총평: {m['head']}")
        M.append(f"## 오늘 금전운 ({m['score']}점)")
        for p in ma["stories"]["money"]:
            L.append(f"  {p}")
            M.append(f"- [이야기] {p}")
        M.append(f"- 한 줄 총평: {m['head']}")
        for r in m["reasons"]:
            L.append(f"  · {r}")
            M.append(f"- {r}")
        if ma["hour_unknown"]:
            L.append("  · 재백궁 주성 풀이는 시간 미상이라 제외, 원국 재성과 대운으로 봐.")
            M.append("- 재백궁 주성 풀이는 시간 미상이라 제외, 원국 재성과 대운으로 봐.")
        else:
            line = (f"재백궁 주성 {m['caibo_main']}: 돈을 보는 자리에 {j(m['caibo_main'], '이')} 앉아 있어. "
                    f"{STAR_TALK.get(m['caibo_main'], '자기 자리를 지키는 별이야')} {MONEY_STAR.get(m['caibo_main'], '')}")
            L.append(f"  · {line}")
            M.append(f"- {line}")
        L.append(f"  · {m['cai_line']}")
        M.append(f"- {m['cai_line']}")
        L.append("  · 재백궁 삼방사정 (같은 명반 기반):")
        for x in m["palaces"]:
            L.append(f"    - {narrate_slice_row(x)}")
            M.append(f"- 재백궁 삼방: {narrate_slice_row(x)}")
        for line in ma["money_extra"]:
            L.append(f"  · {line}")
            M.append(f"- {line}")
        L.append("  · 돈의 팁 3:")
        for x in m["tips"]:
            L.append(f"    - {x}")
        L.append(f"  · 오늘 피할 것 1: {m['avoid']}")
        M.append(f"- 돈의 팁: {'; '.join(m['tips'])}")
        M.append(f"- 피할 것: {m['avoid']}")
        M.append("")

    # ---------------- 타고난 명식 (오늘과 무관하게 평생 같은 것)
    if natal_all or show("love"):
        L.append("\n[타고난 명식] 태어날 때 정해진 바탕 (날마다 바뀌지 않아)")
        M.append("## 타고난 명식")
        for line in ma["dist"]:
            L.append(f"  · {line}")
            M.append(f"- {line}")
        L.append("\n[사주 대운·신살]")
        L.append(f"  · {ma['dayun_line']}")
        M.append(f"- {ma['dayun_line']}")
        for s in ma["shensha_lines"]:
            L.append(f"  · {s}")
            M.append(f"- {s}")
        L.append("\n[자미두수 정통 명반]")
        L.append(f"  · {ma['lunar_line']}")
        M.append(f"- {ma['lunar_line_safe']}")
        L.append(f"  · {ma['guo_line']}")
        M.append(f"- {ma['guo_line']}")
        if zw is None:
            L.append("  · 시간 미상이라 명반 상세 배치·12궁은 제외, 위 안내로 봐.")
            M.append("- 시간 미상이라 명반 상세 배치·12궁은 제외, 위 안내로 봐.")
        else:
            L.append(f"  · 부처궁(배우자) 주성 {ma['ziwei_main']}"
                     + (f" (무주성·대궁 {ma['ziwei_borrowed']} 차용)" if ma["ziwei_borrowed"] else "")
                     + (f" · 도화성 {', '.join(ma['peach'])}" if ma["peach"] else ""))
            L.append(f"  · 생년사화: {'; '.join(ma['sihua_lines'])}")
            M.append(f"- 생년사화: {'; '.join(ma['sihua_lines'])}")
            L.append(f"  · {ma['daxian_line']}")
            L.append(f"  · {ma['liunian_line']}")
            M.append(f"- {ma['daxian_line']}")
            M.append(f"- {ma['liunian_line']}")
            for line in ziwei_puli(ma):
                L.append(f"  · 풀이: {line}")
                M.append(f"- 풀이: {line}")
            L.append("\n[자미두수 12궁 배치]")
            M.append("")
            M.append("### 자미두수 12궁 풀이")
            for p in zw["palaces"]:
                mains = [s for s in p["stars"] if s in MAIN14]
                L.append(f"  · {narrate_palace(p, mains, zw['xusui'])}")
                M.append(f"- {narrate_palace(p, mains, zw['xusui'])}")
        L.append("\n[서양 점성술 출생 차트] 태어난 순간의 하늘")
        M.append("")
        M.append("### 서양 점성술 출생 차트")
        L.append(f"  · 태양 {ast['sun']['sign']}({ast['sun']['planet']}) · "
                 f"달 {ast['moon']['sign']} · 금성 {ast['venus']['sign']}")
        _rtr = " ".join(ast["retro_notes"]) or "역행 중이던 행성은 없어"
        _csp = " ".join(ast["cusp_notes"]) or ""
        if ma["hour_unknown"]:
            line = f"시간 미상이라 상승궁·중천 제외. {_rtr}.{_csp and ' ' + _csp + '.' or ''}"
        else:
            line = (f"상승궁(첫인상 자리)은 {j(ast['ascendant'], '이야')}. "
                    f"중천(직업 자리)은 {j(ast['mc'], '이야')}. {_rtr}.{_csp and ' ' + _csp + '.' or ''}")
        L.append(f"  · 풀이: {line}")
        M.append(f"- {line}")
        for line in astro_puli(ma):
            L.append(f"  · 풀이: {line}")
            M.append(f"- 풀이: {line}")
        L.append("\n[만날 인연 아키타입, 정통 계산 기반 상세]")
        M.append("")
        M.append("## 만날 인연 아키타입 (정통 계산)")
        rows = [
            f"배우자궁(배우자를 보는 자리)에는 '{ma['god']}'({GOD_SHORT[ma['god']]}) 기운이 앉아 있어. {ma['side']}",
            f"관계 에너지: {ma['god_vibe']} / 관계 팁: {ma['god_tip']}",
            f"어울리는 직업군: {ma['god_job']}",
            ma["star_line"],
            f"일주 십이운성 '{ma['stage']}'(기운의 12단계 중 하나): {ma['stage_love']}",
            *ma["dohwa_lines"], ma["hong_line"],
        ]
        if ma["jindohwa"]:
            rows.append("진도화 일주, 매력이 정통으로 드러나기 쉬운 흐름으로 전해짐")
        zd = ma["ziwei_detail"]
        if ma["hour_unknown"]:
            rows.append("자미두수 부처궁 풀이는 시간 미상이라 제외.")
        else:
            rows.append(f"자미두수 부처궁 '{ma['ziwei_main']}': {STAR_TALK.get(ma['ziwei_main'], '자기 색이 분명한 별이야')}. "
                        f"인상: {zd['look']} {zd['mind']} / 직업군: {zd['job']} / 만남: {zd['meet']} / 관계 팁: {zd['tip']}")
        vd = ma["venus_detail"]
        rows += [f"금성(사랑과 취향) {ma['venus']}, 연애 스타일: {vd['style']} / 끌리는 상대: {vd['ideal']} / 통하는 법: {vd['how']}",
                 f"달(감정) {ma['moon']}, {ma['moon_need']}",
                 f"만나기 쉬운 자리 TOP3: {', '.join(ma['meet_top3'])}",
                 f"올해 시기: {ma['timing']}", *ma["love_extra"]]
        for r in rows:
            L.append(f"  · {r}")
            M.append(f"- {r}")
        M.append("")

    # ---------------- 이번 달·올해 흐름 (오늘이 아닌 날)
    if show("total", "career", "money"):
        L.append("\n[이번 달·올해 흐름] 오늘이 아닌 날들 (사주 일진·월운 기준, 계획용)")
        M.append("## 이번 달·올해 흐름")
        if show("total"):
            L.append("  · 일운 30일 (매일 간지와 영역 점수, 사주 일진 기준):")
            for row in ma["ilun"]:
                L.append(f"    - {row['line']}")
                M.append(f"- [일운] {row['line']}")
            L.append(f"  · 풀이: {ma['month_line']}")
            M.append(f"- 풀이: {ma['month_line']}")
        if show("career"):
            L.append("  · 월별 직장 흐름 (이번 해 월간 계획용):")
            M.append("- 월별 직장 흐름 (이번 해 월간 계획용):")
            for row in ma["monthly"]:
                L.append(f"    - {row['career_line']}")
                M.append(f"- {row['career_line']}")
        if show("money"):
            L.append("  · 월별 금전 흐름 (이번 해 월간 계획용):")
            M.append("- 월별 금전 흐름 (이번 해 월간 계획용):")
            for row in ma["monthly"]:
                L.append(f"    - {row['money_line']}")
                M.append(f"- {row['money_line']}")
        M.append("")

    # ---------------- 재미로 보는 점괘 (계산과 무관)
    if show("total"):
        L.append("\n[재미로 보는 점괘] 사주·자미두수·점성술 계산과는 무관한 재미 요소야 (날짜로 뽑음)")
        L.append(f"  · 행운의 색: {adv['color']} / 방향: {adv['direction']} / 시간대: {adv['time']}")
        L.append(f"  · 추천 장소: {', '.join(adv['places'])}")
        L.append(f"  · 타로: {adv['tarot']}, {adv['tarot_line']}")
        L.append(f"  · 주역: {adv['gua']} / 효 {', '.join(adv['yao'])}, {adv['gua_line']}")
        L.append(f"  · 생명수 {adv['life_path']}(생년월일 숫자를 더한 값), {adv['life_path_vibe']}")
        M.append("## 재미로 보는 점괘 (계산과 무관)")
        M.append(f"- 행운의 색: {adv['color']} / 방향: {adv['direction']} / 시간대: {adv['time']}")
        M.append(f"- 장소: {', '.join(adv['places'])}")
        M.append(f"- 타로 {adv['tarot']}: {adv['tarot_line']}")
        M.append(f"- 주역 {adv['gua']}: {adv['gua_line']}")
        M.append("")

    L.append("\n" + DISCLAIMER)
    if lifetime:
        lt = ma["lifetime"]
        _yb = ma["yongsin"]
        _ya = _yb["analysis"]
        base = [f"타고난 기질: {_yb['ilgang']}",
                f"신강약 추정: {_ya['score']}점, {_ya['strong_label']} "
                f"(득령 {'있음' if _ya['deukryeong'] else '없음'} · "
                f"통근 {', '.join(_ya['tonggeun']) or '없음'} · "
                f"투출 {', '.join(_ya['tuchul']).replace('일간 ', '') or '없음'}, 점수화는 간략 추정)",
                f"격국: {_ya['geguk']}, {_ya['geguk_mean']}",
                f"용신: {_ya['yongsin']} (강약에 맞춘 간략법으로 본 것)"]
        L.append("\n[평생 운세 타임라인]")
        L.append("  · 타고난 바탕:")
        L += [f"    - {b}" for b in base]
        for p in lt["phases"]:
            L.append(f"  · {p['line']}")
        L.append(f"  · 지금 연대: {lt['current']['short']}")
        L.append("  · 연대별:")
        for d in lt["decades"]:
            L.append(f"    - {d['parts'][0]}")
            for sub in d["parts"][1:]:
                L.append(f"      · {sub}")
        L.append("  · 대운 풀이 (8스텝):")
        for line in _yb["dayun_narr"]:
            L.append(f"    - {line}")
        L.append("  · 연도별:")
        for y in lt["years"]:
            L.append(f"    - {y['line']}")
        M.append("## 평생 운세")
        for p in ma["stories"]["life"]:
            M.append(f"- [이야기] {p}")
        M += [f"- [바탕] {b}" for b in base]
        for p in lt["phases"]:
            M.append(f"- {p['line']}")
        M.append(f"- 지금 연대: {lt['current']['short']}")
        for d in lt["decades"]:
            M.append(f"- [연대] {d['line']}")
        for line in _yb["dayun_narr"]:
            M.append(f"- [대운] {line}")
        for y in lt["years"]:
            M.append(f"- [해] {y['line']}")
        M.append("")
    L.append("\n[용어 풀이, 처음 보는 사람을 위한 설명]")
    M.append("## 용어 풀이")
    for term, desc in TERMS.items():
        L.append(f"  · {term}: {desc}")
        M.append(f"- {term}: {desc}")
    M.append("")
    return "\n".join(L), "\n".join(M) + "\n"


def build_match_report(a_birth: date, a_h: int, a_m: int, a_sex: str,
                       a_city: str, b_birth: date, b_h: int, b_m: int,
                       b_sex: str, b_city: str, r: dict | None = None) -> tuple[str, str]:
    """(터미널 텍스트, md 텍스트) 반환. 두 사람의 개인정보는 포함하지 않음."""
    from .matchmaking import compatibility
    if r is None:
        r = compatibility(a_birth, a_h, a_m, a_sex, a_city,
                          b_birth, b_h, b_m, b_sex, b_city)
    L = []
    L.append("=" * 46)
    L.append(f"  두 사람 궁합 ({r['score']}점 / 100점)")
    L.append(DISCLAIMER)
    L.append("=" * 46)
    L.append(f"\n[종합] {r['head']}")
    for p in r["story"]:
        L.append(f"  {p}")
    L.append(f"  · 나: 일간 {r['a_ilgan']}, 일지 {r['a_day_branch']}, "
             f"띠 {r['a_animal']}, 명궁 {r['a_mingong']}, 태양 {r['a_sun']}")
    L.append(f"  · 상대: 일간 {r['b_ilgan']}, 일지 {r['b_day_branch']}, "
             f"띠 {r['b_animal']}, 명궁 {r['b_mingong']}, 태양 {r['b_sun']}")
    L.append("\n[잘 맞는 점]")
    for x in r["strengths"] or ["특별히 도드라지는 점 없이 잔잔하게 맞는 흐름"]:
        L.append(f"  · {x}")
    if r["minus"]:
        L.append("\n[조심할 점]")
        for x in r["cautions"]:
            L.append(f"  · {x}")
    if r["info"]:
        L.append("\n[참고]")
        for x in r["info"]:
            L.append(f"  · {x}")
    L.append("\n" + DISCLAIMER)
    text = "\n".join(L)

    M = []
    M.append("# 두 사람 궁합")
    M.append("")
    M.append("> " + DISCLAIMER)
    M.append("> 이 파일에는 두 사람의 생년월일·시간·성별·도시를 저장하지 않습니다.")
    M.append("")
    M.append(f"- 궁합 점수: **{r['score']}점 / 100점**, {r['head']}")
    M.append("")
    M.append("## 두 사람 이야기")
    for p in r["story"]:
        M.append(f"- [이야기] {p}")
    M.append("")
    M.append("## 잘 맞는 점")
    for x in r["strengths"] or ["특별히 도드라지는 점 없이 잔잔하게 맞는 흐름"]:
        M.append(f"- {x}")
    if r["minus"]:
        M.append("")
        M.append("## 조심할 점")
        for x in r["cautions"]:
            M.append(f"- {x}")
    if r["info"]:
        M.append("")
        M.append("## 참고")
        for x in r["info"]:
            M.append(f"- {x}")
    md = "\n".join(M) + "\n"
    return text, md


def build_pick_report(birth: date, hour: int, minute: int, sex: str,
                      city: str, start: date, end: date,
                      domain: str = "total", top: int = 5,
                      r: dict | None = None) -> tuple[str, str]:
    """(터미널 텍스트, md 텍스트) 반환. 개인정보는 포함하지 않음."""
    from .taekil import pick_dates
    if r is None:
        r = pick_dates(birth, hour, minute, sex, city, start, end, domain)
    dom_name = {"total": "총운", "love": "연애", "career": "직장", "money": "금전"}[domain]
    L = []
    L.append("=" * 46)
    L.append(f"  길일 고르기 ({r['start']}~{r['end']}, {dom_name} 기준)")
    L.append(DISCLAIMER)
    L.append("=" * 46)
    L.append(f"\n[상위 {top}일]")
    for p in r["story"]:
        L.append(f"  {p}")
    for row in r["rows"][:top]:
        L.append(f"  {row['rank']}위: {row['label']} {row['ganzhi']} "
                 f"(연애 {row['love']}·직장 {row['career']}·금전 {row['money']})")
    L.append("\n[전체 표]")
    for row in r["rows"]:
        L.append(f"  - {row['label']} {row['ganzhi']}: 연애 {row['love']}점·"
                 f"직장 {row['career']}점·금전 {row['money']}점")
    L.append("\n" + DISCLAIMER)
    text = "\n".join(L)

    M = []
    M.append(f"# 길일 고르기 ({r['start']}~{r['end']}, {dom_name} 기준)")
    M.append("")
    M.append("> " + DISCLAIMER)
    M.append("> 이 파일에는 생년월일·시간·성별·도시를 저장하지 않습니다.")
    M.append("")
    M.append("## 상위 일자")
    for p in r["story"]:
        M.append(f"- [이야기] {p}")
    M.append("")
    for row in r["rows"][:top]:
        M.append(f"- {row['rank']}위: {row['label']} {row['ganzhi']} "
                 f"(연애 {row['love']}·직장 {row['career']}·금전 {row['money']})")
    M.append("")
    M.append("## 전체 표")
    for row in r["rows"]:
        best = max((("연애", row["love"]), ("직장", row["career"]), ("금전", row["money"])),
                   key=lambda t: t[1])[0]
        M.append(f"- [길일] {row['date']} | {row['ganzhi']} | 연애 {row['love']} | "
                 f"직장 {row['career']} | 금전 {row['money']} | 으뜸 {best}")
    md = "\n".join(M) + "\n"
    return text, md


def _parse_hm(value: str) -> tuple[int | None, int]:
    """HH:MM 또는 '모름' → (시|None, 분)."""
    if value.strip() in ("모름", "unknown", "모름시간", ""):
        return None, 0
    h, m = (int(x) for x in value.strip().split(":"))
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("시간은 00:00~23:59 사이여야 해")
    return h, m


def _sex_arg(value: str) -> str:
    import argparse
    try:
        return normalize_sex(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from None


def main(argv=None):
    args = parse_args(argv)
    from .manseryuk import zi_mode
    with zi_mode(getattr(args, "zi", "next")):
        _main(args)


def _main(args):
    if args.cmd == "form":
        from .web import serve
        serve(args.port, args.host)
        return
    if args.cmd == "match":
        try:
            ab = parse_birth_date(args.birth, args.calendar, args.leap)
            bb = parse_birth_date(args.birth2, args.calendar2, args.leap2)
            ah, am = _parse_hm(args.birth_time)
            bh, bm = _parse_hm(args.birth2_time)
        except (ValueError, TypeError) as e:
            raise SystemExit(f"입력 오류: {e}\n예: --birth 1995-02-28 --birth2 1997-06-15")
        text, md = build_match_report(ab, ah, am, args.sex, args.city,
                                      bb, bh, bm, args.sex2, args.city2)
        print(text)
        if not args.no_save:
            fname = f"match_{date.today().strftime('%Y%m%d')}.md"
            with open(fname, "w", encoding="utf-8") as f:
                f.write(md)
            print(f"\n[저장] {fname} (개인정보 제외)")
        return
    if args.cmd == "pick":
        try:
            birth = parse_birth_date(args.birth, args.calendar, args.leap)
            hh, mm = _parse_hm(args.birth_time)
            start = datetime.strptime(args.from_date, "%Y-%m-%d").date()
            end = datetime.strptime(args.to_date, "%Y-%m-%d").date()
        except (ValueError, TypeError) as e:
            raise SystemExit(f"입력 오류: {e}\n예: --birth 1995-02-28 --from 2026-10-01 --to 2026-10-31")
        try:
            text, md = build_pick_report(birth, hh, mm, args.sex, args.city,
                                         start, end, args.domain, args.top)
        except ValueError as e:
            raise SystemExit(str(e))
        print(text)
        if not args.no_save:
            fname = f"pick_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.md"
            with open(fname, "w", encoding="utf-8") as f:
                f.write(md)
            print(f"\n[저장] {fname} (개인정보 제외)")
        return
    if args.interactive or not args.birth:
        if not args.birth and not args.interactive:
            # 인자 없이 실행 → 대화형으로 유도 (단, --birth 없으면 에러 대신 질문)
            ans = interactive_ask()
        else:
            ans = interactive_ask()
        for k in ("birth", "calendar", "leap", "birth_time", "sex", "city"):
            setattr(args, k, ans[k])

    try:
        birth = parse_birth_date(args.birth, args.calendar, args.leap)
    except (ValueError, TypeError) as e:
        raise SystemExit(f"생년월일 입력 오류: {e}\n"
                         "예: --birth 1995-02-28 (음력이면 --calendar lunar, 윤달이면 --leap)")
    if args.calendar == "lunar":
        print(f"(음력 {'윤달 ' if args.leap else ''}{args.birth} → 양력 {birth.isoformat()} 로 바꿔 계산해)")
    try:
        hh, mm = _parse_hm(args.birth_time)
    except ValueError:
        raise SystemExit("birth-time 형식이 잘못됐습니다. 예: --birth-time 12:00 또는 모름")

    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target = date.today()
    if args.tomorrow:
        target = target + timedelta(days=1)

    try:
        text, md = build_report(birth, hh, mm, args.sex, args.city, target,
                                args.domain, args.lifetime)
    except ValueError as e:
        raise SystemExit(f"입력 오류: {e}")
    print(text)
    if not args.no_save:
        fname = f"report_{target.strftime('%Y%m%d')}.md"
        with open(fname, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"\n[저장] {fname} (개인정보 제외)")
