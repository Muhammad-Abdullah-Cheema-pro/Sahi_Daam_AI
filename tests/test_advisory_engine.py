"""Table-driven advisory + weather cache tests (offline stubs)."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest

import advisory_engine as ae
from advisory_engine import (
    CROP_STAGES,
    DistrictWeather,
    AdvisoryError,
    fetch_district_weather,
    generate_harvest_advice,
    _classify_weather_risk,
)
from config import (
    WEATHER_CACHE_MAX_AGE_H,
    WEATHER_RISK_HIGH_PRECIP_MM,
    WEATHER_RISK_HIGH_PRECIP_PROB,
    WEATHER_RISK_MED_PRECIP_MM,
    WEATHER_RISK_MED_PRECIP_PROB,
)


def _wx(
    precip: float = 0.0,
    prob: float = 0.0,
    *,
    from_cache: bool = False,
    fetched_at: float = 0.0,
    district: str = "Lahore",
) -> DistrictWeather:
    return DistrictWeather(
        district=district,
        forecast_date="2026-10-10",
        precip_mm_48h=precip,
        max_precip_prob=prob,
        temp_min_c=18.0,
        temp_max_c=30.0,
        source="Open-Meteo",
        from_cache=from_cache,
        fetched_at=fetched_at,
    )


@pytest.mark.parametrize("risk", ["High", "Medium", "Low"])
@pytest.mark.parametrize("trend", ["Rising", "Flat", "Falling"])
@pytest.mark.parametrize("stage", CROP_STAGES)
def test_all_risk_trend_stage_combos(risk, trend, stage) -> None:
    # Force risk via precip thresholds
    if risk == "High":
        wx = _wx(precip=WEATHER_RISK_HIGH_PRECIP_MM + 1)
    elif risk == "Medium":
        wx = _wx(precip=WEATHER_RISK_MED_PRECIP_MM + 1)
    else:
        wx = _wx(precip=0.0, prob=0.0)
    adv = generate_harvest_advice("Tomato", stage, wx, price_trend=trend)
    assert adv.action_advice.strip()
    assert adv.weather_risk == risk
    assert adv.price_trend == trend
    assert adv.disclaimer
    assert "district-level forecasts" in adv.disclaimer
    low = adv.action_advice.lower()
    for bad in ("pesticide", "insecticide", "herbicide", "fungicide", "cheat", "fraud"):
        assert bad not in low


def test_risk_boundaries() -> None:
    assert _classify_weather_risk(_wx(precip=WEATHER_RISK_HIGH_PRECIP_MM)) == "High"
    assert _classify_weather_risk(
        _wx(precip=0, prob=WEATHER_RISK_HIGH_PRECIP_PROB)
    ) == "High"
    assert _classify_weather_risk(_wx(precip=WEATHER_RISK_MED_PRECIP_MM)) == "Medium"
    assert _classify_weather_risk(
        _wx(precip=0, prob=WEATHER_RISK_MED_PRECIP_PROB)
    ) == "Medium"
    assert _classify_weather_risk(_wx(precip=0, prob=0)) == "Low"


def test_unknown_district_raises() -> None:
    with pytest.raises(AdvisoryError):
        fetch_district_weather("NotADistrict")


def test_timeout_uses_warm_cache(tmp_path, monkeypatch) -> None:
    db = tmp_path / "weather_cache.db"
    monkeypatch.setattr(ae, "CACHE_DB", db)
    now = time.time()
    cached = _wx(precip=1.0, from_cache=False, fetched_at=now)
    ae._cache_put(cached)

    def boom(*a, **k):
        raise TimeoutError("slow")

    with patch("advisory_engine.requests.get", side_effect=boom):
        got = fetch_district_weather("Lahore")
    assert got.from_cache is True
    assert got.district == "Lahore"


def test_timeout_cold_cache_raises(tmp_path, monkeypatch) -> None:
    db = tmp_path / "weather_cache.db"
    monkeypatch.setattr(ae, "CACHE_DB", db)
    # Stale cache older than max age
    old = time.time() - (WEATHER_CACHE_MAX_AGE_H + 2) * 3600
    ae._ensure_cache()
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO weather_cache(district, payload, fetched_at) VALUES (?,?,?)",
            ("Lahore", json.dumps(asdict(_wx(fetched_at=old))), old),
        )
        conn.commit()

    def boom(*a, **k):
        raise TimeoutError("slow")

    with patch("advisory_engine.requests.get", side_effect=boom):
        with pytest.raises(AdvisoryError):
            fetch_district_weather("Lahore")


def test_http_500_and_bad_json(tmp_path, monkeypatch) -> None:
    db = tmp_path / "weather_cache.db"
    monkeypatch.setattr(ae, "CACHE_DB", db)

    resp = MagicMock()
    resp.raise_for_status.side_effect = Exception("500")
    with patch("advisory_engine.requests.get", return_value=resp):
        with pytest.raises(AdvisoryError):
            fetch_district_weather("Lahore")

    resp2 = MagicMock()
    resp2.raise_for_status.return_value = None
    resp2.json.return_value = {"hourly": {}}
    with patch("advisory_engine.requests.get", return_value=resp2):
        with pytest.raises(AdvisoryError):
            fetch_district_weather("Multan")
