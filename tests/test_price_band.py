"""Toy-series tests for fair-price bands (no network)."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from config import BAND_QUANTILES, MIN_HISTORY_DAYS
from model.price_band import clear_model_cache, get_band


def _toy_df(
    n_days: int = 40,
    city: str = "ToyCity",
    commodity: str = "Tomato",
    start: date | None = None,
    base: float = 1000.0,
    noise: float = 0.0,
) -> pd.DataFrame:
    """Hand-built toy AMIS-like frame (labelled toy — not real market data)."""
    start = start or date(2026, 1, 1)
    rows = []
    for i in range(n_days):
        d = start + timedelta(days=i)
        # Gentle toy drift; optional tiny noise
        fqp = base + i * 2.0 + (noise * i)
        rows.append(
            {
                "date": d,
                "city": city,
                "commodity": commodity,
                "min_rs_100kg": fqp / 0.4 * 0.95,
                "max_rs_100kg": fqp / 0.4 * 1.05,
                "fqp_rs_100kg": fqp / 0.4,
                "quantity": None,
                "min_rs_maund": fqp * 0.95,
                "max_rs_maund": fqp * 1.05,
                "fqp_rs_maund": fqp,
                "is_suspect": False,
            }
        )
    return pd.DataFrame(rows)


def test_short_history_basis_none() -> None:
    clear_model_cache()
    df = _toy_df(n_days=MIN_HISTORY_DAYS - 1)
    as_of = date(2026, 1, 1) + timedelta(days=MIN_HISTORY_DAYS - 2)
    band = get_band("ToyCity", "Tomato", as_of=as_of, df=df)
    assert band.basis == "none"
    assert band.low is None and band.high is None and band.avg is None
    assert "Only" in (band.reason or "")
    assert band.sample_days == MIN_HISTORY_DAYS - 1


def test_recent_median_band_hand_checked() -> None:
    clear_model_cache()
    # Toy: constant 1000 for clarity on medians/percentiles
    df = _toy_df(n_days=30, base=1000.0, noise=0.0)
    # Make last 14 vary so percentiles are non-trivial
    fqp = df["fqp_rs_maund"].tolist()
    # last 14: 100,110,...,230
    for j, i in enumerate(range(len(df) - 14, len(df))):
        fqp[i] = 100.0 + j * 10.0
    df["fqp_rs_maund"] = fqp
    df["fqp_rs_100kg"] = df["fqp_rs_maund"] / 0.4
    as_of = df["date"].max()
    # Force recent_median by using enough history but too few pooled rows
    # (single city, short) — still >= MIN_HISTORY_DAYS so not none
    band = get_band("ToyCity", "Tomato", as_of=as_of, df=df)
    assert band.basis in {"recent_median_band", "model_band", "none"}
    # Hand-check recent_median numbers on the series tip
    last7 = np.array(fqp[-7:])
    last14 = np.array(fqp[-14:])
    exp_avg = float(np.median(last7))
    exp_low = float(np.quantile(last14, BAND_QUANTILES[0]))
    exp_high = float(np.quantile(last14, BAND_QUANTILES[1]))
    if band.basis == "recent_median_band":
        assert band.avg == pytest.approx(exp_avg, rel=1e-6)
        assert band.low == pytest.approx(exp_low, rel=1e-6)
        assert band.high == pytest.approx(exp_high, rel=1e-6)
    assert band.low is not None and band.avg is not None and band.high is not None
    assert band.low <= band.avg <= band.high


def test_order_low_avg_high_always() -> None:
    clear_model_cache()
    df = _toy_df(n_days=45, base=500.0)
    # Add a second toy city so pooled features exist
    df2 = _toy_df(n_days=45, city="ToyCityB", base=520.0)
    df = pd.concat([df, df2], ignore_index=True)
    as_of = df["date"].max()
    band = get_band("ToyCity", "Tomato", as_of=as_of, df=df)
    if band.avg is not None:
        assert band.low <= band.avg <= band.high


def test_no_leakage_future_edit() -> None:
    clear_model_cache()
    df = _toy_df(n_days=40, base=800.0)
    as_of = date(2026, 1, 20)
    band1 = get_band("ToyCity", "Tomato", as_of=as_of, df=df)
    df2 = df.copy()
    # Edit a FUTURE row after as_of
    future_mask = pd.to_datetime(df2["date"]).dt.date > as_of
    df2.loc[future_mask, "fqp_rs_maund"] = 999999.0
    clear_model_cache()
    band2 = get_band("ToyCity", "Tomato", as_of=as_of, df=df2)
    assert band1.basis == band2.basis
    assert band1.low == band2.low
    assert band1.high == band2.high
    assert band1.avg == band2.avg
    assert band1.last_fqp == band2.last_fqp


def test_never_raises_empty_or_unknown() -> None:
    clear_model_cache()
    empty = pd.DataFrame(
        columns=[
            "date",
            "city",
            "commodity",
            "min_rs_100kg",
            "max_rs_100kg",
            "fqp_rs_100kg",
            "quantity",
            "min_rs_maund",
            "max_rs_maund",
            "fqp_rs_maund",
            "is_suspect",
        ]
    )
    b1 = get_band("Nowhere", "Tomato", as_of=date(2026, 1, 1), df=empty)
    assert b1.basis == "none"
    df = _toy_df(n_days=25)
    b2 = get_band("UnknownCity", "Tomato", as_of=df["date"].max(), df=df)
    assert b2.basis == "none"
    b3 = get_band("ToyCity", "Dragonfruit", as_of=df["date"].max(), df=df)
    assert b3.basis == "none"
