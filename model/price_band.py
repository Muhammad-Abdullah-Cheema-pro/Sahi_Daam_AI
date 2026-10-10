"""Fair-price band model over real AMIS per-maund FQP series."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal, Optional

import numpy as np
import pandas as pd

from config import (
    BAND_QUANTILES,
    HOLDOUT_DAYS,
    MIN_HISTORY_DAYS,
    MIN_MODEL_ROWS,
    POTATO_PREFERENCE,
    TARGET_CITIES,
)
from data.store import load_prices

logger = logging.getLogger(__name__)

Basis = Literal["model_band", "recent_median_band", "none"]

# In-memory cache: (commodity, as_of_iso) -> trained quantile models + city columns
_MODEL_CACHE: dict[tuple[str, str], dict[str, Any]] = {}

_FEATURE_LAGS = (1, 2, 3, 7)


@dataclass
class BandResult:
    low: Optional[float]
    high: Optional[float]
    avg: Optional[float]
    basis: Basis
    sample_days: int
    data_as_of: Optional[date]
    reason: Optional[str]
    last_fqp: Optional[float]


def _as_date(d: Any) -> date:
    if isinstance(d, date) and not isinstance(d, pd.Timestamp):
        return d
    return pd.to_datetime(d).date()


def _prepare_frame(df: pd.DataFrame, as_of: date) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    work = df.copy()
    work["date"] = pd.to_datetime(work["date"]).dt.date
    if "is_suspect" in work.columns:
        work = work[work["is_suspect"] == False]  # noqa: E712
    work = work[work["date"] <= as_of]
    work = work.dropna(subset=["fqp_rs_maund"])
    work = work[work["fqp_rs_maund"] > 0]
    return work.sort_values(["commodity", "city", "date"]).reset_index(drop=True)


def _resolve_commodity(work: pd.DataFrame, city: str, commodity: str) -> Optional[str]:
    """Map Potato → preferred AMIS row present for the city."""
    if commodity in work["commodity"].values:
        # Prefer exact name when present for this city
        if not work[(work["city"] == city) & (work["commodity"] == commodity)].empty:
            return commodity
        if commodity != "Potato":
            return commodity
    if commodity in {"Potato", "potato"}:
        for pref in POTATO_PREFERENCE:
            if not work[(work["city"] == city) & (work["commodity"] == pref)].empty:
                return pref
        for pref in POTATO_PREFERENCE:
            if pref in set(work["commodity"]):
                return pref
    return commodity if commodity in set(work["commodity"]) else None


def _city_series(work: pd.DataFrame, city: str, commodity: str) -> pd.DataFrame:
    g = work[(work["city"] == city) & (work["commodity"] == commodity)].copy()
    return g.sort_values("date").reset_index(drop=True)


def _recent_median_band(series: pd.DataFrame) -> tuple[float, float, float, str]:
    fqp = series["fqp_rs_maund"].astype(float)
    last7 = fqp.tail(7)
    last14 = fqp.tail(14)
    q_lo, q_hi = BAND_QUANTILES
    avg = float(last7.median())
    low = float(last14.quantile(q_lo))
    high = float(last14.quantile(q_hi))
    low, avg, high = _enforce_order(low, avg, high)
    reason = (
        f"recent_median_band: median(last 7) with "
        f"{int(q_lo*100)}th/{int(q_hi*100)}th pct of last 14 obs"
    )
    return low, avg, high, reason


def _enforce_order(
    low: Optional[float], avg: Optional[float], high: Optional[float]
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    if low is None or avg is None or high is None:
        return low, avg, high
    if low > high:
        low, high = high, low
    avg = min(max(avg, low), high)
    return float(low), float(avg), float(high)


def _other_cities_mean(
    work: pd.DataFrame, city: str, commodity: str, on_or_before: date
) -> Optional[float]:
    sub = work[
        (work["commodity"] == commodity)
        & (work["city"] != city)
        & (work["date"] <= on_or_before)
    ]
    if sub.empty:
        return None
    latest = sub.sort_values("date").groupby("city", as_index=False).tail(1)
    vals = latest["fqp_rs_maund"].astype(float)
    if vals.empty:
        return None
    return float(vals.mean())


def _row_features(
    series: pd.DataFrame,
    i: int,
    work: pd.DataFrame,
    commodity: str,
    city: str,
) -> Optional[dict[str, float]]:
    """Features for predicting the step after index i (using only rows <= i)."""
    if i < 13:  # need lag-7 and full 14-obs rolling windows (no wrap)
        return None
    row = series.iloc[i]
    last_fqp = float(row["fqp_rs_maund"])
    if last_fqp <= 0:
        return None
    fqp = series["fqp_rs_maund"].astype(float).values
    dates = list(series["date"])

    feats: dict[str, float] = {}
    for lag in _FEATURE_LAGS:
        if i - lag < 0 or fqp[i - lag] <= 0:
            return None
        feats[f"ret_lag_{lag}"] = float(last_fqp / fqp[i - lag] - 1.0)

    for win in (7, 14):
        start = i - win + 1
        window = fqp[start : i + 1]
        if len(window) < win:
            return None
        feats[f"roll_mean_{win}_rel"] = float(np.mean(window) / last_fqp)
        feats[f"roll_std_{win}_rel"] = float(np.std(window) / last_fqp)

    d = _as_date(dates[i])
    feats["dow"] = float(d.weekday())
    if i > 0:
        feats["gap_days"] = float((_as_date(dates[i]) - _as_date(dates[i - 1])).days)
    else:
        feats["gap_days"] = 1.0

    mn = row.get("min_rs_maund")
    mx = row.get("max_rs_maund")
    if pd.notna(mn) and pd.notna(mx) and last_fqp > 0:
        feats["spread_rel"] = float((float(mx) - float(mn)) / last_fqp)
    else:
        feats["spread_rel"] = 0.0

    other = _other_cities_mean(work, city, commodity, d)
    if other is None or other <= 0:
        feats["other_cities_rel"] = 1.0
    else:
        feats["other_cities_rel"] = float(other / last_fqp)

    return feats


def _build_training_table(
    work: pd.DataFrame, commodity: str
) -> tuple[pd.DataFrame, list[str]]:
    """Pooled training rows for one commodity. Target = next_fqp/last_fqp - 1."""
    cities = sorted(work.loc[work["commodity"] == commodity, "city"].unique())
    records: list[dict[str, Any]] = []
    for city in cities:
        series = _city_series(work, city, commodity)
        if len(series) < 9:
            continue
        for i in range(len(series) - 1):
            feats = _row_features(series, i, work, commodity, city)
            if feats is None:
                continue
            last_fqp = float(series.iloc[i]["fqp_rs_maund"])
            next_fqp = float(series.iloc[i + 1]["fqp_rs_maund"])
            if last_fqp <= 0 or next_fqp <= 0:
                continue
            rec = dict(feats)
            rec["target"] = next_fqp / last_fqp - 1.0
            rec["last_fqp"] = last_fqp
            rec["next_fqp"] = next_fqp
            rec["city"] = city
            rec["date"] = _as_date(series.iloc[i]["date"])
            rec["target_date"] = _as_date(series.iloc[i + 1]["date"])
            records.append(rec)

    if not records:
        return pd.DataFrame(), []

    df = pd.DataFrame(records)
    city_cols: list[str] = []
    for city in cities:
        col = f"city_{city}"
        df[col] = (df["city"] == city).astype(float)
        city_cols.append(col)
    feature_cols = [
        c
        for c in df.columns
        if c
        not in {
            "target",
            "last_fqp",
            "next_fqp",
            "city",
            "date",
            "target_date",
        }
    ]
    return df, feature_cols


def _train_quantile_models(
    train: pd.DataFrame, feature_cols: list[str]
) -> dict[str, Any]:
    from sklearn.ensemble import GradientBoostingRegressor

    X = train[feature_cols].astype(float).values
    y = train["target"].astype(float).values
    models = {}
    for alpha, name in ((0.1, "q10"), (0.5, "q50"), (0.9, "q90")):
        m = GradientBoostingRegressor(
            loss="quantile",
            alpha=alpha,
            n_estimators=150,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.8,
            random_state=0,
        )
        m.fit(X, y)
        models[name] = m
    return {"models": models, "feature_cols": feature_cols}


def _predict_quantiles(
    packed: dict[str, Any], feats: dict[str, float], city: str
) -> tuple[float, float, float]:
    cols = packed["feature_cols"]
    row = dict(feats)
    for c in cols:
        if c.startswith("city_"):
            row[c] = 1.0 if c == f"city_{city}" else 0.0
        else:
            row.setdefault(c, 0.0)
    X = np.array([[row[c] for c in cols]], dtype=float)
    q10 = float(packed["models"]["q10"].predict(X)[0])
    q50 = float(packed["models"]["q50"].predict(X)[0])
    q90 = float(packed["models"]["q90"].predict(X)[0])
    return q10, q50, q90


def _holdout_selection(
    work: pd.DataFrame, commodity: str, as_of: date
) -> tuple[Basis, str, Optional[dict[str, Any]]]:
    """Choose model_band vs recent_median_band; return basis, reason, cached models."""
    table, feature_cols = _build_training_table(work, commodity)
    n_rows = len(table)
    if n_rows == 0:
        return (
            "recent_median_band",
            "model skipped: no training rows; using recent_median_band",
            None,
        )

    holdout_start = as_of - timedelta(days=HOLDOUT_DAYS)
    train = table[table["target_date"] < holdout_start]
    test = table[
        (table["target_date"] >= holdout_start) & (table["target_date"] <= as_of)
    ]

    if len(train) < 20 or test.empty:
        return (
            "recent_median_band",
            (
                f"model skipped: train={len(train)} test={len(test)} "
                f"(need holdout); using recent_median_band"
            ),
            None,
        )

    if n_rows < MIN_MODEL_ROWS:
        return (
            "recent_median_band",
            (
                f"model skipped: only {n_rows} rows < MIN_MODEL_ROWS={MIN_MODEL_ROWS}; "
                f"using recent_median_band"
            ),
            None,
        )

    packed = _train_quantile_models(train, feature_cols)
    y_true = test["next_fqp"].astype(float).values
    naive = test["last_fqp"].astype(float).values
    preds = []
    lo_b, hi_b = [], []
    for _, r in test.iterrows():
        feats = {
            c: float(r[c])
            for c in feature_cols
            if not c.startswith("city_")
        }
        q10, q50, q90 = _predict_quantiles(packed, feats, str(r["city"]))
        last = float(r["last_fqp"])
        pred = last * (1.0 + q50)
        preds.append(pred)
        lo_b.append(last * (1.0 + q10))
        hi_b.append(last * (1.0 + q90))
    preds_a = np.array(preds, dtype=float)
    lo_a = np.array(lo_b, dtype=float)
    hi_a = np.array(hi_b, dtype=float)
    # enforce per-row order for coverage
    lo_a = np.minimum(lo_a, hi_a)
    hi_a = np.maximum(lo_a, hi_a)

    mae_model = float(np.mean(np.abs(preds_a - y_true)))
    mae_naive = float(np.mean(np.abs(naive - y_true)))
    cover = float(np.mean((y_true >= lo_a) & (y_true <= hi_a)))

    use_model = (
        n_rows >= MIN_MODEL_ROWS
        and mae_model < mae_naive
        and 0.65 <= cover <= 0.95
    )
    # Retrain on all data <= as_of for deployment
    packed_full = _train_quantile_models(table, feature_cols)
    if use_model:
        reason = (
            f"model_band selected: n={n_rows}, holdout MAE model={mae_model:.2f} "
            f"< naive={mae_naive:.2f}, 80% band coverage={cover:.2%} in [0.65,0.95]"
        )
        return "model_band", reason, packed_full

    reason = (
        f"recent_median_band selected: n={n_rows}, holdout MAE model={mae_model:.2f} "
        f"vs naive={mae_naive:.2f}, coverage={cover:.2%} "
        f"(need MAE_model<MAE_naive and coverage in [0.65,0.95])"
    )
    return "recent_median_band", reason, packed_full


def get_band(
    city: str,
    commodity: str,
    as_of: Optional[date] = None,
    df: Optional[pd.DataFrame] = None,
) -> BandResult:
    """Return a fair-price band. Never raises."""
    try:
        as_of = as_of or date.today()
        if df is None:
            df = load_prices()
        work = _prepare_frame(df, as_of)
        if work.empty:
            return BandResult(
                None, None, None, "none", 0, None,
                "No price rows available", None,
            )

        resolved = _resolve_commodity(work, city, commodity)
        if resolved is None:
            return BandResult(
                None, None, None, "none", 0, None,
                f"No data for {commodity} in {city}", None,
            )
        commodity = resolved

        series = _city_series(work, city, commodity)
        if series.empty:
            return BandResult(
                None, None, None, "none", 0, None,
                f"Only 0 days of data for {commodity} in {city}", None,
            )

        window_start = as_of - timedelta(days=60)
        recent = series[series["date"] >= window_start]
        sample_days = int(len(recent))
        data_as_of = _as_date(series.iloc[-1]["date"])
        last_fqp = float(series.iloc[-1]["fqp_rs_maund"])

        if sample_days < MIN_HISTORY_DAYS:
            return BandResult(
                None,
                None,
                None,
                "none",
                sample_days,
                data_as_of,
                f"Only {sample_days} days of data for {commodity} in {city}",
                last_fqp,
            )

        cache_key = (commodity, as_of.isoformat())
        if cache_key in _MODEL_CACHE:
            cached = _MODEL_CACHE[cache_key]
            basis = cached["basis"]
            sel_reason = cached["reason"]
            packed = cached.get("packed")
        else:
            basis, sel_reason, packed = _holdout_selection(work, commodity, as_of)
            _MODEL_CACHE[cache_key] = {
                "basis": basis,
                "reason": sel_reason,
                "packed": packed,
            }

        if basis == "model_band" and packed is not None:
            i = len(series) - 1
            feats = _row_features(series, i, work, commodity, city)
            if feats is None:
                low, avg, high, r2 = _recent_median_band(series)
                return BandResult(
                    low, high, avg, "recent_median_band", sample_days, data_as_of,
                    sel_reason + "; fallback recent_median (insufficient lags at tip)",
                    last_fqp,
                )
            q10, q50, q90 = _predict_quantiles(packed, feats, city)
            low = last_fqp * (1.0 + q10)
            avg = last_fqp * (1.0 + q50)
            high = last_fqp * (1.0 + q90)
            low, avg, high = _enforce_order(low, avg, high)
            return BandResult(
                low, high, avg, "model_band", sample_days, data_as_of, sel_reason, last_fqp
            )

        low, avg, high, r2 = _recent_median_band(series)
        return BandResult(
            low,
            high,
            avg,
            "recent_median_band",
            sample_days,
            data_as_of,
            f"{sel_reason} | {r2}",
            last_fqp,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("get_band failed: %s", exc)
        return BandResult(
            None, None, None, "none", 0, None, f"error: {exc}", None
        )


def clear_model_cache() -> None:
    _MODEL_CACHE.clear()
