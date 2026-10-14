"""injection.py, 프롬프트 인젝션 막기 (상담 채팅).

사용자가 친 글은 AI 에게 '자료'일 뿐 지시가 아니다. 여러 겹으로 막는다.
1) 정리(clean): 보이지 않는 문자·제어 문자를 지우고 길이를 자른다.
2) 알아보기(looks_like): 규칙 무시·역할 바꾸기·지시문 공개 요청·가짜 역할 표시는 AI 를 부르기 전에
   정해 둔 답으로 돌려보낸다 (토큰 0). 글자 사이에 공백·점·보이지 않는 문자를 끼우거나
   전각 글자, 라틴 글자와 똑같이 생긴 키릴·그리스 글자로 써도 같은 글로 본다.
3) 가두기(fence): AI 에 넣을 때 <질문>·<대화> 울타리 안에 한 줄로 넣고, 울타리를 닫는 꺾쇠를 바꾼다.
   줄바꿈으로 '상담사:' 같은 가짜 대화 줄을 만들 수 없다.
4) 서명(sign·verify): 대화 기록의 상담사 답은 서버가 서명한 것만 믿는다. 브라우저가 꾸민 답은 버린다.
5) 새는지 보기(leaks): 답에 시스템 지시문 문장이 그대로 들어 있으면 그 답을 버린다.

챕터 풀이에는 사용자가 친 글자가 들어가지 않아(계산한 사실표만) 이 모듈을 거치지 않는다.
특수 문자는 소스에서 보이지 않거나 헷갈리지 않게 코드포인트 숫자로만 둔다.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata

# 보이지 않거나 글 방향을 뒤집는 문자 (글자 사이에 끼워 거름망을 피하는 데 쓰인다)
_INVISIBLE_RANGES = (
    (0x00AD, 0x00AD), (0x034F, 0x034F), (0x061C, 0x061C), (0x115F, 0x1160), (0x17B4, 0x17B5),
    (0x180B, 0x180F), (0x200B, 0x200F), (0x202A, 0x202E), (0x2060, 0x206F), (0x3164, 0x3164),
    (0xFE00, 0xFE0F), (0xFEFF, 0xFEFF), (0xFFA0, 0xFFA0),
)
_INVISIBLE = re.compile("[" + "".join(chr(a) if a == b else chr(a) + "-" + chr(b)
                                      for a, b in _INVISIBLE_RANGES) + "]")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")      # 탭·줄바꿈은 남긴다
# 라틴 글자와 똑같이 생긴 키릴(0x04xx·0x05xx)·그리스(0x03xx) 글자 → 라틴 글자
_LOOKALIKE = {
    0x0430: "a", 0x0435: "e", 0x043E: "o", 0x0440: "p", 0x0441: "c", 0x0443: "y", 0x0445: "x",
    0x0456: "i", 0x0458: "j", 0x0455: "s", 0x0501: "d", 0x04BB: "h", 0x04CF: "l",
    0x03BF: "o", 0x03B1: "a", 0x03B5: "e", 0x03B9: "i", 0x03BA: "k", 0x03BD: "v", 0x03C1: "p",
    0x03C4: "t", 0x03C5: "u", 0x03C7: "x",
}
_FW_COLON = chr(0xFF1A)                                    # 전각 쌍점


def clean(text: str, limit: int) -> str:
    """보이지 않는 문자·제어 문자를 지우고 공백을 줄여 limit 글자로 자른다.

    NFKC 는 쓰지 않는다 (ㅋ·ㅎ 같은 낱자 자모를 다른 글자로 바꿔 버려서). 알아보기에서만 쓴다.
    """
    s = unicodedata.normalize("NFC", str(text or ""))
    s = _INVISIBLE.sub("", s)
    s = _CONTROL.sub(" ", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()[:limit]


def squash(text: str) -> str:
    """알아보기용: 전각·닮은 글자를 보통 글자로, 소문자로, 글자·숫자만 남긴다 (공백·점·기호 제거)."""
    s = unicodedata.normalize("NFKC", str(text or "")).lower()
    s = _INVISIBLE.sub("", s).translate(_LOOKALIKE)
    return "".join(ch for ch in s if ch.isalnum())


# ---------------------------------------------------------------- 알아보기

# 공백·기호를 뺀 글에서 찾는다. 운세 질문을 잘못 막지 않게 '앞의·모든·너의' 같은 꾸밈말이 붙은 경우만 잡는다
# ("상사가 내 지시를 무시해", "내 역할을 바꿔야 할까", "규칙적인 생활", "제한 없이 살아도 될까" 는 통과).
_Q = ("(?:이전|이전의|앞의|앞에|앞|위의|위에|위|기존|기존의|원래|원래의|모든|전부|처음|처음의|초기|숨겨진|숨은"
      "|시스템|너의|너는|넌|당신의|당신은|받은|주어진|설정된)")
_A = "(?:지시|지침|명령|규칙(?!적)|설정|제한|필터|검열)"
_A_SHOW = "(?:지시|지침|명령|규칙(?!적)|설정)"
_KO = [
    re.compile(_Q + ".?" + _A + ".{0,4}(?:무시|잊어|잊고|잊으|무효|해제|풀어|우회|어기|어겨|따르지마|따르지말|버려|지워)"),
    re.compile(_Q + ".?" + _A_SHOW + ".{0,4}(?:알려|보여|출력|공개|말해|그대로|복사|읊어|적어)"),
    re.compile("(?:너의|너는|넌|당신의|당신은)(?:역할|정체|설정|규칙)(?:을|를|은|는)?(?:바꿔|바꾸|변경|잊어|버려)"),
    re.compile("프롬프트|지시문|시스템메시지|시스템메세지|개발자모드|관리자모드|디버그모드|탈옥|역할극|검열없이|필터없이"
               "|흉내내|인척해"),
]
_EN = [
    re.compile(r"(?:ignore|disregard|forget|override|bypass|skip)(?:all|any|the|your|my|of|these|those)*"
               r"(?:previous|prior|above|earlier|preceding|system|original|initial|existing)?"
               r"(?:instructions?|prompts?|rules?|directions?|guidelines?|context|messages?)"),
    re.compile(r"(?:system|developer|hidden|initial|original|secret)(?:prompt|message|instructions?)"),
    re.compile(r"youarenow|fromnowon|pretendtobe|pretendyouare|roleplay|newinstructions?|newrules|doanythingnow"
               r"|danmode|developermode|godmode|jailbr[ea]k|unrestricted|nofilters?|norestrictions?|promptinjection"),
    re.compile(r"(?:reveal|print|repeat|show|output|tellme)(?:me)?(?:your|the)(?:system)?(?:prompt|instructions|rules)"),
]
# 기호를 남긴 채 봐야 하는 것: 역할 꼬리표, 대화 틀 흉내
_RAW = [
    re.compile(r"<\s*/?\s*(?:system|assistant|user|developer|instructions?|질문|대화|시스템|상담사)\b[^>]{0,20}>", re.I),
    re.compile(r"<\|[^|>]{1,24}\|>"),
    re.compile(r"\[\s*/?\s*(?:system|inst|assistant|시스템|상담사)\s*\]", re.I),
    re.compile(r"(?m)^\s*(?:system|assistant|developer|시스템|상담사|어시스턴트)\s*[:" + _FW_COLON + "]", re.I),
    re.compile(r"#{2,}\s*(?:instruction|system|지시|시스템)", re.I),
]


def looks_like(text: str) -> bool:
    """규칙을 바꾸거나 숨은 지시를 캐내려는 글로 보이면 True."""
    raw = unicodedata.normalize("NFKC", _INVISIBLE.sub("", str(text or "")))
    if any(p.search(raw) for p in _RAW):
        return True
    s = squash(text)
    return any(p.search(s) for p in _KO) or any(p.search(s) for p in _EN)


# ---------------------------------------------------------------- 가두기

def fence(text: str, limit: int = 900) -> str:
    """AI 프롬프트의 울타리 안에 넣을 한 줄. 줄바꿈과 꺾쇠를 없애 울타리를 닫거나 가짜 줄을 만들지 못하게."""
    s = clean(text, limit)
    s = re.sub(r"\s*\n\s*", " / ", s)
    return s.replace("<", "(").replace(">", ")")


# ---------------------------------------------------------------- 서명

def sign(key: bytes, token: str, text: str) -> str:
    """서버가 보낸 상담사 답의 서명 (결과 토큰에 묶인다)."""
    return hmac.new(key, (token + "\x00" + str(text)).encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def verify(key: bytes, token: str, text: str, sig: str) -> bool:
    return bool(sig) and hmac.compare_digest(sign(key, token, text), str(sig))


# ---------------------------------------------------------------- 새는지 보기

def leaks(reply: str, secret: str, window: int = 24) -> bool:
    """답에 secret(시스템 지시문)의 글자 window 개가 연달아 그대로 들어 있으면 True (공백·기호는 빼고 비교)."""
    r, s = squash(reply), squash(secret)
    if len(r) < window or len(s) < window:
        return False
    grams = {s[i:i + window] for i in range(len(s) - window + 1)}
    return any(r[i:i + window] in grams for i in range(len(r) - window + 1))
