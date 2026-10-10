"""Tests for Sahi Daam AI Pydantic schemas."""

from datetime import date

import pytest
from pydantic import ValidationError

from schema import (
    FairPriceVerdict,
    ParseOutcome,
    ParsedFarmerRequest,
)


def test_valid_full_request() -> None:
    req = ParsedFarmerRequest(
        crop="Wheat",
        quantity_maunds=50.0,
        district="Lahore",
        quoted_price_per_maund=3200.0,
        language_detected="ur",
        raw_transcript="Wheat fifty maund Lahore thirty two hundred",
    )
    assert req.quoted_price_per_maund == 3200.0
    assert req.crop_stage == "Ready to harvest"
    assert req.confidence == 1.0
    assert req.language_detected == "ur"
    assert req.raw_transcript is not None


def test_request_with_no_quote() -> None:
    req = ParsedFarmerRequest(
        crop="Tomato",
        quantity_maunds=10.0,
        district="Multan",
        quoted_price_per_maund=None,
    )
    assert req.quoted_price_per_maund is None


def test_unable_to_assess_without_prices_passes() -> None:
    verdict = FairPriceVerdict(
        reference_market="Lahore Grain Market",
        verdict_status="Unable to assess",
        basis="none",
        reason="No quoted price given",
    )
    assert verdict.predicted_low_maund is None
    assert verdict.predicted_high_maund is None
    assert verdict.predicted_avg_maund is None
    assert verdict.percentage_gap is None
    assert verdict.reason == "No quoted price given"


def test_unable_to_assess_with_band_and_any_basis_passes() -> None:
    """No quote: band may still be shown with non-none basis."""
    verdict = FairPriceVerdict(
        reference_market="Faisalabad",
        predicted_low_maund=3000.0,
        predicted_high_maund=3600.0,
        predicted_avg_maund=3300.0,
        verdict_status="Unable to assess",
        percentage_gap=None,
        basis="recent_median_band",
        reason="No quoted price given. Band is WHOLESALE reference only.",
        data_as_of=date(2026, 10, 1),
        sample_days=14,
    )
    assert verdict.basis == "recent_median_band"
    assert verdict.predicted_avg_maund == 3300.0


def test_fair_without_prices_fails() -> None:
    with pytest.raises(ValidationError):
        FairPriceVerdict(
            reference_market="Lahore Grain Market",
            verdict_status="Fair",
            basis="model_band",
        )


def test_high_less_than_low_fails() -> None:
    with pytest.raises(ValidationError):
        FairPriceVerdict(
            reference_market="Lahore Grain Market",
            predicted_low_maund=3600.0,
            predicted_high_maund=3000.0,
            predicted_avg_maund=3300.0,
            verdict_status="Fair",
            percentage_gap=-3.0,
            basis="model_band",
            data_as_of=date(2026, 10, 1),
            sample_days=14,
        )


def test_avg_outside_range_fails() -> None:
    with pytest.raises(ValidationError):
        FairPriceVerdict(
            reference_market="Lahore Grain Market",
            predicted_low_maund=3000.0,
            predicted_high_maund=3600.0,
            predicted_avg_maund=4000.0,
            verdict_status="Fair",
            percentage_gap=-3.0,
            basis="recent_median_band",
            data_as_of=date(2026, 10, 1),
            sample_days=7,
        )


def test_invalid_verdict_string_fails() -> None:
    with pytest.raises(ValidationError):
        FairPriceVerdict(
            reference_market="Lahore Grain Market",
            predicted_low_maund=3000.0,
            predicted_high_maund=3600.0,
            predicted_avg_maund=3300.0,
            verdict_status="Bargain",  # type: ignore[arg-type]
            percentage_gap=-3.0,
            basis="model_band",
        )


def test_parse_outcome_ok() -> None:
    outcome = ParseOutcome(
        status="ok",
        request=ParsedFarmerRequest(
            crop="Onion",
            quantity_maunds=20.0,
            district="Kasur",
            quoted_price_per_maund=1800.0,
        ),
        missing_fields=[],
        message="Request parsed successfully.",
    )
    assert outcome.status == "ok"
    assert outcome.request is not None
    assert outcome.missing_fields == []


def test_parse_outcome_needs_clarification() -> None:
    outcome = ParseOutcome(
        status="needs_clarification",
        request=None,
        missing_fields=["quantity_maunds", "district"],
        message="Please tell quantity in maunds and your district.",
    )
    assert outcome.status == "needs_clarification"
    assert outcome.missing_fields == ["quantity_maunds", "district"]


def test_parse_outcome_failed() -> None:
    outcome = ParseOutcome(
        status="failed",
        request=None,
        missing_fields=["crop", "quantity_maunds", "district"],
        message="Could not understand the request. Please say crop, quantity, and district.",
    )
    assert outcome.status == "failed"
    assert outcome.request is None
