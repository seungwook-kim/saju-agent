"""portrait.py, 탭별 분위기 삽화. 계산 결과를 장면 묘사로 바꿔 로컬 이미지 서버(imagegen)에 부탁한다.

예언이 아니라 화면을 꾸미는 삽화다. 카드에는 '계산 결과로 그린 분위기 이미지'라고 적는다.
- 인물의 인상: 자미두수 주성(부처궁·관록궁·재백궁·명궁)의 성격
- 배경·색감: 오행 (목 아침 공원, 화 노을, 토 카페, 금 하얀 도시, 수 비 오는 저녁)
- 인물 구성: 연애는 반대 성별 비슷한 나이, 직장은 연배 있는 멘토, 금전은 여유로운 사람,
  오늘은 나와 같은 성별·나이, 평생은 나의 20·40·60대
개인정보(생년월일·이름·도시)는 묘사에 넣지 않는다. 시드는 계산 결과의 해시라 같은 사람은 같은 그림.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request

from . import content_store

IMAGE_URL = os.environ.get("LOVE_FORTUNE_IMAGE_URL", "http://127.0.0.1:8766")

STAR_LOOK = {
    "자미": "dignified confident presence, calm authority", "천기": "bright clever eyes, quick witty smile",
    "태양": "radiant warm outgoing smile", "무곡": "determined steady gaze, practical style",
    "천동": "gentle easygoing soft smile", "염정": "charismatic striking eyes, artistic style",
    "천부": "composed generous calm expression", "태음": "soft elegant graceful calm",
    "탐랑": "charming playful expressive smile", "거문": "thoughtful articulate intelligent look",
    "천상": "kind diplomatic neat appearance", "천량": "mature caring warm eyes",
    "칠살": "bold decisive sharp features", "파군": "adventurous free-spirited unconventional style",
}
ELEM_SCENE = {
    "목": "green park in soft morning light, fresh leaves, pastel green tones",
    "화": "warm golden sunset street, glowing light, peach and coral tones",
    "토": "cozy wooden cafe interior, warm earthy tones, soft window light",
    "금": "minimal bright white modern space, clean lines, silver and ivory tones",
    "수": "rainy evening city with soft bokeh lights, calm blue tones",
}
BASE = ("photo, candid portrait, Korean person, natural skin texture, soft pastel color grading, "
        "85mm lens, shallow depth of field, gentle film grain, tasteful, fully clothed")


def _age_word(age: int) -> str:
    if age < 23:
        return "early 20s"
    if age < 30:
        return "late 20s"
    if age < 36:
        return "early 30s"
    if age < 45:
        return "late 30s"
    if age < 55:
        return "late 40s"
    return "60s"


def _person(sex_kr: str, opposite: bool = False) -> str:
    male = (sex_kr == "남성") != opposite
    return "man" if male else "woman"


def _main_star(facts: dict, palace: str) -> str | None:
    zw = facts["natal"].get("ziwei")
    if not zw:
        return None
    p = next((x for x in zw["palaces"] if x["name"] == palace), None)
    if not p:
        return None
    return next((s for s in p["stars"] if s in STAR_LOOK), None)


def _elem_of_sign(sign: str) -> str:
    fire, earth, air = ("양자리", "사자자리", "사수자리"), ("황소자리", "처녀자리", "염소자리"), ("쌍둥이자리", "천칭자리", "물병자리")
    return "화" if sign in fire else "토" if sign in earth else "금" if sign in air else "수"


def scenes(tab: str, facts: dict) -> list[dict]:
    """탭의 삽화 목록 [{slot, prompt, seed, caption}]."""
    meta = facts["meta"]
    age, sex = int(meta["age"]), meta["sex"]
    ilgan_e = facts["natal"]["ilgan_element"]
    out = []

    def add(slot, who, look, elem, caption, extra=""):
        prompt = f"{BASE}, {who}, {look}, {ELEM_SCENE[elem]}{', ' + extra if extra else ''}"
        seed = int(hashlib.sha256((tab + slot + prompt + facts["natal"]["day_pillar"]).encode()).hexdigest()[:8], 16)
        out.append({"slot": slot, "prompt": prompt, "seed": seed, "caption": caption})

    if tab == "love":
        star = _main_star(facts, "부처(배우자)")
        venus = facts["love"]["venus"]["sign"]
        look = STAR_LOOK.get(star, "warm friendly smile")
        add("partner", f"{_person(sex, opposite=True)} in {_age_word(age)}", look, _elem_of_sign(venus),
            f"잘 맞는 상대의 분위기 (부처궁 {star or '미상'} · 금성 {venus})", "looking slightly away, romantic mood")
    elif tab == "career":
        star = _main_star(facts, "관록")
        add("mentor", f"{_person(sex)} mentor in late 40s, smart casual office attire",
            STAR_LOOK.get(star, "reliable warm expression"), ilgan_e,
            f"일에서 힘이 되는 사람의 분위기 (관록궁 {star or '미상'})", "modern workplace, confident posture")
    elif tab == "money":
        star = _main_star(facts, "재백")
        add("partner", f"{_person(sex)} in {_age_word(age + 8)}, elegant relaxed outfit",
            STAR_LOOK.get(star, "composed satisfied smile"), "금" if ilgan_e == "목" else ilgan_e,
            f"재물 흐름의 분위기 (재백궁 {star or '미상'})", "relaxed prosperous atmosphere")
    elif tab == "today":
        elem = facts["today"]["element"]
        add("me", f"{_person(sex)} in {_age_word(age)}, everyday outfit",
            STAR_LOOK.get(_main_star(facts, "명궁"), "natural relaxed expression"), elem,
            f"오늘의 나 (오늘 {elem} 기운)", "walking, candid daily life moment")
    elif tab == "life":
        star = _main_star(facts, "명궁")
        look = STAR_LOOK.get(star, "natural expression")
        # 나이만 적으면 모델이 다 젊게 그려서, 연대마다 눈에 보이는 나이 단서를 붙인다
        ages = (("20s", "young adult in mid 20s, youthful fresh face, casual student style", "20대"),
                ("40s", "middle-aged in mid 40s, subtle fine lines around eyes, mature refined style", "40대"),
                ("60s", "senior in late 60s, gray silver hair, visible wrinkles, elegant older style", "60대"))
        for slot, who, cap in ages:
            add(slot, f"{_person(sex)}, {who}", look, ilgan_e, f"{cap}의 나 (분위기)", "warm light")
    return out


def _post(path: str, obj: dict, timeout: float) -> dict:
    req = urllib.request.Request(IMAGE_URL + path, data=json.dumps(obj).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def server_up() -> bool:
    try:
        with urllib.request.urlopen(IMAGE_URL + "/healthz", timeout=2) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def render(tab: str, slot: str, facts: dict, timeout: float = 180) -> dict:
    """삽화 하나. {status: ready|off|error, url, caption}."""
    sc = next((s for s in scenes(tab, facts) if s["slot"] == slot), None)
    if sc is None:
        raise ValueError("없는 삽화")
    key = hashlib.sha256((sc["prompt"] + str(sc["seed"])).encode()).hexdigest()
    hit = content_store.get_portrait(key)
    if hit and hit.get("file"):
        return {"status": "ready", "url": f"/img/{hit['file']}", "caption": sc["caption"]}
    if not server_up():
        return {"status": "off", "caption": sc["caption"]}
    try:
        res = _post("/generate", {"prompt": sc["prompt"], "seed": sc["seed"],
                                  "width": 832, "height": 1024, "steps": 26}, timeout)
    except Exception:  # noqa: BLE001
        return {"status": "error", "caption": sc["caption"]}
    content_store.put_portrait(key, tab, slot, sc["prompt"], res["file"])
    return {"status": "ready", "url": f"/img/{res['file']}", "caption": sc["caption"]}
