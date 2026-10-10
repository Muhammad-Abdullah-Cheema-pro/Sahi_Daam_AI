"""Weather fetch + MusamGuard phenology×weather risk matrix (Open-Meteo + SQLite).

Harvest advisory is RULE-BASED on the Open-Meteo forecast, observed price trend,
and optional disease triage — NOT a neural weather network.
Thresholds marked heuristic need agronomist verification.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Literal, Optional, Union

import requests

from config import (
    FROST_MIN_TEMP_C,
    HEATWAVE_MAX_TEMP_C,
    RAIN_THREAT_MM,
    RAIN_THREAT_PROB,
    THERMAL_DAY_MAX_TEMP_C,
    THERMAL_NIGHT_MIN_TEMP_C,
    WEATHER_CACHE_MAX_AGE_H,
    WEATHER_FORECAST_HOURS,
    WEATHER_PRECIP_SUM_HOURS,
    WEATHER_RISK_HIGH_PRECIP_MM,
    WEATHER_RISK_HIGH_PRECIP_PROB,
    WEATHER_RISK_MED_PRECIP_MM,
    WEATHER_RISK_MED_PRECIP_PROB,
    WEATHER_TIMEOUT_S,
)
from geo import COORDS
from schema import (
    DiseaseTriageResult,
    EnhancedHarvestAdvisory,
    HarvestAdvisory,
    PhenologyStage,
    WeatherThreatType,
)

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent


def _cache_db_path() -> Path:
    preferred = ROOT / "data" / "sahi_daam.db"
    try:
        preferred.parent.mkdir(parents=True, exist_ok=True)
        preferred.parent.joinpath(".write_probe").write_text("ok", encoding="utf-8")
        preferred.parent.joinpath(".write_probe").unlink(missing_ok=True)
        return preferred
    except OSError:
        tmp = Path(tempfile.gettempdir()) / "sahi_daam.db"
        logger.warning("Repo data/ not writable; using temp DB %s", tmp)
        return tmp


CACHE_DB = _cache_db_path()

# Extended phenology list (includes legacy harvest stages)
CROP_STAGES: list[str] = [s.value for s in PhenologyStage]

PriceTrend = Literal["Rising", "Flat", "Falling"]
WeatherRisk = Literal["High", "Medium", "Low"]

DEFAULT_DISCLAIMER = (
    "Advice only. Non-chemical/standard extension practice recommendations "
    "based on district-level forecasts."
)

# Block pesticide-class wording; allow standard extension SOP spray language.
_FORBIDDEN_WORDS = (
    "pesticide",
    "insecticide",
    "herbicide",
    "fungicide",
    "cheat",
    "fraud",
)


@dataclass
class DistrictWeather:
    """48–72 h forecast summary for a Punjab district."""

    district: str
    forecast_date: str
    precip_mm_48h: float
    max_precip_prob: float
    temp_min_c: float
    temp_max_c: float
    source: str
    from_cache: bool
    fetched_at: float = 0.0
    raw_note: str = ""
    wind_max_kmh: float = 0.0


class AdvisoryError(Exception):
    """Weather or advice generation failure."""


def _ensure_cache() -> None:
    CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(CACHE_DB) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS weather_cache (
                district TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                fetched_at REAL NOT NULL
            )
            """
        )
        conn.commit()


def _cache_get(
    district: str, *, max_age_h: float = WEATHER_CACHE_MAX_AGE_H
) -> Optional[DistrictWeather]:
    _ensure_cache()
    with sqlite3.connect(CACHE_DB) as conn:
        row = conn.execute(
            "SELECT payload, fetched_at FROM weather_cache WHERE district = ?",
            (district,),
        ).fetchone()
    if not row:
        return None
    payload, fetched_at = row
    age_h = (time.time() - float(fetched_at)) / 3600.0
    if age_h > max_age_h:
        return None
    data = json.loads(payload)
    data["from_cache"] = True
    data["fetched_at"] = float(fetched_at)
    data.setdefault("wind_max_kmh", 0.0)
    return DistrictWeather(**{k: data[k] for k in DistrictWeather.__dataclass_fields__})


def _cache_put(weather: DistrictWeather) -> None:
    _ensure_cache()
    payload = asdict(weather)
    payload["from_cache"] = False
    with sqlite3.connect(CACHE_DB) as conn:
        conn.execute(
            """
            INSERT INTO weather_cache(district, payload, fetched_at)
            VALUES (?, ?, ?)
            ON CONFLICT(district) DO UPDATE SET
                payload = excluded.payload,
                fetched_at = excluded.fetched_at
            """,
            (weather.district, json.dumps(payload), weather.fetched_at or time.time()),
        )
        conn.commit()


def fetch_district_weather(district: str) -> DistrictWeather:
    """Fetch forecast for a district centre. 5 s timeout; SQLite cache fallback."""
    if district not in COORDS:
        raise AdvisoryError(f"Unknown district for weather: {district!r}")

    cached = _cache_get(district, max_age_h=WEATHER_CACHE_MAX_AGE_H)
    lat, lon = COORDS[district]
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": (
            "temperature_2m,precipitation,precipitation_probability,rain,"
            "wind_speed_10m"
        ),
        "forecast_days": 3,
        "timezone": "Asia/Karachi",
    }
    try:
        resp = requests.get(url, params=params, timeout=WEATHER_TIMEOUT_S)
        resp.raise_for_status()
        data = resp.json()
        hourly = data.get("hourly") or {}
        temps = [float(x) for x in (hourly.get("temperature_2m") or []) if x is not None]
        precips = [float(x) for x in (hourly.get("precipitation") or []) if x is not None]
        rains = [float(x) for x in (hourly.get("rain") or []) if x is not None]
        probs = [
            float(x)
            for x in (hourly.get("precipitation_probability") or [])
            if x is not None
        ]
        winds = [
            float(x) for x in (hourly.get("wind_speed_10m") or []) if x is not None
        ]
        temps_w = temps[:WEATHER_FORECAST_HOURS]
        precips_w = (rains or precips)[:WEATHER_PRECIP_SUM_HOURS]
        probs_w = probs[:WEATHER_FORECAST_HOURS]
        winds_w = winds[:WEATHER_FORECAST_HOURS]
        if not temps_w:
            raise AdvisoryError("Empty weather payload")
        now = time.time()
        weather = DistrictWeather(
            district=district,
            forecast_date=date.today().isoformat(),
            precip_mm_48h=float(sum(precips_w)),
            max_precip_prob=float(max(probs_w) if probs_w else 0.0),
            temp_min_c=float(min(temps_w)),
            temp_max_c=float(max(temps_w)),
            source="Open-Meteo",
            from_cache=False,
            fetched_at=now,
            raw_note=f"lat={lat},lon={lon}",
            wind_max_kmh=float(max(winds_w) if winds_w else 0.0),
        )
        _cache_put(weather)
        return weather
    except Exception as exc:
        logger.warning("Weather fetch failed for %s: %s", district, exc)
        if cached is not None:
            logger.warning("Using SQLite cached weather for %s", district)
            return cached
        raise AdvisoryError(f"Weather unavailable for {district}: {exc}") from exc


def _classify_weather_risk(weather: DistrictWeather) -> WeatherRisk:
    if (
        weather.precip_mm_48h >= WEATHER_RISK_HIGH_PRECIP_MM
        or weather.max_precip_prob >= WEATHER_RISK_HIGH_PRECIP_PROB
        or weather.temp_max_c >= HEATWAVE_MAX_TEMP_C
        or weather.temp_min_c <= FROST_MIN_TEMP_C
    ):
        return "High"
    if (
        weather.precip_mm_48h >= WEATHER_RISK_MED_PRECIP_MM
        or weather.max_precip_prob >= WEATHER_RISK_MED_PRECIP_PROB
    ):
        return "Medium"
    return "Low"


def _normalize_stage(crop_stage: str) -> str:
    text = (crop_stage or "").strip()
    for s in CROP_STAGES:
        if s.lower() == text.lower():
            return s
    return "Ready to harvest"


def _crop_key(crop: str) -> str:
    return (crop or "").strip().lower()


def _evaluate_threat_matrix(
    crop: str,
    stage: str,
    weather: DistrictWeather,
) -> tuple[WeatherRisk, WeatherThreatType, str]:
    """Deterministic phenology × weather lookups. Returns risk, threat, protocol."""
    c = _crop_key(crop)
    stage_l = stage.lower()

    # Wheat + Grain-Filling + heat spike
    if (
        c == "wheat"
        and stage_l in {"grain-filling", "grain filling"}
        and weather.temp_max_c >= HEATWAVE_MAX_TEMP_C
    ):
        return (
            "High",
            "Heatwave",
            (
                "Apply 1% Potassium Nitrate (SOP) spray or light night-irrigation "
                "to maintain canopy cooling and protect kernel weight."
            ),
        )

    # Cotton + Early Flowering + extreme night / day stress
    if (
        c == "cotton"
        and stage_l in {"early flowering", "early-flowering"}
        and (
            weather.temp_min_c >= THERMAL_NIGHT_MIN_TEMP_C
            or weather.temp_max_c >= THERMAL_DAY_MAX_TEMP_C
        )
    ):
        return (
            "High",
            "Thermal Night Stress",
            (
                "Apply foliar nutrient spray (SOP/Boron) and ensure root-zone soil "
                "moisture to prevent early boll shedding."
            ),
        )

    # Maize/Wheat + harvest readiness / harvested + rain
    harvestish = stage_l in {
        "nearly ready",
        "ready to harvest",
        "harvested, not sold",
        "harvested not sold",
    }
    if (
        c in {"wheat", "maize", "corn"}
        and harvestish
        and (
            weather.precip_mm_48h > RAIN_THREAT_MM
            or weather.max_precip_prob > RAIN_THREAT_PROB
        )
    ):
        return (
            "High",
            "Unseasonal Rain",
            (
                "Delay harvest or cover harvested heaps immediately with tarpaulins "
                "to avoid fungal aflatoxin contamination."
            ),
        )

    # Young vegetables / Growing + frost / near-frost
    veg = c in {"tomato", "onion", "potato", "vegetable", "vegetables"}
    if (
        (veg or stage_l == "growing")
        and weather.temp_min_c <= FROST_MIN_TEMP_C
    ):
        return (
            "High",
            "Frost",
            (
                "Conduct controlled micro-drenching or light smoky border fires at night "
                "to elevate field boundary-layer air temperatures. Prefer physical covers "
                "where available."
            ),
        )

    # Generic rain cover for ready harvest of any supported crop
    if harvestish and (
        weather.precip_mm_48h >= WEATHER_RISK_HIGH_PRECIP_MM
        or weather.max_precip_prob >= WEATHER_RISK_HIGH_PRECIP_PROB
    ):
        return (
            "High",
            "Unseasonal Rain",
            (
                "Cover harvested or ready produce with tarpaulins; improve ventilation; "
                "prefer the next dry window for transport."
            ),
        )

    risk = _classify_weather_risk(weather)
    if risk == "Medium":
        return (
            "Medium",
            "None",
            (
                "Watch the sky daily; keep tarpaulins ready; provide shade and airflow "
                "for packed produce."
            ),
        )
    if risk == "High":
        return (
            "High",
            "None",
            (
                "Prefer a dry harvest window; shade produce; use tarpaulins if rain is "
                "likely; improve temporary-storage ventilation."
            ),
        )
    return (
        "Low",
        "None",
        "Weather risk is low. Time harvest by market readiness; keep basic shade.",
    )


def _disease_tip(disease: Optional[DiseaseTriageResult]) -> str:
    if disease is None or disease.is_healthy:
        return ""
    return (
        f"Leaf health: {disease.detected_disease} ({disease.severity}). "
        f"{disease.symptoms_summary} "
        "Isolate visibly affected leaves where practical, improve row ventilation, "
        "and consult local agricultural extension before any product use."
    )


def generate_harvest_advice(
    crop: str,
    crop_stage: str,
    weather: Union[DistrictWeather, dict],
    price_trend: PriceTrend = "Flat",
    disease_triage: Optional[DiseaseTriageResult] = None,
) -> EnhancedHarvestAdvisory:
    """Build MusamGuard-enhanced harvest/mitigation advice.

    Backward compatible with prior call sites (optional disease_triage).
    Accepts DistrictWeather or a plain dict (tests).
    """
    if isinstance(weather, dict):
        weather = DistrictWeather(**weather)
    if price_trend not in {"Rising", "Flat", "Falling"}:
        price_trend = "Flat"

    stage = _normalize_stage(crop_stage)
    risk, threat, protocol = _evaluate_threat_matrix(crop, stage, weather)
    disease_tip = _disease_tip(disease_triage)

    parts: list[str] = []
    if stage == "Growing" and threat == "None":
        parts.append(
            f"Crop stage is Growing — monitor weather for {crop}; keep shade/"
            "ventilation ready; use tarpaulins if unexpected rain threatens young plants."
        )
    else:
        parts.append(f"Weather risk is {risk}. {protocol}")

    if price_trend == "Rising" and risk == "Low":
        parts.append(
            "Prices appear Rising with low weather risk — a short wait may be "
            "reasonable if produce can be kept shaded and ventilated."
        )
    elif price_trend == "Falling":
        parts.append(
            "Prices appear Falling — delaying sale is less attractive; compare mandi "
            "options if produce is ready."
        )

    if disease_tip:
        parts.append(disease_tip)

    cache_note = ""
    if weather.from_cache and weather.fetched_at:
        cache_note = (
            ", cached forecast from "
            + time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(weather.fetched_at))
        )
    wind_bit = (
        f" wind max ~{weather.wind_max_kmh:.0f} km/h;"
        if weather.wind_max_kmh > 0
        else ""
    )
    parts.append(
        f"Forecast source: {weather.source} for {weather.district} "
        f"(as of {weather.forecast_date}{cache_note}). "
        f"Temps {weather.temp_min_c:.0f}–{weather.temp_max_c:.0f}°C;"
        f"{wind_bit} "
        f"rain chance max {weather.max_precip_prob:.0f}%; "
        f"precip ~{weather.precip_mm_48h:.1f} mm/48h."
    )

    advice = " ".join(parts)
    low = advice.lower()
    for w in _FORBIDDEN_WORDS:
        if w in low:
            advice = (
                "Keep produce shaded and ventilated; use tarpaulins if rain is likely; "
                "time harvest for a dry window. " + DEFAULT_DISCLAIMER
            )
            protocol = (
                "Shade, ventilate, and use tarpaulins; consult local extension "
                "for any spray guidance."
            )
            break

    return EnhancedHarvestAdvisory(
        weather_risk=risk,
        price_trend=price_trend,
        action_advice=advice,
        disclaimer=DEFAULT_DISCLAIMER,
        weather_threat_type=threat,
        mitigation_protocol=protocol,
        disease_action_tip=disease_tip,
    )


def normalize_crop_stage(raw: Optional[str]) -> tuple[str, bool]:
    """Map free-text stage to a CROP_STAGES option. Returns (stage, used_default)."""
    if not raw or not str(raw).strip():
        return "Ready to harvest", True
    text = str(raw).strip().lower()
    mapping = {
        "growing": "Growing",
        "grow": "Growing",
        "vegetative": "Growing",
        "early flowering": "Early Flowering",
        "flowering": "Early Flowering",
        "grain-filling": "Grain-Filling",
        "grain filling": "Grain-Filling",
        "nearly ready": "Nearly ready",
        "almost ready": "Nearly ready",
        "near harvest": "Nearly ready",
        "ready to harvest": "Ready to harvest",
        "ready": "Ready to harvest",
        "harvest ready": "Ready to harvest",
        "harvested, not sold": "Harvested, not sold",
        "harvested not sold": "Harvested, not sold",
        "harvested": "Harvested, not sold",
        "in store": "Harvested, not sold",
    }
    if text in mapping:
        return mapping[text], False
    for stage in CROP_STAGES:
        if stage.lower() in text or text in stage.lower():
            return stage, False
    return "Ready to harvest", True
