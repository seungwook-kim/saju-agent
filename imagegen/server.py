"""server.py, 가상 인물 삽화를 만드는 로컬 이미지 서버 (Stable Diffusion XL, 이 PC 의 GPU).

사주 앱 본체는 표준라이브러리만 쓰므로, 무거운 이미지 생성은 이 별도 프로그램이 맡는다.
이 컴퓨터 안(127.0.0.1)에서만 열리고, 생년월일 같은 개인정보는 받지 않는다
(앱이 계산 결과로 만든 장면 묘사와 시드만 받는다).

    cd imagegen
    uv run python server.py --download   # 처음 한 번, 모델 받기 (약 7GB)
    uv run python server.py              # 서버 시작 (127.0.0.1:8766)

POST /generate  {"prompt", "negative", "seed", "width", "height", "steps"}
                → {"file": "<해시>.webp", "cached": bool, "seconds": float}
GET  /healthz   → {"ok": true, "loaded": bool, "model": "..."}

같은 요청(묘사·시드·크기)이면 저장해 둔 그림을 돌려준다.
모델은 기본 RealVisXL V5.0 (SDXL 기반 실사 모델, CreativeML Open RAIL++-M).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = Path(os.environ.get("LOVE_FORTUNE_PORTRAITS", ROOT / "data" / "portraits"))
MODEL = os.environ.get("LOVE_FORTUNE_IMAGE_MODEL", "SG161222/RealVisXL_V5.0")
PORT = int(os.environ.get("LOVE_FORTUNE_IMAGE_PORT", "8766"))
DEFAULT_NEG = ("lowres, blurry, deformed, bad anatomy, extra fingers, extra limbs, text, watermark, "
               "logo, nsfw, nude, cartoon, 3d render, disfigured, cross-eyed")

_PIPE = None
_GPU = threading.Lock()


def load():
    """모델을 한 번만 올린다."""
    global _PIPE
    if _PIPE is not None:
        return _PIPE
    import torch
    from diffusers import DPMSolverMultistepScheduler, StableDiffusionXLPipeline
    kw = dict(torch_dtype=torch.float16, use_safetensors=True)
    try:
        pipe = StableDiffusionXLPipeline.from_pretrained(MODEL, variant="fp16", **kw)
    except Exception:  # noqa: BLE001  fp16 변형이 없는 저장소
        pipe = StableDiffusionXLPipeline.from_pretrained(MODEL, **kw)
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(
        pipe.scheduler.config, use_karras_sigmas=True, algorithm_type="dpmsolver++")
    pipe.to("cuda")
    pipe.set_progress_bar_config(disable=True)
    _PIPE = pipe
    return pipe


def _key(req: dict) -> str:
    blob = json.dumps({k: req.get(k) for k in ("prompt", "negative", "seed", "width", "height", "steps")},
                      ensure_ascii=False, sort_keys=True)
    return hashlib.sha256((MODEL + blob).encode("utf-8")).hexdigest()[:32]


def generate(req: dict) -> dict:
    prompt = str(req.get("prompt", "")).strip()[:900]
    if not prompt:
        raise ValueError("prompt 가 비었어")
    req = {"prompt": prompt, "negative": str(req.get("negative") or DEFAULT_NEG)[:600],
           "seed": int(req.get("seed", 0)) % (2 ** 31),
           "width": int(req.get("width", 832)), "height": int(req.get("height", 1024)),
           "steps": max(10, min(40, int(req.get("steps", 26))))}
    if req["width"] % 8 or req["height"] % 8 or not (512 <= req["width"] <= 1344) or not (512 <= req["height"] <= 1344):
        raise ValueError("크기는 512~1344 사이 8의 배수")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    name = _key(req) + ".webp"
    path = OUT_DIR / name
    if path.exists():
        return {"file": name, "cached": True, "seconds": 0.0}
    import torch
    t0 = time.time()
    with _GPU:
        pipe = load()
        g = torch.Generator("cuda").manual_seed(req["seed"])
        img = pipe(prompt=req["prompt"], negative_prompt=req["negative"],
                   width=req["width"], height=req["height"],
                   num_inference_steps=req["steps"], guidance_scale=5.0, generator=g).images[0]
    tmp = path.with_suffix(".tmp.webp")
    img.save(tmp, "WEBP", quality=88, method=5)
    tmp.replace(path)
    return {"file": name, "cached": False, "seconds": round(time.time() - t0, 2)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj: dict, code: int = 200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/healthz":
            self._json({"ok": True, "loaded": _PIPE is not None, "model": MODEL})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/generate":
            self._json({"error": "not found"}, 404)
            return
        try:
            n = int(self.headers.get("Content-Length", 0) or 0)
            if n > 20_000:
                raise ValueError("요청이 너무 커")
            req = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            self._json(generate(req))
        except ValueError as e:
            self._json({"error": str(e)}, 400)
        except Exception as e:  # noqa: BLE001
            print(f"[생성 오류] {type(e).__name__}: {e}", file=sys.stderr)
            self._json({"error": "생성 실패"}, 500)


def main() -> int:
    ap = argparse.ArgumentParser(description="가상 인물 삽화 로컬 서버")
    ap.add_argument("--download", action="store_true", help="모델만 받고 끝낸다")
    ap.add_argument("--warm", action="store_true", help="시작하자마자 모델을 GPU 에 올린다")
    args = ap.parse_args()
    if args.download:
        from huggingface_hub import snapshot_download
        try:
            snapshot_download(MODEL, allow_patterns=["*.json", "*.txt", "*fp16.safetensors",
                                                     "tokenizer*/*", "scheduler/*"])
        except Exception:  # noqa: BLE001
            snapshot_download(MODEL)
        load()
        print("모델 준비 완료:", MODEL)
        return 0
    if args.warm:
        # 모델을 올리는 동안에도 /healthz 는 답하게 따로 올린다 (감시 프로그램이 죽은 줄 알지 않게)
        def _warm():
            with _GPU:
                load()
        threading.Thread(target=_warm, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    srv.daemon_threads = True
    print(f"이미지 서버 http://127.0.0.1:{PORT} (모델 {MODEL})", flush=True)
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
