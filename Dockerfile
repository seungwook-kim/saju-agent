# 표준 라이브러리만 쓰므로 설치할 패키지가 없다
FROM python:3.12-slim

WORKDIR /app
COPY love_fortune ./love_fortune
COPY db ./db
COPY pyproject.toml README.md THIRD_PARTY_NOTICES.md ./

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    HOST=0.0.0.0 \
    PORT=8765 \
    LOVE_FORTUNE_PREFETCH=0

EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8765')+'/healthz',timeout=4)"
CMD ["python", "-m", "love_fortune", "form"]
