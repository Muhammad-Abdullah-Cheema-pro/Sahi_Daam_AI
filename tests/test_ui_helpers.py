"""Unit tests for ui_helpers (no Streamlit)."""

from __future__ import annotations

from datetime import date

from schema import (
    AnalysisResult,
    CityMarginResult,
    FairPriceVerdict,
    HarvestAdvisory,
    ParsedFarmerRequest,
)
from ui_helpers import (
    STATUS_STYLE,
    build_urdu_summary,
    format_city_rows,
    verdict_sentence,
)

_FORBIDDEN = ("cheat", "fraud", "scam", "lying", "gouging")


def _req(**kwargs):
    base = dict(
        crop="Tomato",
        quantity_maunds=40,
        district="Okara",
        quoted_price_per_maund=2800.0,
    )
    base.update(kwargs)
    return ParsedFarmerRequest(**base)


def _verdict(status: str, **kwargs) -> FairPriceVerdict:
    data = dict(
        reference_market="Okara",
        predicted_low_maund=5000.0,
        predicted_high_maund=6000.0,
        predicted_avg_maund=5500.0,
        verdict_status=status,
        percentage_gap=-49.0,
        basis="recent_median_band",
        reason="toy reason WHOLESALE",
        data_as_of=date(2026, 10, 1),
        sample_days=14,
    )
    if status == "Unable to assess":
        data["percentage_gap"] = None
    data.update(kwargs)
    return FairPriceVerdict(**data)


def test_status_style_all_four() -> None:
    for status in ("Fair", "Low", "Very low", "Unable to assess"):
        assert status in STATUS_STYLE
        assert STATUS_STYLE[status]["emoji"]
        assert STATUS_STYLE[status]["label"]
        assert STATUS_STYLE[status]["color"]


def test_verdict_sentence_no_forbidden_words() -> None:
    for status in ("Fair", "Low", "Very low", "Unable to assess"):
        text = verdict_sentence(_verdict(status)).lower()
        for word in _FORBIDDEN:
            assert word not in text
        assert "wholesale" in text or "farm-gate" in text


def test_format_city_rows_hides_gain_without_quote() -> None:
    cities = [
        CityMarginResult(
            city_name="Lahore",
            distance_km=10.0,
            gross_price_maund=5500.0,
            net_price_maund=5200.0,
            net_gain_vs_quote=100.0,
            break_even_price=5100.0,
            assumptions="toy",
        )
    ]
    with_q = format_city_rows(cities, has_quote=True)
    without = format_city_rows(cities, has_quote=False)
    assert "Net gain vs quote" in with_q[0]
    assert "Net gain vs quote" not in without[0]


def test_build_urdu_summary_all_statuses() -> None:
    city = CityMarginResult(
        city_name="Faisalabad",
        distance_km=50.0,
        gross_price_maund=5700.0,
        net_price_maund=5400.0,
        net_gain_vs_quote=200.0,
        break_even_price=5000.0,
        assumptions="toy",
    )
    adv = HarvestAdvisory(
        weather_risk="Low",
        price_trend="Rising",
        action_advice="Shade and ventilate.",
    )
    for status in ("Fair", "Low", "Very low", "Unable to assess"):
        for has_quote in (True, False):
            for has_adv in (True, False):
                req = _req(
                    quoted_price_per_maund=2800.0 if has_quote else None,
                )
                v = _verdict(status)
                result = AnalysisResult(
                    request=req,
                    verdict=v,
                    advisory=adv if has_adv else None,
                    top_cities=[city],
                    disclaimers=["toy"],
                )
                text = build_urdu_summary(result)
                assert text.strip()
                assert "ہول سیل" in text or "معذرت" in text


def test_urdu_summary_rising_branch() -> None:
    adv = HarvestAdvisory(
        weather_risk="Low",
        price_trend="Rising",
        action_advice="Shade.",
    )
    result = AnalysisResult(
        request=_req(quoted_price_per_maund=2800.0),
        verdict=_verdict("Fair"),
        advisory=adv,
        top_cities=[],
        disclaimers=[],
    )
    text = build_urdu_summary(result)
    assert "قیمتیں بڑھ رہی ہیں" in text
