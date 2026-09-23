"""narrate.py, 상세 서사 생성 (로컬·결정적).

iztro 14보조성·37잡성 해설을 토대로 보조별·궁·행성·어스펙트를
점술가가 풀어주듯 문장으로 바꾼다. 전부 순우리말 서술.
"""
from __future__ import annotations


def _eun(word: str) -> str:
    return "은" if (ord(word[-1]) - 0xAC00) % 28 != 0 else "는"


# 14주성 이름표 (lifetime.MAIN14와 동일, 순환참조 방지용 복제)
MAIN14 = ("자미", "천기", "태양", "무곡", "천동", "염정", "천부",
          "태음", "탐랑", "거문", "천상", "천량", "칠살", "파군")


def narrate_slice_row(row: str) -> str:
    """'본궁 관록(병자): 무곡,천부,천괴' 같은 행을 풀어준다."""
    try:
        left, stars = row.split(": ", 1)
        tag, rest = left.split(" ", 1)
        name = rest
        names = [s.strip() for s in stars.split(",") if s.strip()]
    except ValueError:
        return row
    mains = [s for s in names if s in MAIN14]
    aux = [s for s in names if s not in MAIN14 and s in AUX_TALK]
    if mains:
        s = (f"{tag} {name} 자리에는 {', '.join(mains)}{_eun(mains[-1])} 앉아 있어. "
             f"{STAR_TALK[mains[0]]}")
    else:
        s = f"{tag} {name} 자리는 주성이 비어 있어 건너편 기운을 빌려 쓰는 때야."
    if aux:
        s += " 함께 있는 " + ", ".join(f"{a}({AUX_TALK[a]})" for a in aux[:3]) + "."
    return s

# 십신 쉬운 말
GOD_SHORT = {
    "비견": "곁을 지키는 동료 같은 힘", "겁재": "불붙는 승부욕 같은 힘",
    "식신": "표현하고 만드는 힘", "상관": "튀는 재능과 말",
    "정재": "착실히 모이는 돈", "편재": "돌고 도는 돈",
    "정관": "믿음 주는 책임", "편관": "세게 밀어붙이는 힘",
    "정인": "든든한 뒷받침", "편인": "엉뚱한 영감과 몰입",
}
# 지지 관계 쉬운 말
REL_TALK = [("육합", "손잡는 합"), ("삼합", "큰 팀을 이루는 합"),
            ("육충", "정면으로 부딪치는 충"), ("상형", "얽매는 형"),
            ("삼형", "얽매는 형"), ("파", "깨뜨리는 파"), ("해", "삐걱이는 해")]


def _has_jongseong(word: str) -> bool:
    return (ord(word[-1]) - 0xAC00) % 28 != 0


def _eun(word: str) -> str:
    return "은" if _has_jongseong(word) else "는"


def _wa(word: str) -> str:
    return "과" if _has_jongseong(word) else "와"


def _rel_text(rels: list[str]) -> str:
    out = []
    for r in rels:
        for key, talk in REL_TALK:
            if key in r:
                out.append(talk)
                break
    return ", ".join(out) if out else "특별히 부딪치지도 손잡지도 않는 무난한 사이"


# 14주성 쉬운 말
STAR_TALK = {
    "자미": "무게 잡고 중심을 잡는 별이라 맡은 자리에서 우두머리 역할을 하게 된다",
    "천기": "눈치 빠르고 대처가 빠른 별이라 머리 쓰는 일에 통한다",
    "태양": "밝고 나서기 좋아하는 별이라 사람 앞에 서면 빛난다",
    "무곡": "실속 챙기고 밀어붙이는 별이라 결과로 말한다",
    "천동": "순하고 편안한 별이라 복이 따르고 사람을 편하게 한다",
    "염정": "자존심 세고 원칙 있는 별이라 흐트러지지 않는다",
    "천부": "곳간 지키듯 안정적인 별이라 모으고 지키는 데 통한다",
    "태음": "조용하고 섬세한 별이라 살뜰히 챙기는 데 통한다",
    "탐랑": "끼 많고 사교적인 별이라 판을 벌리면 사람이 모인다",
    "거문": "말 잘하고 따지는 별이라 분석하고 설득하는 데 통한다",
    "천상": "둥글게 중재하는 별이라 싸움을 말리는 역할을 하게 된다",
    "천량": "어른스럽게 돌보는 별이라 가르치고 보살피는 데 통한다",
    "칠살": "앞장서서 돌파하는 별이라 개척하는 일에 통한다",
    "파군": "판을 엎고 새로 만드는 별이라 변화가 많은 때와 맞는다",
}
# 사화 쉬운 말
HUA_TALK = {"록": "복과 기회가 붙는 자리", "권": "힘과 주도권이 붙는 자리",
            "과": "인정과 명예가 붙는 자리", "기": "막힘과 과제가 붙는 자리"}
# 목성·토성 별자리원소별 쉬운 말
JUP_TALK = {"불": "도전하고 벌리면 커지는 때", "흙": "심은 게 결실로 돌아오는 때",
            "공기": "사람과 정보가 문을 여는 때", "물": "마음을 돌보면 채워지는 때"}
SAT_TALK = {"불": "추진력을 시험받는 때", "흙": "결실을 매듭짓는 때",
            "공기": "관계를 정리하는 때", "물": "마음을 단단히 하는 때"}

# 보조별 쉬운 말 (iztro 14보조성·37잡성 해설 종합)
AUX_TALK = {
    "좌보": "앞에서 끌어주는 귀인 기운이라 남을 세우는 역할을 하게 돼",
    "우필": "뒤에서 받쳐주는 귀인 기운이라 부드럽게 중재하는 역할을 하게 돼",
    "천괴": "급할 때 나타나는 해결사 기운이라 리더 노릇을 하게 돼",
    "천월": "문제를 근본부터 푸는 지혜 기운이라 기획과 해결에 통한다",
    "문창": "정통 학문과 문서 기운이라 공부와 기록에 통한다",
    "문곡": "예술과 표현 끼가 있어 말과 글로 풀어내는 데 통한다",
    "지공": "생각이 많아 실행이 늦어지는 기운이지만 아이디어는 풍부하다",
    "지겁": "돈 앞에서 까다로운 기운이라 원칙대로 버는 데 통한다",
    "화성": "생각부터 앞서는 불같은 기운이라 속도가 붙는다",
    "영성": "속으로 삭히는 기운이라 꼼꼼하게 따지는 데 통한다",
    "타라": "결정을 미루고 맴도는 기운이지만 파고들면 전문가가 된다",
    "경양": "몸이 먼저 나가는 행동파 기운이라 추진력이 붙는다",
    "천마": "가만 못 있고 돌아다니는 기운이라 변화와 이동이 따른다",
    "녹존": "본전 지키는 신중한 돈 기운이라 안정감이 생긴다",
    "홍란": "다정하고 단아한 매력 기운이다",
    "천희": "웃는 얼굴로 붙임성을 더하는 기운이다",
    "천요": "주목받는 끼로 모임의 중심에 서게 하는 기운이다",
    "함지": "이성을 끄는 은근한 매력 기운이다",
    "고진": "혼자 있고 싶어하는 기운이다",
    "과숙": "말수 적고 속으로 삭히는 기운이다",
    "천형": "엄격하고 웃음기 없는 인상을 주는 기운이다",
    "용지": "손재주 같은 단단한 기술 기운이다",
    "봉각": "예술 감각과 멋을 더하는 기운이다",
    "천재": "눈치 빠르고 배우기 빠른 기운이다",
    "천수": "차분하고 안정적인 기운이다",
    "대보": "정신적으로 받쳐주는 도움 기운이다",
    "봉고": "물질적으로 받쳐주는 도움 기운이다",
    "삼태": "멋과 체면을 차리는 기운이다",
    "팔좌": "즐기고 누리는 여유 기운이다",
    "은광": "받은 만큼 갚는 의리 기운이다",
    "천귀": "작은 귀인이 되어 돕고 인정받는 기운이다",
    "천곡": "애잔한 분위기를 더하는 기운이다",
    "천허": "속으로 끙끙 앓는 기운이라 쉬어주면 풀린다",
    "천공": "엉뚱한 전환이 오는 기운이라 돌발에 유연하면 좋다",
    "화개": "신비로운 것에 끌리는 철학자 기운이다",
    "절공": "막히면 뚫고 가는 끈기 기운이다",
}

# 12궁 쉬운 말
PALACE_TALK = {
    "명궁": "나 자신과 인생 방향이 담긴 자리",
    "형제": "형제와 가까운 친구가 담긴 자리",
    "부처(배우자)": "배우자와 연애가 담긴 자리",
    "자녀": "자녀와 아랫사람이 담긴 자리",
    "재백": "돈과 재물이 담긴 자리",
    "질액": "건강과 몸이 담긴 자리",
    "천이": "바깥생활과 이동이 담긴 자리",
    "노복": "동료와 거래처가 담긴 자리",
    "관록": "직업과 일이 담긴 자리",
    "전택": "집과 살림이 담긴 자리",
    "복덕": "마음의 평화와 취미가 담긴 자리",
    "부모": "부모와 윗사람이 담긴 자리",
}

# 행성 쉬운 말
BODY_TALK = {
    "태양": "삶의 방향을 비추는", "달": "감정을 어루만지는",
    "수성": "말과 생각을 오가는", "금성": "사랑과 취향을 가꾸는",
    "화성": "행동력을 불태우는", "목성": "기회를 넓히는",
    "토성": "책임을 다지는",
}
# 하우스 쉬운 말
HOUSE_TALK = {
    1: "나 자신", 2: "돈과 소유", 3: "소통과 배움", 4: "집과 뿌리",
    5: "연애와 창작", 6: "일과 건강", 7: "인연과 계약", 8: "공유와 변화",
    9: "철학과 여행", 10: "직업과 명예", 11: "친구와 희망", 12: "휴식과 정리",
}
# 어스펙트 쉬운 말
ASPECT_TALK = {
    "합": "딱 붙어 함께 가", "육합": "가볍게 손잡고",
    "형": "직각으로 긴장하며", "삼합": "넓게 어울리며", "충": "마주 보고 팽팽하게",
}
# 오행국 쉬운 말
GUO_NAME = {2: "수이국", 3: "목삼국", 4: "금사국", 5: "토오국", 6: "화육국"}

# 십신 쉬운 말
GOD_MEAN = {    "비견": "곁을 지키는 동료 같은 사이야.", "겁재": "불붙는 승부욕이 이는 사이야.",
    "식신": "표현하고 만드는 힘이 통하는 사이야.", "상관": "튀는 재능과 말이 오가는 사이야.",
    "정재": "착실히 모이는 돈으로 통하는 사이야.", "편재": "돌고 도는 돈으로 통하는 사이야.",
    "정관": "믿음 주는 책임으로 통하는 사이야.", "편관": "세게 밀어붙이는 힘으로 통하는 사이야.",
    "정인": "든든한 뒷받침이 오가는 사이야.", "편인": "엉뚱한 영감이 오가는 사이야.",
}

GUO_NAME = {2: "수이국", 3: "목삼국", 4: "금사국", 5: "토오국", 6: "화육국"}


def ziwei_puli(ma: dict) -> list[str]:
    """자미두수 명반 풀이문. md·터미널 공용."""
    zw = ma["ziwei"]
    if zw is None:
        return ["시간 미상이라 자미두수 명반 풀이는 제외, 사주 대운으로 봐."]
    out = []
    out.append(f"명반 전체 바탕은 {GUO_NAME[zw['guo']]} 기운이야. "
               f"나를 보는 명궁({zw['mingong']} 자리)에는 {zw['ming_main']}이 앉아 있어. "
               f"{STAR_TALK.get(zw['ming_main'], '자기 자리를 지키는 별이야')} "
               f"신궁({zw['shengong']})은 중년 이후 겉모습을 보는 자리야.")
    peach = f" 여기에 도화성 {', '.join(zw['peach'])}이 함께 있어 설렘이 엮이기 쉬워." \
        if zw["peach"] else ""
    out.append(f"배우자를 보는 부처궁에는 {zw['spouse_main']}이 앉아 있어. "
               f"{STAR_TALK.get(zw['spouse_main'], '자기 색이 분명한 별이야')}{peach}")
    for hua, star in (("록", zw["sihua"]["록"]), ("권", zw["sihua"]["권"]),
                      ("과", zw["sihua"]["과"]), ("기", zw["sihua"]["기"])):
        pal = next((p["name"] for p in zw["palaces"] if star in p["stars"]), "어딘가")
        out.append(f"태어난 해의 기운으로 {star}에는 {HUA_TALK[hua]} "
                   f"그래서 {pal} 쪽 일이 풀리기 쉬워.")
    cur = next((p for p in zw["palaces"]
                if p["daxian"] and p["daxian"][0] <= zw["xusui"] <= p["daxian"][1]), None)
    if cur:
        out.append(f"지금 {zw['xusui']}세는 {cur['name']} 대운({cur['daxian'][0]}~{cur['daxian'][1]}세) "
                   f"한가운데야. 이 궁에는 {', '.join(cur['stars'])}이 앉아 있어.")
    out.append(f"올해 유년은 {zw['liunian']['branch']} 자리({zw['liunian']['stem']}의 해)에 걸려 있어. "
               f"올해 사화는 록{zw['liunian']['sihua']['록']} 권{zw['liunian']['sihua']['권']} "
               f"과{zw['liunian']['sihua']['과']} 기{zw['liunian']['sihua']['기']}로 돌아.")
    return out


def astro_puli(ma: dict) -> list[str]:
    """점성술 풀이문. md·터미널 공용."""
    out = []
    if ma.get("hour_unknown"):
        out.append("시간 미상이라 하우스·상승궁 풀이는 제외, 행성 자리만 봐.")
        for body, p in ma["astro"]["positions"].items():
            out.append(f"{BODY_KR[body]}은 {p['sign']}에 머물러 있어.")
        for a in ma["astro"]["aspects"]:
            out.append(narrate_aspect(a))
        return out
    for body, p in ma["astro"]["positions"].items():
        out.append(narrate_planet(BODY_KR[body], p["sign"],
                                  ma["astro"]["houses"][BODY_KR[body]],
                                  p["retro"], p["cusp"]))
    for a in ma["astro"]["aspects"]:
        out.append(narrate_aspect(a))
    return out


BODY_KR = {"sun": "태양", "moon": "달", "mercury": "수성", "venus": "금성",
           "mars": "화성", "jupiter": "목성", "saturn": "토성"}


def match_puli(ma: dict) -> list[str]:
    """인연 풀이문. md·터미널 공용."""
    from .match import STAGE_LOVE
    out = [
        f"배우자 자리에는 '{ma['god']}' 기운이 앉아 있어. {GOD_SHORT[ma['god']]}. {ma['side']}",
        f"태어난 날의 기운 단계는 '{ma['stage']}'이야. {STAGE_LOVE[ma['stage']]}",
        ("시간 미상이라 부처궁 주성 풀이는 제외."
         if ma.get("hour_unknown") else
         f"부처궁 주성 {ma['ziwei_main']}은 {STAR_TALK.get(ma['ziwei_main'], '자기 색이 분명한 별이야')}"),
        f"금성(사랑과 취향)은 {ma['venus']}, 달(감정)은 {ma['moon']}에 머물러. "
        f"{ma['venus_detail']['style']} {ma['moon_need']}",
        f"만나기 쉬운 자리는 {', '.join(ma['meet_top3'])}이야.",
    ]
    if ma["dohwa_lines"]:
        out.append("도화 기운으로 " + " 그리고 ".join(ma["dohwa_lines"]))
    out.append(ma["hong_line"])
    return out


def narrate_palace(p: dict, mains: list[str], xusui_now: int | None = None) -> str:
    """한 궁을 두세 문장으로 풀어준다. xusui_now가 있으면 대운 시제를 덧붙인다."""
    name = p["name"]
    base = PALACE_TALK.get(name, "인생 한 영역이 담긴 자리")
    if mains:
        main = mains[0]
        s = (f"{name} 자리({p['stem_kr']}{p['branch_kr']})는 {base}야. "
             f"여기 주성 {main}{_eun(main)} {STAR_TALK[main]}")
        if len(mains) > 1:
            s += f" 같이 있는 {', '.join(mains[1:])}도 힘을 보태."
        else:
            s += "."
    else:
        s = (f"{name} 자리({p['stem_kr']}{p['branch_kr']})는 {base}야. "
             f"주성이 비어 있어 건너편 기운을 빌려 쓰는 때야.")
    aux = [x for x in p["stars"] if x in AUX_TALK]
    if aux:
        s += " 함께 있는 " + ", ".join(
            f"{a}({AUX_TALK[a]})" for a in aux[:4]) + "."
    if p["hua"]:
        s += " 여기에 " + ", ".join(
            f"{s}에는 {HUA_TALK[h]}" for s, h in p["hua"].items()) + "."
    if p.get("daxian"):
        _a, _b = p["daxian"][0], p["daxian"][1]
        s += f" 이 궁의 대운은 {_a}~{_b}세에 도래해."
        if xusui_now is not None:
            if xusui_now < _a:
                s += " 아직 오지 않은 때라 씨를 뿌리며 준비하는 마음이 좋아."
            elif xusui_now > _b:
                s += " 이미 지나간 때라 그때 다져 둔 것이 지금의 밑거름이 돼."
            else:
                s += " 바로 지금 지나가는 중인 때라 이 궁의 기운이 가장 가까이 와 있어."
    return s


def narrate_planet(body_kr: str, sign: str, house: int,
                   retro: bool, cusp: bool) -> str:
    s = (f"{body_kr}은 지금 {sign}에 머물러 {house}번 하우스 칸({HOUSE_TALK[house]})에서 "
         f"{BODY_TALK[body_kr]} 중이야.")
    if retro:
        s += " 지금은 역행 중이라 되돌아보고 고치기 좋은 때야."
    if cusp:
        s += " 별자리 경계에 걸려 있어 다음 자리 기운도 살짝 섞여."
    return s


def narrate_aspect(text: str) -> str:
    """'태양–목성 형(85.8°)' 같은 문자열을 풀어준다."""
    for name, talk in ASPECT_TALK.items():
        if f" {name}(" in text:
            head, rest = text.split(f" {name}(", 1)
            deg = rest.rstrip(")").rstrip("°")
            return (f"{head}{_eun(head)} {talk} 있어. 각도는 {deg}도야. "
                    f"{'가까울수록 힘이 세게 실려.' if name in ('합', '충') else '흐름을 타고 가면 돼.'}")
    return text


def rel_sentence(rels: list[str]) -> str:
    """관계 목록을 완성 문장으로. fallback 내장이라 사이 중복 없음."""
    out = []
    for r in rels:
        for key, talk in REL_TALK:
            if key in r:
                out.append(talk)
                break
    if not out:
        return "특별히 부딪치지도 손잡지도 않는 무난한 사이야."
    return ", ".join(out) + " 사이야."
