"""Tests for analysis.trend.get_price_trend (no network)."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from analysis.trend import get_price_trend
from config import TREND_THRESHOLD_PCT


def _series(
    city: str,
    commodity: str,
    start: date,
    values: list[float],
) -> pd.DataFrame:
    rows = []
    for i, v in enumerate(values):
        rows.append(
            {
                "date": start + timedelta(days=i),
                "city": city,
                "commodity": commodity,
                "fqp_rs_maund": v,
                "fqp_rs_100kg": v / 0.4,
                "is_suspect": False,
            }
        )
    return pd.DataFrame(rows)


def test_threshold_exactly_plus_3_is_flat() -> None:
    # prior median 100; recent median 103 → +3.0% → Flat (not Rising)
    prior = [100.0] * 7
    recent = [103.0] * 7
    df = _series("Lahore", "Tomato", date(2026, 9, 1), prior + recent)
    as_of = date(2026, 9, 14)
    r = get_price_trend("Lahore", "Tomato", as_of=as_of, df=df)
    assert r.label == "Flat"
    assert r.pct_change is not None
    assert abs(r.pct_change - TREND_THRESHOLD_PCT) < 1e-9


def test_threshold_exactly_minus_3_is_flat() -> None:
    prior = [100.0] * 7
    recent = [97.0] * 7
    df = _series("Lahore", "Tomato", date(2026, 9, 1), prior + recent)
    r = get_price_trend("Lahore", "Tomato", as_of=date(2026, 9, 14), df=df)
    assert r.label == "Flat"


def test_above_threshold_rising() -> None:
    prior = [100.0] * 7
    recent = [104.0] * 7
    df = _series("Lahore", "Tomato", date(2026, 9, 1), prior + recent)
    r = get_price_trend("Lahore", "Tomato", as_of=date(2026, 9, 14), df=df)
    assert r.label == "Rising"


def test_below_threshold_falling() -> None:
    prior = [100.0] * 7
    recent = [96.0] * 7
    df = _series("Lahore", "Tomato", date(2026, 9, 1), prior + recent)
    r = get_price_trend("Lahore", "Tomato", as_of=date(2026, 9, 14), df=df)
    assert r.label == "Falling"


def test_thin_data_returns_none() -> None:
    df = _series("Lahore", "Tomato", date(2026, 9, 1), [100.0] * 5)
    r = get_price_trend("Lahore", "Tomato", as_of=date(2026, 9, 10), df=df)
    assert r.label is None
    assert r.n_obs < 10


def test_no_leakage_future_edit() -> None:
    base = [100.0] * 7 + [100.0] * 7
    df = _series("Lahore", "Tomato", date(2026, 9, 1), base)
    as_of = date(2026, 9, 14)
    before = get_price_trend("Lahore", "Tomato", as_of=as_of, df=df)
    # Add a huge future spike after as_of
    future = pd.DataFrame(
        [
            {
                "date": date(2026, 9, 20),
                "city": "Lahore",
                "commodity": "Tomato",
                "fqp_rs_maund": 9999.0,
                "fqp_rs_100kg": 9999.0 / 0.4,
                "is_suspect": False,
            }
        ]
    )
    df2 = pd.concat([df, future], ignore_index=True)
    after = get_price_trend("Lahore", "Tomato", as_of=as_of, df=df2)
    assert before.label == after.label
    assert before.pct_change == after.pct_change
    assert before.n_obs == after.n_obs
