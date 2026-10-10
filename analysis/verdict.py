"""Fair-price quote assessment against a wholesale band."""

from __future__ import annotations

from typing import Optional

from config import FARMGATE_ALLOWANCE, VERY_LOW_RATIO
from model.price_band import BandResult
from schema import FairPriceVerdict


def _band_usable(band: BandResult) -> bool:
    return (
        band.basis != "none"
        and band.low is not None
        and band.high is not None
        and band.avg is not None
        and band.avg > 0
    )


def assess_quote(
    quote: Optional[float],
    band: BandResult,
    reference_market: str,
) -> FairPriceVerdict:
    """Compare a farmer quote (Rs/maund) to a WHOLESALE band. Never invent prices."""
    prices = {
        "predicted_low_maund": band.low,
        "predicted_high_maund": band.high,
        "predicted_avg_maund": band.avg,
        "data_as_of": band.data_as_of,
        "sample_days": band.sample_days,
        "basis": band.basis,
    }

    if not _band_usable(band):
        reason = (
            band.reason
            or "No usable WHOLESALE price band for this market/commodity."
        )
        if "WHOLESALE" not in reason.upper() and "wholesale" not in reason.lower():
            reason = reason.rstrip(".") + ". Comparison is against WHOLESALE prices."
        return FairPriceVerdict(
            reference_market=reference_market,
            verdict_status="Unable to assess",
            percentage_gap=None,
            reason=reason,
            **prices,
        )

    assert band.low is not None and band.avg is not None and band.high is not None

    if quote is None:
        return FairPriceVerdict(
            reference_market=reference_market,
            predicted_low_maund=band.low,
            predicted_high_maund=band.high,
            predicted_avg_maund=band.avg,
            verdict_status="Unable to assess",
            percentage_gap=None,
            basis=band.basis,
            data_as_of=band.data_as_of,
            sample_days=band.sample_days,
            reason=(
                "No quoted price given. Showing WHOLESALE band only "
                "(not farm-gate). Comparison would be against WHOLESALE prices."
            ),
        )

    adj_low = band.low * (1.0 - FARMGATE_ALLOWANCE)
    gap = (float(quote) - band.avg) / band.avg * 100.0

    if quote >= adj_low:
        status = "Fair"
        detail = (
            f"Quote is at or above farm-gate-adjusted WHOLESALE low "
            f"(adj_low={adj_low:.0f} Rs/maund = band.low×(1−{FARMGATE_ALLOWANCE}))."
        )
    elif quote >= VERY_LOW_RATIO * adj_low:
        status = "Low"
        detail = (
            f"Quote is below the farm-gate-adjusted WHOLESALE low "
            f"(adj_low={adj_low:.0f}) but not under {VERY_LOW_RATIO:.0%} of adj_low "
            f"— below wholesale range."
        )
    else:
        status = "Very low"
        detail = (
            f"Quote is under {VERY_LOW_RATIO:.0%} of farm-gate-adjusted WHOLESALE low "
            f"(adj_low={adj_low:.0f}) — below wholesale range."
        )

    reason = (
        f"{detail} Comparison is against WHOLESALE prices "
        f"(basis={band.basis})."
    )
    return FairPriceVerdict(
        reference_market=reference_market,
        predicted_low_maund=band.low,
        predicted_high_maund=band.high,
        predicted_avg_maund=band.avg,
        verdict_status=status,  # type: ignore[arg-type]
        percentage_gap=gap,
        basis=band.basis,
        data_as_of=band.data_as_of,
        sample_days=band.sample_days,
        reason=reason,
    )
