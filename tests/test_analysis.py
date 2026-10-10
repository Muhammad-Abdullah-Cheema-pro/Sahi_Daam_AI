"""Toy-band tests for verdict, routing, and analyze (no invented AMIS prices)."""

from __future__ import annotations

from datetime import date

import pytest

from analysis.analyze import analyze
from analysis.routing import rank_markets
from analysis.verdict import assess_quote
from config import (
    COMMISSION_PCT,
    FARMGATE_ALLOWANCE,
    VERY_LOW_RATIO,
    TRANSPORT_RS_PER_MAUND_KM,
)
from geo import COORDS, distance_km, haversine_km
from model.price_band import BandResult
from schema import AnalysisResult, ParsedFarmerRequest


def _toy_band(
    low: float,
    high: float,
    avg: float,
    basis: str = "recent_median_band",
    sample_days: int = 30,
) -> BandResult:
    """Labelled toy BandResult — not real market data."""
    return BandResult(
        low=low,
        high=high,
        avg=avg,
        basis=basis,  # type: ignore[arg-type]
        sample_days=sample_days,
        data_as_of=date(2026, 10, 1),
        reason="toy band",
        last_fqp=avg,
    )


def _none_band(reason: str = "toy: no data") -> BandResult:
    return BandResult(
        None, None, None, "none", 0, None, reason, None
    )


def test_haversine_lahore_multan_faisalabad() -> None:
    la = COORDS["Lahore"]
    mu = COORDS["Multan"]
    fa = COORDS["Faisalabad"]
    lm = haversine_km(la[0], la[1], mu[0], mu[1])
    lf = haversine_km(la[0], la[1], fa[0], fa[1])
    assert 300 <= lm <= 325
    assert 115 <= lf <= 130
    # road-adjusted is larger
    assert distance_km("Lahore", "Multan") > lm


def test_verdict_boundaries() -> None:
    band = _toy_band(1000.0, 1200.0, 1100.0)
    adj_low = 1000.0 * (1.0 - FARMGATE_ALLOWANCE)  # 900
    # Fair: quote == adj_low
    v = assess_quote(adj_low, band, "Lahore")
    assert v.verdict_status == "Fair"
    assert "WHOLESALE" in (v.reason or "").upper()
    # Low: just below adj_low, at threshold
    low_edge = VERY_LOW_RATIO * adj_low  # 765
    v = assess_quote(low_edge, band, "Lahore")
    assert v.verdict_status == "Low"
    assert "below wholesale range" in (v.reason or "").lower()
    # Very low: just under threshold
    v = assess_quote(low_edge - 1.0, band, "Lahore")
    assert v.verdict_status == "Very low"


def test_verdict_no_quote_keeps_band() -> None:
    band = _toy_band(1000.0, 1200.0, 1100.0, basis="model_band")
    v = assess_quote(None, band, "Faisalabad")
    assert v.verdict_status == "Unable to assess"
    assert v.basis == "model_band"
    assert v.predicted_avg_maund == 1100.0
    assert v.percentage_gap is None
    AnalysisResult.model_validate(
        {
            "request": ParsedFarmerRequest(
                crop="Tomato",
                quantity_maunds=40,
                district="Okara",
                quoted_price_per_maund=None,
            ).model_dump(),
            "verdict": v.model_dump(),
        }
    )


def test_verdict_basis_none() -> None:
    v = assess_quote(2800.0, _none_band(), "Okara")
    assert v.verdict_status == "Unable to assess"
    assert v.basis == "none"
    assert "WHOLESALE" in (v.reason or "").upper()


def test_gap_sign() -> None:
    band = _toy_band(1000.0, 1200.0, 1100.0)
    v_hi = assess_quote(1210.0, band, "Lahore")  # above avg
    v_lo = assess_quote(990.0, band, "Lahore")
    assert v_hi.percentage_gap is not None and v_hi.percentage_gap > 0
    assert v_lo.percentage_gap is not None and v_lo.percentage_gap < 0
    assert v_hi.percentage_gap == pytest.approx((1210 - 1100) / 1100 * 100)


def test_routing_hand_computed_and_sort(monkeypatch: pytest.MonkeyPatch) -> None:
    """Toy bands + known distances → hand-checked nets and sort order."""
    # Use Lahore district; markets Lahore (0 km) and Faisalabad
    bands = {
        ("Lahore", "Tomato"): _toy_band(5000.0, 6000.0, 5500.0),
        ("Faisalabad", "Tomato"): _toy_band(5200.0, 6200.0, 5700.0),
        ("Multan", "Tomato"): _none_band(),
        ("Gujranwala", "Tomato"): _none_band(),
        ("Okara", "Tomato"): _none_band(),
        ("Sargodha", "Tomato"): _none_band(),
        ("Rawalpindi", "Tomato"): _none_band(),
    }

    def fake_get_band(city, commodity, as_of=None, df=None):
        return bands.get((city, commodity), _none_band())

    monkeypatch.setattr("analysis.routing.get_band", fake_get_band)

    req = ParsedFarmerRequest(
        crop="Tomato",
        quantity_maunds=40,
        district="Lahore",
        quoted_price_per_maund=2800.0,
    )
    ranked = rank_markets(req, band_fn=fake_get_band)
    assert len(ranked) == 2
    # Hand compute
    d_lhr = distance_km("Lahore", "Lahore")
    d_fsd = distance_km("Lahore", "Faisalabad")
    net_lhr = 5500 * (1 - COMMISSION_PCT) - d_lhr * TRANSPORT_RS_PER_MAUND_KM
    net_fsd = 5700 * (1 - COMMISSION_PCT) - d_fsd * TRANSPORT_RS_PER_MAUND_KM
    by_city = {r.city_name: r for r in ranked}
    assert by_city["Lahore"].net_price_maund == pytest.approx(net_lhr, rel=1e-6)
    assert by_city["Faisalabad"].net_price_maund == pytest.approx(net_fsd, rel=1e-6)
    assert by_city["Lahore"].net_gain_vs_quote == pytest.approx(net_lhr - 2800, rel=1e-6)
    # Sorted by net desc
    assert ranked[0].net_price_maund >= ranked[1].net_price_maund
    assert "TRANSPORT_RS_PER_MAUND_KM".lower() in ranked[0].assumptions.lower() or "1.5" in ranked[0].assumptions


def test_okara_wheat_falls_back_to_faisalabad(monkeypatch: pytest.MonkeyPatch) -> None:
    bands = {
        ("Okara", "Wheat"): _none_band("toy: no Okara wheat"),
        ("Faisalabad", "Wheat"): _toy_band(4000.0, 4500.0, 4200.0),
        ("Lahore", "Wheat"): _toy_band(4100.0, 4600.0, 4300.0),
        ("Multan", "Wheat"): _none_band(),
        ("Gujranwala", "Wheat"): _none_band(),
        ("Sargodha", "Wheat"): _none_band(),
        ("Rawalpindi", "Wheat"): _none_band(),
    }

    def fake_get_band(city, commodity, as_of=None, df=None):
        return bands.get((city, commodity), _none_band())

    monkeypatch.setattr("analysis.analyze.get_band", fake_get_band)
    monkeypatch.setattr("analysis.routing.get_band", fake_get_band)

    req = ParsedFarmerRequest(
        crop="Wheat",
        quantity_maunds=50,
        district="Okara",
        quoted_price_per_maund=3800.0,
    )
    def _weather_boom(_district: str):
        raise RuntimeError("toy: no network in unit tests")

    result = analyze(
        req,
        band_fn=fake_get_band,
        weather_fn=_weather_boom,
    )
    # Nearest usable to Okara among Faisalabad/Lahore is Faisalabad
    assert result.verdict.reference_market == "Faisalabad"
    assert "Faisalabad" in (result.verdict.reason or "")
    assert "not Okara" in (result.verdict.reason or "")
    AnalysisResult.model_validate(result.model_dump())


def test_potato_variant_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_get_band(city, commodity, as_of=None, df=None):
        calls.append((city, commodity))
        if commodity == "Potato Fresh":
            return _toy_band(2000.0, 2400.0, 2200.0)
        if commodity == "Potato Store":
            return _none_band("toy: store empty")
        return _none_band()

    monkeypatch.setattr("analysis.routing.get_band", fake_get_band)
    req = ParsedFarmerRequest(
        crop="Potato",
        quantity_maunds=35,
        district="Kasur",
        quoted_price_per_maund=2000.0,
    )
    ranked = rank_markets(req, band_fn=fake_get_band)
    # Preference tries Store first (none), then Fresh (usable)
    assert any(c == "Potato Store" for _, c in calls)
    assert any(c == "Potato Fresh" for _, c in calls)
    assert ranked  # some city with Fresh band
    assert all(r.gross_price_maund == 2200.0 for r in ranked)


def test_analyze_outputs_validate_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get_band(city, commodity, as_of=None, df=None):
        if commodity == "Tomato":
            return _toy_band(5000.0, 6000.0, 5500.0)
        return _none_band()

    monkeypatch.setattr("analysis.analyze.get_band", fake_get_band)
    monkeypatch.setattr("analysis.routing.get_band", fake_get_band)

    req = ParsedFarmerRequest(
        crop="Tomato",
        quantity_maunds=40,
        district="Okara",
        quoted_price_per_maund=2800.0,
    )
    def _weather_boom(_district: str):
        raise RuntimeError("toy: no network in unit tests")

    result = analyze(
        req,
        band_fn=fake_get_band,
        weather_fn=_weather_boom,
    )
    assert result.advisory is None
    assert result.disclaimers
    assert any("WHOLESALE" in d.upper() for d in result.disclaimers)
    assert any("Weather forecast unavailable" in d for d in result.disclaimers)
    AnalysisResult.model_validate(result.model_dump())


def test_analyze_no_markets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "analysis.analyze.get_band",
        lambda *a, **k: _none_band(),
    )
    monkeypatch.setattr(
        "analysis.routing.get_band",
        lambda *a, **k: _none_band(),
    )
    req = ParsedFarmerRequest(
        crop="Tomato",
        quantity_maunds=10,
        district="Lahore",
        quoted_price_per_maund=1000.0,
    )
    result = analyze(req, band_fn=lambda *a, **k: _none_band())
    assert result.verdict.verdict_status == "Unable to assess"
    assert result.top_cities == []
    AnalysisResult.model_validate(result.model_dump())
