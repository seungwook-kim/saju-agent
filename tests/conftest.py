"""시험은 AI 없이 돈다 (계산 풀이만). 서버 시험이 AI 미리 만들기를 부르지 않게 한다."""
import os

os.environ["SAJU_DOTENV"] = "0"     # 개발자 PC 의 .env(Supabase 키 등)를 시험이 읽지 않게
for _k in ("SUPABASE_URL", "SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
    os.environ.pop(_k, None)

os.environ["SAJU_AI"] = "0"
os.environ["SAJU_RATE"] = "0"
os.environ["SAJU_BOT_BLOCK"] = "0"          # 시험 도구(python-urllib)가 봇으로 막히지 않게. test_guard 에서 따로 켠다       # 요청 횟수 제한은 test_fixes 에서 따로 켜서 본다
