"""Vercel 입구: 모든 주소를 이 함수 하나가 받아 love_fortune.web.Handler 로 처리한다 (vercel.json 의 rewrites).

Vercel 파이썬 실행기는 이 파일의 handler(BaseHTTPRequestHandler) 클래스를 찾아 쓴다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from love_fortune.web import Handler as handler  # noqa: E402,F401
