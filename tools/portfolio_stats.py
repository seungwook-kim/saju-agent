"""소개 저장소(saju-agent-portfolio)에 적는 숫자를 뽑는다.

실행: uv run --no-project --with pytest python tools/portfolio_stats.py
소개 README 의 '한눈에 보기' 표와 docs/01 의 시험 수를 이 출력으로 맞춘다.
"""
from __future__ import annotations

import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_TABLES = {"solar_terms_data.py", "calendar_data.py"}          # 생성된 내장 데이터 표
EXTERNAL = {"test_saju_reference.py": "lunar-python 기준",
            "test_official_reference.py": "천문연 음양력·2026년 절기 공개 자료 기준",
            "test_ziwei_iztro.py": "iztro 기준"}


def lines(paths) -> int:
    return sum(len(p.read_text(encoding="utf-8").splitlines()) for p in paths)


def main() -> None:
    pkg = ROOT / "love_fortune"
    py = sorted(pkg.glob("*.py"))
    code = [p for p in py if p.name not in DATA_TABLES]
    static = [p for p in (pkg / "static").iterdir() if p.suffix in (".js", ".css", ".html")]
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
                         cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    per = Counter(line.split("::")[0].split("/")[-1].split("\\")[-1]
                  for line in out.stdout.splitlines() if "::" in line)
    total = sum(per.values())
    ext = sum(per[f] for f in EXTERNAL)
    print(f"파이썬 모듈: {len(py)}개 (계산·서버 {lines(code):,}줄 + 내장 데이터 표 {lines(py) - lines(code):,}줄)")
    print(f"화면 JS·CSS·HTML: {lines(static):,}줄")
    print(f"시험: {total}개, 외부 기준 대조 {ext}개 ({ext * 100 // max(total, 1)}%)")
    for f, label in EXTERNAL.items():
        print(f"  tests/{f:<32} {per[f]:>4}개   ← {label}")
    commits = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    print(f"커밋: {commits}개")


if __name__ == "__main__":
    main()
