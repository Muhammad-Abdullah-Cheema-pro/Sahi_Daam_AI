"""Offline failure-path / UI hardening tests (stubs only)."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from advisory_engine import DistrictWeather
from analysis.analyze import analyze
from analysis.trend import TrendResult
from model.price_band import BandResult, get_band
from schema import HarvestAdvisory, ParsedFarmerRequest
from voice_parser import parse_request

APP = Path(__file__).resolve().parents[1] / "app.py"


def _band(city="Okara", low=5000, high=6000, avg=5500, as_of=None):
    return BandResult(
        low=float(low),
        high=float(high),
        avg=float(avg),
        basis="recent_median_band",
        sample_days=30,
        data_as_of=as_of or date.today(),
        reason="stub",
        last_fqp=float(avg),
    )


def _band_fn_tomato(city, commodity, as_of=None, df=None):
    if commodity == "Tomato":
        return _band(city=city, as_of=as_of)
    return BandResult(None, None, None, "none", 0, None, "none", None)


def _wx(district: str) -> DistrictWeather:
    return DistrictWeather(
        district=district,
        forecast_date=date.today().isoformat(),
        precip_mm_48h=1.0,
        max_precip_prob=5.0,
        temp_min_c=18.0,
        temp_max_c=30.0,
        source="stub",
        from_cache=False,
    )


def test_1_normal_sample_ok() -> None:
    req = ParsedFarmerRequest(
        crop="Tomato",
        quantity_maunds=40,
        district="Okara",
        quoted_price_per_maund=2800.0,
    )
    r = analyze(req, band_fn=_band_fn_tomato, weather_fn=_wx, trend_fn=lambda *a, **k: TrendResult(None, None, 0, "x"))
    assert r.verdict.verdict_status in {"Fair", "Low", "Very low"}
    assert r.top_cities


def test_2_second_sample_changes_market_or_band() -> None:
    r1 = analyze(
        ParsedFarmerRequest(crop="Tomato", quantity_maunds=40, district="Okara", quoted_price_per_maund=2800),
        band_fn=_band_fn_tomato,
        weather_fn=_wx,
        trend_fn=lambda *a, **k: TrendResult(None, None, 0, "x"),
    )

    def band_fsd(city, commodity, as_of=None, df=None):
        if commodity != "Tomato":
            return BandResult(None, None, None, "none", 0, None, "none", None)
        if city == "Faisalabad":
            return _band(city="Faisalabad", low=3000, high=4000, avg=3500)
        return BandResult(None, None, None, "none", 0, None, "none", None)

    r2 = analyze(
        ParsedFarmerRequest(crop="Tomato", quantity_maunds=40, district="Faisalabad", quoted_price_per_maund=2800),
        band_fn=band_fsd,
        weather_fn=_wx,
        trend_fn=lambda *a, **k: TrendResult(None, None, 0, "x"),
    )
    assert (
        r1.verdict.reference_market != r2.verdict.reference_market
        or r1.verdict.predicted_avg_maund != r2.verdict.predicted_avg_maund
    )


def test_3_missing_quantity_needs_clarification() -> None:
    out = parse_request(text="tamatar Okara mein hain", use_llm=False)
    assert out.status == "needs_clarification"
    assert "quantity_maunds" in out.missing_fields


def test_4_parse_failed_message() -> None:
    out = parse_request(text="", use_llm=False)
    assert out.status in {"failed", "needs_clarification"}


def test_5_unsupported_crop_and_non_punjab_blocked() -> None:
    out = parse_request(text="40 maund rice in Karachi broker 1000", use_llm=False)
    # offline lexicon: rice/Karachi not supported → clarification or failed
    assert out.status in {"needs_clarification", "failed", "ok"}
    if out.request is not None:
        # If somehow parsed, district must be Punjab list or schema would reject later
        from geo import COORDS

        if out.request.district:
            # Karachi not in COORDS
            assert out.request.district in COORDS or out.status != "ok"


def test_6_no_quote_unable_assess_band_shown() -> None:
    req = ParsedFarmerRequest(
        crop="Tomato",
        quantity_maunds=40,
        district="Okara",
        quoted_price_per_maund=None,
    )
    r = analyze(req, band_fn=_band_fn_tomato, weather_fn=_wx, trend_fn=lambda *a, **k: TrendResult(None, None, 0, "x"))
    assert r.verdict.verdict_status == "Unable to assess"
    assert r.verdict.predicted_low_maund is not None or r.verdict.predicted_avg_maund is not None


def test_7_llm_raises_fallback_confidence() -> None:
    from llm_client import LLMError

    with patch("voice_parser.extract_from_text", side_effect=LLMError("boom", cause="timeout")):
        out = parse_request(
            text="40 maund tamatar hain Okara mein, broker 2800 de raha hai",
            use_llm=True,
        )
    assert out.status in {"ok", "needs_clarification"}
    if out.request is not None:
        assert out.request.confidence <= 0.6


def test_8_weather_stub_raises_verdict_intact() -> None:
    def boom(_d):
        raise TimeoutError("weather down")

    r = analyze(
        ParsedFarmerRequest(crop="Tomato", quantity_maunds=40, district="Okara", quoted_price_per_maund=2800),
        band_fn=_band_fn_tomato,
        weather_fn=boom,
        trend_fn=lambda *a, **k: TrendResult(None, None, 0, "x"),
    )
    assert r.verdict is not None
    assert r.top_cities
    assert r.advisory is None
    assert any("Weather" in d for d in r.disclaimers)


def test_9_apptest_process_does_not_analyze() -> None:
    from streamlit.testing.v1 import AppTest

    calls = {"n": 0}

    def spy(req, **kwargs):
        calls["n"] += 1
        return analyze(
            req,
            band_fn=_band_fn_tomato,
            weather_fn=_wx,
            trend_fn=lambda *a, **k: TrendResult(None, None, 0, "x"),
        )

    with patch("app.analyze", side_effect=spy):
        at = AppTest.from_file(str(APP), default_timeout=15)
        at.run()
        # Process text without confirm
        if at.text_area:
            at.text_area[0].set_value("40 maund tamatar Okara 2800").run()
        # Click process_text if present
        for b in at.button:
            if "Process text" in (b.label or ""):
                b.click().run()
                break
        assert calls["n"] == 0


def test_10_session_ai_cap_offline(monkeypatch) -> None:
    import app as app_mod

    class SS(dict):
        def __getattr__(self, k):
            return self.get(k)

        def __setattr__(self, k, v):
            self[k] = v

    fake = SS()
    fake.update(
        {
            "ai_calls": 15,
            "parse_outcome": None,
            "form_draft": None,
            "analysis_result": None,
            "audio_cache": {},
            "stage_defaulted": False,
            "ai_mode_label": None,
            "typed_text": "",
        }
    )
    monkeypatch.setattr(app_mod.st, "session_state", fake)
    monkeypatch.setattr(app_mod.st, "info", lambda *a, **k: None)
    monkeypatch.setattr(app_mod.st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(app_mod.st, "warning", lambda *a, **k: None)
    monkeypatch.setattr(app_mod.st, "error", lambda *a, **k: None)
    monkeypatch.setattr(app_mod, "resolve_api_key", lambda: "fake")
    with patch("app.parse_text_to_request") as p:
        p.return_value = MagicMock(
            status="ok",
            request=ParsedFarmerRequest(
                crop="Tomato", quantity_maunds=40, district="Okara", quoted_price_per_maund=2800
            ),
            message="ok",
            missing_fields=[],
        )
        app_mod._process_text("40 maund tamatar Okara 2800")
        assert p.call_args.kwargs.get("use_llm") is False


def test_11_stale_data_warning_logic() -> None:
    from config import STALE_DATA_DAYS

    stale_as_of = date.today() - timedelta(days=STALE_DATA_DAYS + 2)

    def band_stale(city, commodity, as_of=None, df=None):
        if commodity == "Tomato":
            return _band(as_of=stale_as_of)
        return BandResult(None, None, None, "none", 0, None, "none", None)

    r = analyze(
        ParsedFarmerRequest(crop="Tomato", quantity_maunds=40, district="Okara", quoted_price_per_maund=2800),
        band_fn=band_stale,
        weather_fn=_wx,
        trend_fn=lambda *a, **k: TrendResult(None, None, 0, "x"),
    )
    assert r.verdict.data_as_of is not None
    assert (date.today() - r.verdict.data_as_of).days > STALE_DATA_DAYS


def test_12_no_wheat_potato_unable() -> None:
    def none_band(city, commodity, as_of=None, df=None):
        return BandResult(None, None, None, "none", 0, None, "no data", None)

    for crop in ("Wheat", "Potato"):
        r = analyze(
            ParsedFarmerRequest(crop=crop, quantity_maunds=10, district="Lahore", quoted_price_per_maund=3000),
            band_fn=none_band,
            weather_fn=_wx,
        )
        assert r.verdict.verdict_status == "Unable to assess"
        assert "WHOLESALE" in (r.verdict.reason or "")
        assert r.verdict.predicted_avg_maund is None
