"""Observed wholesale price trend from AMIS FQP history (not a forecast)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal, Optional

import pandas as pd

from config import (
    TREND_LOOKBACK_DAYS,
    TREND_MIN_OBS,
    TREND_THRESHOLD_PCT,
    TREND_WINDOW,
)
from data.store import load_prices

logger = logging.getLogger(__name__)

TrendLabel = Literal["Rising", "Flat", "Falling"]


@dataclass
class TrendResult:
    label: Optional[TrendLabel]
    pct_change: Optional[float]
    n_obs: int
    reason: str


def get_price_trend(
    city: str,
    commodity: str,
    as_of: Optional[date] = None,
    df: Optional[pd.DataFrame] = None,
) -> TrendResult:
    """Median FQP of last 7 obs vs prior 7; never raises; no leakage past as_of."""
    try:
        as_of = as_of or date.today()
        if df is None:
            df = load_prices()
        if df is None or df.empty:
            return TrendResult(None, None, 0, "No price data")

        work = df.copy()
        work["date"] = pd.to_datetime(work["date"]).dt.date
        if "is_suspect" in work.columns:
            work = work[work["is_suspect"] == False]  # noqa: E712
        work = work[
            (work["city"] == city)
            & (work["commodity"] == commodity)
            & (work["date"] <= as_of)
            & (work["date"] >= as_of - timedelta(days=TREND_LOOKBACK_DAYS))
        ]
        work = work.dropna(subset=["fqp_rs_maund"])
        work = work[work["fqp_rs_maund"] > 0].sort_values("date")
        n = len(work)
        if n < TREND_MIN_OBS:
            return TrendResult(
                None,
                None,
                n,
                f"Only {n} valid observations in last {TREND_LOOKBACK_DAYS} days "
                f"(need >= {TREND_MIN_OBS})",
            )
        if n < 2 * TREND_WINDOW:
            return TrendResult(
                None,
                None,
                n,
                f"Need at least {2 * TREND_WINDOW} observations for trend windows",
            )

        fqp = work["fqp_rs_maund"].astype(float).tolist()
        recent = fqp[-TREND_WINDOW:]
        prior = fqp[-2 * TREND_WINDOW : -TREND_WINDOW]
        med_recent = float(pd.Series(recent).median())
        med_prior = float(pd.Series(prior).median())
        if med_prior <= 0:
            return TrendResult(None, None, n, "Prior median is zero")
        pct = (med_recent - med_prior) / med_prior * 100.0
        if pct > TREND_THRESHOLD_PCT:
            label: Optional[TrendLabel] = "Rising"
        elif pct < -TREND_THRESHOLD_PCT:
            label = "Falling"
        else:
            label = "Flat"
        return TrendResult(
            label,
            pct,
            n,
            (
                f"Median FQP last {TREND_WINDOW} vs prior {TREND_WINDOW} obs "
                f"at {city}/{commodity}: {pct:+.2f}% "
                f"(threshold ±{TREND_THRESHOLD_PCT}%)"
            ),
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("get_price_trend failed: %s", exc)
        return TrendResult(None, None, 0, f"error: {exc}")
