"""wsgi.py, Vercel 입구 (pyproject.toml 의 [tool.vercel] entrypoint = "love_fortune.wsgi:app").

Vercel 파이썬 실행기는 WSGI/ASGI 의 app 을 부른다. 서버 코드(web.Handler)는 표준 라이브러리
http.server 방식이라, WSGI 요청을 원래 HTTP 요청 바이트로 되돌려 Handler 에 그대로 먹이고
Handler 가 쓴 응답 바이트를 다시 WSGI 응답으로 바꾼다. 서버 코드는 한 줄도 안 바꾼다.
"""
from __future__ import annotations

import io

from .web import Handler


class _Conn:
    """Handler 가 소켓이라고 믿고 쓰는 가짜 연결. 읽을 요청 바이트를 들고 있고, 쓴 바이트를 모은다."""

    def __init__(self, raw: bytes):
        self._in = io.BytesIO(raw)
        self.out = bytearray()

    def makefile(self, mode, *a, **k):
        return self._in

    def sendall(self, b):
        self.out += b

    def settimeout(self, *_):
        pass

    def close(self):
        pass


class _Server:
    server_name, server_port = "vercel", 443


def _raw_request(environ) -> bytes:
    path = environ.get("PATH_INFO") or "/"
    path = path.encode("latin-1").decode("utf-8", "replace")      # WSGI 는 경로를 latin-1 로 준다
    from urllib.parse import quote
    path = quote(path, safe="/:@!$&'()*+,;=-._~%")
    qs = environ.get("QUERY_STRING") or ""
    target = path + ("?" + qs if qs else "")
    n = int(environ.get("CONTENT_LENGTH") or 0)
    body = environ["wsgi.input"].read(n) if n > 0 else b""
    lines = [f"{environ['REQUEST_METHOD']} {target} HTTP/1.1"]
    for k, v in environ.items():
        if k.startswith("HTTP_"):
            lines.append(k[5:].replace("_", "-").title() + ": " + v)
    if environ.get("CONTENT_TYPE"):
        lines.append("Content-Type: " + environ["CONTENT_TYPE"])
    lines.append(f"Content-Length: {len(body)}")
    lines.append("Connection: close")
    return ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1") + body


def app(environ, start_response):
    conn = _Conn(_raw_request(environ))
    Handler(conn, (environ.get("REMOTE_ADDR") or "0.0.0.0", 0), _Server())
    head, _, body = bytes(conn.out).partition(b"\r\n\r\n")
    lines = head.decode("latin-1").split("\r\n")
    status = lines[0].split(" ", 1)[1] if " " in lines[0] else "500 Internal Server Error"
    headers = []
    for line in lines[1:]:
        k, _, v = line.partition(":")
        if k and k.lower() not in ("connection", "server", "date"):
            headers.append((k, v.strip()))
    start_response(status, headers)
    return [body]
