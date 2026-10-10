"""Shared configuration for Sahi Daam AI."""

from __future__ import annotations

# 1 maund = 40 kg; 100 kg = 2.5 maunds.
# AMIS quotes Rs per 100 kg → per-maund = rs_per_100kg / 2.5 = rs_per_100kg * 0.4
MAUND_KG = 40
KG_PER_100 = 100
MAUNDS_PER_100KG = KG_PER_100 / MAUND_KG  # 2.5
RS_100KG_TO_MAUND = 1.0 / MAUNDS_PER_100KG  # 0.4

# Exact AMIS ViewPrices row names (searchType=1 city pages).
TARGET_COMMODITIES: dict[str, str] = {
    "Wheat": "Wheat",
    "Tomato": "Tomato",
    "Onion": "Onion",
    "Potato Fresh": "Potato Fresh",
    "Potato Store": "Potato Store",
}

# City display name -> AMIS searchType=1 commodityId (city id).
TARGET_CITIES: dict[str, int] = {
    "Lahore": 1,
    "Faisalabad": 2,
    "Gujranwala": 3,
    "Okara": 4,
    "Sargodha": 5,
    "Rawalpindi": 6,
    "Multan": 7,
}

AMIS_BASE_URL = "http://www.amis.pk"
AMIS_VIEW_PRICES_URL = f"{AMIS_BASE_URL}/ViewPrices.aspx"
AMIS_USER_AGENT = (
    "SahiDaamAI/0.1 (+AICON26; fair-price advisor research; "
    "polite 1.5s delay; cached fetches)"
)
AMIS_REQUEST_TIMEOUT_S = 20  # RUNTIME — AMIS scrape (ASP.NET); longer than 5 s rule
AMIS_POLITE_DELAY_S = 1.5  # RUNTIME
AMIS_MAX_RETRIES = 3  # RUNTIME

# Fair-price band model
MIN_HISTORY_DAYS = 20  # ASSUMPTION - adjustable
BAND_QUANTILES = (0.10, 0.90)  # ASSUMPTION - adjustable
HOLDOUT_DAYS = 28  # ASSUMPTION - adjustable
MIN_MODEL_ROWS = 150  # ASSUMPTION - adjustable
POTATO_PREFERENCE = ["Potato Store", "Potato Fresh"]

# Verdict + routing assumptions (ASSUMPTION - adjustable)
FARMGATE_ALLOWANCE = 0.10  # ASSUMPTION - adjustable
VERY_LOW_RATIO = 0.85  # ASSUMPTION - adjustable
ROAD_FACTOR = 1.3  # ASSUMPTION - adjustable
TRANSPORT_RS_PER_MAUND_KM = 1.5  # ASSUMPTION - adjustable
COMMISSION_PCT = 0.04  # ASSUMPTION - adjustable
TOP_N = 3  # ASSUMPTION - adjustable

# Price trend (ASSUMPTION - adjustable)
TREND_THRESHOLD_PCT = 3.0  # ASSUMPTION - adjustable
TREND_MIN_OBS = 10  # ASSUMPTION - adjustable — need >=10 valid obs in last 30 days
TREND_WINDOW = 7  # ASSUMPTION - adjustable — recent vs prior block size
TREND_LOOKBACK_DAYS = 30  # ASSUMPTION - adjustable

# Weather / advisory (heuristic - verify with an agronomist)
WEATHER_TIMEOUT_S = 5  # RUNTIME — project rule
WEATHER_CACHE_MAX_AGE_H = 24  # ASSUMPTION - adjustable — max age for cached forecast use
WEATHER_FORECAST_HOURS = 72  # ASSUMPTION - adjustable — hourly steps fetched
WEATHER_PRECIP_SUM_HOURS = 48  # ASSUMPTION - adjustable — precip sum window
WEATHER_RISK_HIGH_PRECIP_MM = 20.0  # heuristic - verify with an agronomist
WEATHER_RISK_HIGH_PRECIP_PROB = 70.0  # heuristic - verify with an agronomist
WEATHER_RISK_MED_PRECIP_MM = 8.0  # heuristic - verify with an agronomist
WEATHER_RISK_MED_PRECIP_PROB = 40.0  # heuristic - verify with an agronomist

# MusamGuard phenology × weather threat matrix (heuristic - verify with an agronomist)
HEATWAVE_MAX_TEMP_C = 38.0  # heuristic - verify with an agronomist
THERMAL_NIGHT_MIN_TEMP_C = 28.0  # heuristic - verify with an agronomist
THERMAL_DAY_MAX_TEMP_C = 40.0  # heuristic - verify with an agronomist
RAIN_THREAT_MM = 10.0  # heuristic - verify with an agronomist
RAIN_THREAT_PROB = 60.0  # heuristic - verify with an agronomist
FROST_MIN_TEMP_C = 3.0  # heuristic - verify with an agronomist

# AI / Gemini
DEFAULT_MODEL = "gemini-3.8-flash"  # RUNTIME — Gemini native id (OpenRouter adds google/)
VISION_MODEL = "gemini-3.8-flash"  # RUNTIME — multimodal leaf/canopy triage
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"  # RUNTIME
GEMINI_HTTP_TIMEOUT_MS = 15000  # RUNTIME — Gemini/OpenRouter allowed longer than 5 s
MAX_AI_CALLS_PER_SESSION = 15  # RUNTIME — public URL abuse/quota guard
MAX_VISION_UPLOAD_BYTES = 5 * 1024 * 1024  # RUNTIME — 5 MB leaf photo limit

# Audio upload limits (RUNTIME)
MAX_AUDIO_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_AUDIO_DURATION_S = 60.0  # ASSUMPTION - adjustable
MIN_AUDIO_DURATION_S = 0.4  # ASSUMPTION - adjustable
MIN_AUDIO_BYTES = 2000  # RUNTIME — rough floor before format parse
AUDIO_SILENCE_RMS = 50.0  # ASSUMPTION - adjustable — 16-bit PCM RMS threshold

# Stale band warning
STALE_DATA_DAYS = 3  # ASSUMPTION - adjustable

# UI
CONFIDENCE_WARN = 0.7  # RUNTIME
