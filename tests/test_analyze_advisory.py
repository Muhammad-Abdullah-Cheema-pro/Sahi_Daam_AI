"""Advisory wiring tests for analyze() (stubbed weather; no network)."""

from __future__ import annotations

from datetime import date

from advisory_engine import DistrictWeather
from analysis.analyze import analyze
from analysis.trend import TrendResult
from model.price_band import BandResult
from schema import HarvestAdvisory, ParsedFarmerRequest


def _toy_band() -> BandResult:
    return BandResult(
        low=5000.0,
        high=6000.0,
        avg=5500.0,
        basis="recent_median_band",
        sample_days=30,
        data_as_of=date(2026, 10, 1),
        reason="toy",
        last_fqp=5500.0,
    )


def _band_fn(city, commodity, as_of=None, df=None):
    if commodity == "Tomato":
        return _toy_band()
    return BandResult(None, None, None, "none", 0, None, "toy none", None)


def _weather_ok(district: str) -> DistrictWeather:
    return DistrictWeather(
        district=district,
        forecast_date="2026-10-10",
        precip_mm_48h=2.0,
        max_precip_prob=10.0,
        temp_min_c=20.0,
        temp_max_c=32.0,
        source="toy-weather",
        from_cache=False,
    )


def _trend_none(city, commodity, as_of=None, df=None):
    return TrendResult(None, None, 0, "stub thin")


def _trend_rising(city, commodity, as_of=None, df=None):
    return TrendResult("Rising", 5.0, 14, "stub rising")


def _advice_ok(crop, crop_stage, weather, price_trend="Flat", disease_triage=None):
    return HarvestAdvisory(
        weather_risk="Low",
        price_trend=price_trend,
        action_advice="Keep produce shaded and ventilated. Toy advice.",
        disclaimer=(
            "Advice only. Non-chemical/standard extension practice recommendations "
            "based on district-level forecasts."
        ),
    )


def test_advisory_populated_on_success() -> None:
    req = ParsedFarmerRequest(
        crop="Tomato",
        quantity_maunds=40,
        district="Okara",
        quoted_price_per_maund=2800.0,
        crop_stage="Ready to harvest",
    )
    result = analyze(
        req,
        band_fn=_band_fn,
        weather_fn=_weather_ok,
        advice_fn=_advice_ok,
        trend_fn=_trend_none,
    )
    assert result.advisory is not None
    assert result.advisory.weather_risk == "Low"
    assert result.advisory.price_trend == "Flat"
    assert result.top_cities
    assert any("toy-weather" in d or "forecast" in d.lower() for d in result.disclaimers)
    assert any("assumed Flat" in d for d in result.disclaimers)


def test_advisory_rising_trend_passed_through() -> None:
    req = ParsedFarmerRequest(
        crop="Tomato",
        quantity_maunds=40,
        district="Okara",
        quoted_price_per_maund=2800.0,
        crop_stage="Ready to harvest",
    )
    result = analyze(
        req,
        band_fn=_band_fn,
        weather_fn=_weather_ok,
        advice_fn=_advice_ok,
        trend_fn=_trend_rising,
    )
    assert result.advisory is not None
    assert result.advisory.price_trend == "Rising"
    assert any("Observed, not a forecast" in d for d in result.disclaimers)


def test_weather_failure_keeps_verdict_and_cities() -> None:
    def boom(_d: str):
        raise TimeoutError("toy timeout")

    req = ParsedFarmerRequest(
        crop="Tomato",
        quantity_maunds=40,
        district="Okara",
        quoted_price_per_maund=2800.0,
    )
    result = analyze(req, band_fn=_band_fn, weather_fn=boom, advice_fn=_advice_ok)
    assert result.advisory is None
    assert result.verdict.verdict_status in {"Fair", "Low", "Very low", "Unable to assess"}
    assert result.top_cities
    assert any("Weather forecast unavailable" in d for d in result.disclaimers)


def test_growing_still_gets_weather_for_musamguard() -> None:
    called = {"n": 0}

    def weather_spy(district: str):
        called["n"] += 1
        return _weather_ok(district)

    req = ParsedFarmerRequest(
        crop="Tomato",
        quantity_maunds=40,
        district="Okara",
        quoted_price_per_maund=2800.0,
        crop_stage="Growing",
    )
    result = analyze(
        req,
        band_fn=_band_fn,
        weather_fn=weather_spy,
        advice_fn=_advice_ok,
        trend_fn=_trend_none,
    )
    assert called["n"] == 1
    assert result.advisory is not None
    assert result.verdict is not None


def test_no_market_advisory_none() -> None:
    req = ParsedFarmerRequest(
        crop="Tomato",
        quantity_maunds=10,
        district="Lahore",
        quoted_price_per_maund=1000.0,
    )
    result = analyze(
        req,
        band_fn=lambda *a, **k: BandResult(
            None, None, None, "none", 0, None, "none", None
        ),
        weather_fn=_weather_ok,
        advice_fn=_advice_ok,
    )
    assert result.verdict.verdict_status == "Unable to assess"
    assert result.advisory is None
    assert result.top_cities == []
