"""Unit tests for AMIS cleaning and maund conversion."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from data.cleaning import clean, to_per_maund


def test_to_per_maund_11750() -> None:
    # 11,750 Rs/100 kg → 4,700 Rs/maund (× 0.4)
    assert to_per_maund(11750) == 4700.0


def test_to_per_maund_zero_and_none() -> None:
    assert to_per_maund(0) == 0.0
    assert to_per_maund(None) is None


def test_suspect_flag_band_and_median_toy() -> None:
    """Hand-written toy numbers (test-only) for is_suspect logic."""
    base = date(2026, 1, 1)
    rows = []
    # 14 days of stable FQP=1000 for city A / Wheat
    for i in range(14):
        rows.append(
            {
                "date": base + timedelta(days=i),
                "city": "ToyCity",
                "commodity": "Wheat",
                "min_rs_100kg": 900.0,
                "max_rs_100kg": 1100.0,
                "fqp_rs_100kg": 1000.0,
                "quantity": None,
            }
        )
    # Day 14: band violation min > fqp
    rows.append(
        {
            "date": base + timedelta(days=14),
            "city": "ToyCity",
            "commodity": "Wheat",
            "min_rs_100kg": 2000.0,
            "max_rs_100kg": 3000.0,
            "fqp_rs_100kg": 1000.0,
            "quantity": None,
        }
    )
    # Day 15: FQP 10x median → outside 0.3x–3x
    rows.append(
        {
            "date": base + timedelta(days=15),
            "city": "ToyCity",
            "commodity": "Wheat",
            "min_rs_100kg": 9000.0,
            "max_rs_100kg": 11000.0,
            "fqp_rs_100kg": 10000.0,
            "quantity": None,
        }
    )

    out = clean(pd.DataFrame(rows))
    assert "is_suspect" in out.columns
    assert "fqp_rs_maund" in out.columns
    # Stable days not suspect
    stable = out[out["date"] < base + timedelta(days=14)]
    assert not stable["is_suspect"].any()
    # Band violation
    band_row = out[out["date"] == base + timedelta(days=14)].iloc[0]
    assert bool(band_row["is_suspect"]) is True
    # Median spike
    spike = out[out["date"] == base + timedelta(days=15)].iloc[0]
    assert bool(spike["is_suspect"]) is True
    # Rows retained (flagged, not deleted)
    assert len(out) == len(rows)
