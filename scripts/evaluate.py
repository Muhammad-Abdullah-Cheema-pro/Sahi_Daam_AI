"""Evaluate fair-price bands on real AMIS history; write reports/metrics.* (MEASURED)."""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402

    _HAS_MPL = True
except ImportError:
    plt = None  # type: ignore[assignment,misc]
    _HAS_MPL = False
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import HOLDOUT_DAYS, MIN_HISTORY_DAYS, MIN_MODEL_ROWS  # noqa: E402
from data.store import load_prices  # noqa: E402
from model.price_band import (  # noqa: E402
    _build_training_table,
    _predict_quantiles,
    _prepare_frame,
    _recent_median_band,
    _train_quantile_models,
    clear_model_cache,
)

FOLD_DAYS = 14
MAX_FOLDS = 4
NOMINAL_COVERAGE = 0.80
FIG_DIR = ROOT / "reports" / "figures"


def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mask = y_true != 0
    if not mask.any():
        return float("nan")
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100.0)


def _as_date_safe(d: Any) -> date:
    return pd.to_datetime(d).date()


def _thin_pair(
    work: pd.DataFrame, commodity: str, city: str, on_date: date
) -> bool:
    hist = work[
        (work["commodity"] == commodity)
        & (work["city"] == city)
        & (work["date"] <= on_date)
    ]
    window = hist[hist["date"] >= (on_date - timedelta(days=60))]
    return len(window) < MIN_HISTORY_DAYS


def _metrics_from_arrays(
    y: np.ndarray,
    naive: np.ndarray,
    recent: np.ndarray,
    model: np.ndarray,
    cover_recent: list[bool],
    cover_model: list[bool],
) -> dict[str, Any]:
    if len(y) == 0:
        nan = float("nan")
        return {
            "n_test": 0,
            "mae_naive": nan,
            "mae_recent_median": nan,
            "mae_model": nan,
            "mape_naive": nan,
            "mape_recent_median": nan,
            "mape_model": nan,
            "coverage_recent_pct": nan,
            "coverage_model_pct": nan,
            "model_beats_naive": False,
        }
    return {
        "n_test": int(len(y)),
        "mae_naive": float(np.mean(np.abs(naive - y))),
        "mae_recent_median": float(np.mean(np.abs(recent - y))),
        "mae_model": float(np.mean(np.abs(model - y))),
        "mape_naive": _mape(y, naive),
        "mape_recent_median": _mape(y, recent),
        "mape_model": _mape(y, model),
        "coverage_recent_pct": float(np.mean(cover_recent) * 100),
        "coverage_model_pct": float(np.mean(cover_model) * 100),
        "model_beats_naive": bool(np.mean(np.abs(model - y)) < np.mean(np.abs(naive - y))),
    }


def _fold_windows(as_of: date, earliest: date) -> list[tuple[date, date]]:
    """Up to MAX_FOLDS non-overlapping FOLD_DAYS windows ending at or before as_of."""
    folds: list[tuple[date, date]] = []
    end = as_of
    while len(folds) < MAX_FOLDS:
        start = end - timedelta(days=FOLD_DAYS - 1)
        if start < earliest:
            break
        folds.append((start, end))
        end = start - timedelta(days=1)
    folds.reverse()
    return folds


def _predict_on_test_rows(
    work: pd.DataFrame,
    commodity: str,
    train: pd.DataFrame,
    test: pd.DataFrame,
    feature_cols: list[str],
) -> tuple[list[dict[str, Any]], bool]:
    """Return per-row prediction records; second value = model trained ok."""
    records: list[dict[str, Any]] = []
    if test.empty:
        return records, False
    packed = None
    if len(train) >= 10:
        packed = _train_quantile_models(train, feature_cols)

    for _, r in test.iterrows():
        city = str(r["city"])
        pred_date = _as_date_safe(r["date"])
        if _thin_pair(work, commodity, city, pred_date):
            continue
        last = float(r["last_fqp"])
        actual = float(r["next_fqp"])
        series = work[
            (work["commodity"] == commodity)
            & (work["city"] == city)
            & (work["date"] <= pred_date)
        ].sort_values("date")
        low_r, avg_r, high_r, _ = _recent_median_band(series)
        cover_recent = low_r <= actual <= high_r

        if packed is None:
            m_pred = avg_r
            cover_model = cover_recent
            m_lo, m_hi = low_r, high_r
        else:
            feats = {
                c: float(r[c]) for c in feature_cols if not c.startswith("city_")
            }
            q10, q50, q90 = _predict_quantiles(packed, feats, city)
            m_lo, m_hi = last * (1 + q10), last * (1 + q90)
            if m_lo > m_hi:
                m_lo, m_hi = m_hi, m_lo
            m_pred = last * (1 + q50)
            cover_model = m_lo <= actual <= m_hi

        records.append(
            {
                "commodity": commodity,
                "city": city,
                "date": pred_date.isoformat(),
                "target_date": _as_date_safe(r["target_date"]).isoformat(),
                "actual": actual,
                "naive": last,
                "recent_avg": avg_r,
                "model_pred": m_pred,
                "cover_recent": cover_recent,
                "cover_model": cover_model,
                "err_model": abs(m_pred - actual),
            }
        )
    return records, packed is not None


def rolling_backtest(work: pd.DataFrame, as_of: date) -> dict[str, Any]:
    earliest = min(work["date"])
    folds = _fold_windows(as_of, earliest)
    all_rows: list[dict[str, Any]] = []
    fold_summaries: list[dict[str, Any]] = []

    for fold_i, (f_start, f_end) in enumerate(folds):
        fold_rows: list[dict[str, Any]] = []
        for commodity in sorted(work["commodity"].unique()):
            table, feature_cols = _build_training_table(work, commodity)
            if table.empty:
                continue
            train = table[table["target_date"] < f_start]
            test = table[
                (table["target_date"] >= f_start) & (table["target_date"] <= f_end)
            ]
            recs, _ = _predict_on_test_rows(
                work, commodity, train, test, feature_cols
            )
            fold_rows.extend(recs)
        fold_summaries.append(
            {
                "fold": fold_i + 1,
                "test_start": f_start.isoformat(),
                "test_end": f_end.isoformat(),
                "n_test": len(fold_rows),
            }
        )
        all_rows.extend(fold_rows)

    def _agg(group_key: str, key_val: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        sub = [r for r in rows if r[group_key] == key_val]
        if not sub:
            nan = float("nan")
            return {
                group_key: key_val,
                "n_test": 0,
                "skipped_thin": True,
                "mae_naive": nan,
                "mae_recent_median": nan,
                "mae_model": nan,
                "mape_naive": nan,
                "mape_recent_median": nan,
                "mape_model": nan,
                "coverage_recent_pct": nan,
                "coverage_model_pct": nan,
                "model_beats_naive": False,
            }
        y = np.array([r["actual"] for r in sub])
        n = np.array([r["naive"] for r in sub])
        ra = np.array([r["recent_avg"] for r in sub])
        m = np.array([r["model_pred"] for r in sub])
        cr = [r["cover_recent"] for r in sub]
        cm = [r["cover_model"] for r in sub]
        out = _metrics_from_arrays(y, n, ra, m, cr, cm)
        out[group_key] = key_val
        out["skipped_thin"] = False
        return out

    per_commodity = [
        _agg("commodity", c, all_rows)
        for c in sorted(work["commodity"].unique())
    ]
    per_city: list[dict[str, Any]] = []
    for commodity in sorted(work["commodity"].unique()):
        cities = sorted(
            work.loc[work["commodity"] == commodity, "city"].unique()
        )
        for city in cities:
            sub = [r for r in all_rows if r["commodity"] == commodity and r["city"] == city]
            if not sub:
                per_city.append(
                    {
                        "commodity": commodity,
                        "city": city,
                        "n_test": 0,
                        "skipped_thin": True,
                        "mae_naive": float("nan"),
                        "mae_recent_median": float("nan"),
                        "mae_model": float("nan"),
                        "mape_naive": float("nan"),
                        "mape_recent_median": float("nan"),
                        "mape_model": float("nan"),
                        "coverage_recent_pct": float("nan"),
                        "coverage_model_pct": float("nan"),
                        "model_beats_naive": False,
                    }
                )
                continue
            y = np.array([r["actual"] for r in sub])
            n = np.array([r["naive"] for r in sub])
            ra = np.array([r["recent_avg"] for r in sub])
            m = np.array([r["model_pred"] for r in sub])
            cr = [r["cover_recent"] for r in sub]
            cm = [r["cover_model"] for r in sub]
            row = _metrics_from_arrays(y, n, ra, m, cr, cm)
            row["commodity"] = commodity
            row["city"] = city
            row["skipped_thin"] = False
            per_city.append(row)

    obs_model = float(np.mean([r["cover_model"] for r in all_rows])) if all_rows else float("nan")
    obs_recent = float(np.mean([r["cover_recent"] for r in all_rows])) if all_rows else float("nan")
    calibration = [
        {
            "band": "model_q10_q90",
            "nominal_pct": NOMINAL_COVERAGE * 100,
            "observed_pct": obs_model * 100 if all_rows else float("nan"),
        },
        {
            "band": "recent_median_band",
            "nominal_pct": NOMINAL_COVERAGE * 100,
            "observed_pct": obs_recent * 100 if all_rows else float("nan"),
        },
    ]

    top_misses = sorted(all_rows, key=lambda r: r["err_model"], reverse=True)[:10]

    return {
        "label": "MEASURED",
        "fold_days": FOLD_DAYS,
        "max_folds": MAX_FOLDS,
        "folds_used": len(folds),
        "fold_windows": [
            {"start": a.isoformat(), "end": b.isoformat()} for a, b in folds
        ],
        "fold_summaries": fold_summaries,
        "n_test_total": len(all_rows),
        "per_commodity": per_commodity,
        "per_commodity_city": per_city,
        "calibration": calibration,
        "top_misses": top_misses,
        "prediction_rows": all_rows,
    }


def evaluate_commodity(work: pd.DataFrame, commodity: str, as_of: date) -> dict[str, Any]:
    """Legacy single holdout (HOLDOUT_DAYS) — kept for backward compatibility."""
    table, feature_cols = _build_training_table(work, commodity)
    skipped = 0
    empty_metrics = {
        "mae_naive": float("nan"),
        "mae_recent_median": float("nan"),
        "mae_model": float("nan"),
        "mape_naive": float("nan"),
        "mape_recent_median": float("nan"),
        "mape_model": float("nan"),
        "coverage_recent_pct": float("nan"),
        "coverage_model_pct": float("nan"),
        "model_beats_naive": False,
    }
    if table.empty:
        return {
            "commodity": commodity,
            "n_test": 0,
            "n_train": 0,
            "skipped_little_data": 0,
            "total_rows": 0,
            "note": "no training pairs",
            **empty_metrics,
        }

    holdout_start = as_of - timedelta(days=HOLDOUT_DAYS)
    train = table[table["target_date"] < holdout_start]
    test = table[
        (table["target_date"] >= holdout_start) & (table["target_date"] <= as_of)
    ]

    keep_idx = []
    for idx, r in test.iterrows():
        city = str(r["city"])
        if _thin_pair(work, commodity, city, _as_date_safe(r["date"])):
            skipped += 1
            continue
        keep_idx.append(idx)
    test = test.loc[keep_idx] if keep_idx else test.iloc[0:0]

    if test.empty or len(train) < 10:
        return {
            "commodity": commodity,
            "n_test": 0,
            "skipped_little_data": int(skipped),
            "n_train": int(len(train)),
            "total_rows": int(len(table)),
            "note": "too little data for holdout eval",
            **empty_metrics,
        }

    recs, _ = _predict_on_test_rows(work, commodity, train, test, feature_cols)
    if not recs:
        return {
            "commodity": commodity,
            "n_test": 0,
            "skipped_little_data": int(skipped),
            "n_train": int(len(train)),
            "total_rows": int(len(table)),
            "note": "too little data for holdout eval",
            **empty_metrics,
        }

    y = np.array([r["actual"] for r in recs])
    n = np.array([r["naive"] for r in recs])
    ra = np.array([r["recent_avg"] for r in recs])
    m = np.array([r["model_pred"] for r in recs])
    cr = [r["cover_recent"] for r in recs]
    cm = [r["cover_model"] for r in recs]
    met = _metrics_from_arrays(y, n, ra, m, cr, cm)
    row = {
        "commodity": commodity,
        "n_train": int(len(train)),
        "skipped_little_data": int(skipped),
        "total_rows": int(len(table)),
        "min_model_rows": MIN_MODEL_ROWS,
        **met,
    }
    return row


def _write_figures(backtest: dict[str, Any]) -> list[str]:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    rows = backtest.get("prediction_rows") or []
    if not rows or not _HAS_MPL or plt is None:
        return written

    # Demo pair: most test points
    from collections import Counter

    pair_counts = Counter((r["commodity"], r["city"]) for r in rows)
    (demo_com, demo_city), _ = pair_counts.most_common(1)[0]
    demo = sorted(
        [r for r in rows if r["commodity"] == demo_com and r["city"] == demo_city],
        key=lambda r: r["target_date"],
    )
    if demo:
        xs = range(len(demo))
        actual = [r["actual"] for r in demo]
        model = [r["model_pred"] for r in demo]
        naive = [r["naive"] for r in demo]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(xs, actual, "k-o", label="actual next FQP")
        ax.plot(xs, model, "b--s", label="ML median")
        ax.plot(xs, naive, "g:^", label="naive last")
        ax.set_title(
            f"MEASURED one-step forecast — {demo_com} / {demo_city}"
        )
        ax.set_xlabel("test step (chronological)")
        ax.set_ylabel("Rs/maund")
        ax.legend()
        fig.tight_layout()
        p1 = FIG_DIR / "forecast_vs_actual_demo.png"
        fig.savefig(p1, dpi=120)
        plt.close(fig)
        written.append(str(p1.relative_to(ROOT)))

    per_com = backtest.get("per_commodity") or []
    if per_com:
        labels = [r["commodity"] for r in per_com if r.get("n_test", 0) > 0]
        if labels:
            recent_cov = [
                r["coverage_recent_pct"]
                for r in per_com
                if r.get("n_test", 0) > 0
            ]
            model_cov = [
                r["coverage_model_pct"]
                for r in per_com
                if r.get("n_test", 0) > 0
            ]
            x = np.arange(len(labels))
            w = 0.35
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.bar(x - w / 2, recent_cov, w, label="recent_median band")
            ax.bar(x + w / 2, model_cov, w, label="model band")
            ax.axhline(NOMINAL_COVERAGE * 100, color="r", ls="--", label="nominal 80%")
            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=20, ha="right")
            ax.set_ylabel("coverage %")
            ax.set_title("MEASURED 80% band coverage by commodity")
            ax.legend()
            fig.tight_layout()
            p2 = FIG_DIR / "coverage_by_commodity.png"
            fig.savefig(p2, dpi=120)
            plt.close(fig)
            written.append(str(p2.relative_to(ROOT)))
    return written


def _df_to_md_table(df: pd.DataFrame) -> str:
    try:
        return df.to_markdown(index=False)
    except Exception:
        return df.to_string(index=False)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    clear_model_cache()
    raw = load_prices()
    if raw.empty:
        print("No AMIS data in data/amis_prices.csv")
        return 1
    as_of = max(pd.to_datetime(raw["date"]).dt.date)
    work = _prepare_frame(raw, as_of)
    commodities = sorted(work["commodity"].unique())

    backtest = rolling_backtest(work, as_of)
    legacy_rows = [evaluate_commodity(work, c, as_of) for c in commodities]
    legacy_table = pd.DataFrame(legacy_rows)

    bt_com = pd.DataFrame(backtest["per_commodity"])
    print("\n=== Rolling-origin backtest (MEASURED, Rs/maund, one-step-ahead) ===")
    show_cols = [
        "commodity",
        "n_test",
        "mae_naive",
        "mae_recent_median",
        "mae_model",
        "mape_naive",
        "mape_recent_median",
        "mape_model",
        "coverage_recent_pct",
        "coverage_model_pct",
        "model_beats_naive",
    ]
    if not bt_com.empty:
        cols = [c for c in show_cols if c in bt_com.columns]
        print(bt_com[cols].to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    print("\nWhere model does NOT beat naive (rolling, per commodity):")
    any_fail = False
    for _, r in bt_com.iterrows():
        if r.get("n_test", 0) == 0:
            print(f"  {r.get('commodity')}: skipped (thin / no test rows)")
            any_fail = True
            continue
        if not r.get("model_beats_naive", False):
            print(
                f"  {r['commodity']}: MAE model={r.get('mae_model'):.2f} "
                f">= naive={r.get('mae_naive'):.2f}"
            )
            any_fail = True
    if not any_fail and not bt_com.empty:
        print("  (none — model beat naive on every commodity with tests)")

    figures = _write_figures(backtest)

    report = {
        "label": "MEASURED",
        "as_of": as_of.isoformat(),
        "holdout_days": HOLDOUT_DAYS,
        "min_history_days": MIN_HISTORY_DAYS,
        "min_model_rows": MIN_MODEL_ROWS,
        "rolling_backtest": backtest,
        "legacy_single_holdout": {
            "commodities": legacy_rows,
        },
        "figures": figures,
    }

    out_dir = ROOT / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )

    md: list[str] = [
        f"# Price band metrics (MEASURED, as_of={as_of.isoformat()})",
        "",
        f"Rolling-origin: up to {MAX_FOLDS}×{FOLD_DAYS}-day test folds; "
        "train strictly before each fold; one-step-ahead FQP (Rs/maund).",
        "",
        "## Per commodity (rolling aggregate)",
        "",
        _df_to_md_table(bt_com[show_cols] if not bt_com.empty else bt_com),
        "",
        "## Per commodity × city (rolling)",
        "",
    ]
    bt_city = pd.DataFrame(backtest["per_commodity_city"])
    city_cols = ["commodity", "city"] + [c for c in show_cols if c != "commodity"]
    md.append(
        _df_to_md_table(bt_city[city_cols] if not bt_city.empty else bt_city)
    )
    md.append("")
    md.append("## Calibration (nominal vs observed 80% band coverage)")
    md.append("")
    md.append(_df_to_md_table(pd.DataFrame(backtest["calibration"])))
    md.append("")
    md.append("## Largest model errors (top 10)")
    md.append("")
    if backtest["top_misses"]:
        miss_df = pd.DataFrame(backtest["top_misses"])[
            [
                "commodity",
                "city",
                "target_date",
                "actual",
                "model_pred",
                "err_model",
            ]
        ]
        md.append(_df_to_md_table(miss_df))
    else:
        md.append("_No test rows._")
    md.append("")
    md.append("## Model vs naive (rolling, per commodity)")
    for _, r in bt_com.iterrows():
        com = r.get("commodity")
        if r.get("n_test", 0) == 0:
            md.append(f"- **{com}**: skipped (thin / no test rows)")
        elif r.get("model_beats_naive"):
            md.append(f"- **{com}**: model beats naive")
        else:
            md.append(f"- **{com}**: model does NOT beat naive")
    md.append("")
    md.append("## Legacy single holdout (backward compatible)")
    md.append("")
    leg_cols = [c for c in show_cols + ["skipped_little_data"] if c in legacy_table.columns]
    md.append(_df_to_md_table(legacy_table[leg_cols]))
    if figures:
        md.append("")
        md.append("## Figures")
        for f in figures:
            md.append(f"- `{f}`")
    (out_dir / "metrics.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\nWrote reports/metrics.json, reports/metrics.md, figures={figures}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
