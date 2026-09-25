"""josa.py, 받침에 맞춰 조사를 고른다 ("천기를", "태양이", "쌍둥이자리야").

예전엔 조사를 고정으로 붙여서 "천기을", "태양은 앉아", "쌍둥이자리이야" 같은 문장이 나왔다.
"""
from __future__ import annotations

_PAIRS = {"이": ("이", "가"), "가": ("이", "가"), "은": ("은", "는"), "는": ("은", "는"),
          "을": ("을", "를"), "를": ("을", "를"), "과": ("과", "와"), "와": ("과", "와"),
          "아": ("아", "야"), "야": ("이야", "야"), "이야": ("이야", "야"),
          "으로": ("으로", "로"), "로": ("으로", "로"), "이라": ("이라", "라"), "라": ("이라", "라")}


def has_batchim(word: str) -> bool:
    """마지막 글자에 받침이 있나. 끝의 괄호 풀이는 떼고 본다 ("명궁(신 자리)" → "명궁")."""
    word = word.strip()
    while word.endswith(")") and "(" in word:
        word = word[:word.rindex("(")].rstrip()
    for ch in reversed(word):
        if ch in "]} '\"":
            continue
        code = ord(ch) - 0xAC00
        if 0 <= code < 11172:
            return code % 28 != 0
        if ch.isdigit():
            return ch in "013678"          # 영, 일, 삼, 육, 칠, 팔
        return False
    return False


def rieul(word: str) -> bool:
    ch = word.strip()[-1:]
    code = ord(ch) - 0xAC00 if ch else -1
    return 0 <= code < 11172 and code % 28 == 8


def j(word: str, josa: str) -> str:
    """word 에 알맞은 조사를 붙인다. j('천기', '을') → '천기를'."""
    a, b = _PAIRS.get(josa, (josa, josa))
    if josa in ("으로", "로") and rieul(word):
        return word + "로"
    return word + (a if has_batchim(word) else b)
