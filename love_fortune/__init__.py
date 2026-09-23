"""love_fortune package, 정통 공식 기반 상세 해석 (로컬·오프라인)."""
from .manseryuk import four_pillars, dayun, shensha
from .rules import love_score
from .advise import build_advice
from .ziwei import ziwei_chart
from .astro import astro_chart, natal_chart
from .match import spouse_archetype
from .synthesis import detailed_reading
from .lifetime import lifetime_reading
from .glossary import TERMS, explain
from .story import build_stories
from .matchmaking import compatibility
from .taekil import pick_dates
from .lunar import solar_to_lunar, true_solar_time
from .web import local_agent_reply, agent_context

__all__ = ["four_pillars", "dayun", "shensha", "love_score", "build_advice",
           "ziwei_chart", "astro_chart", "natal_chart", "spouse_archetype",
           "detailed_reading", "solar_to_lunar", "true_solar_time",
           "local_agent_reply", "agent_context", "lifetime_reading",
           "TERMS", "explain", "build_stories", "compatibility",
           "pick_dates"]
__version__ = "1.2.0"
