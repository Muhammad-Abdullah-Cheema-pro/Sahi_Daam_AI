"""Persist and summarise long-format AMIS price CSVs."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "data" / "amis_prices.csv"

PRICE_COLUMNS = [
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


def save_prices(df: pd.DataFrame, path: Path = DEFAULT_CSV) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    cols = [c for c in PRICE_COLUMNS if c in out.columns]
    extra = [c for c in out.columns if c not in cols]
    out = out[cols + extra]
    out.to_csv(path, index=False)
    return path


def load_prices(path: Path = DEFAULT_CSV) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame(columns=PRICE_COLUMNS)
    df = pd.read_csv(path)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def coverage_report(
    df: Optional[pd.DataFrame] = None,
    path: Path = DEFAULT_CSV,
) -> pd.DataFrame:
    """Per city+commodity: first date, last date, days present, longest gap."""
    if df is None:
        df = load_prices(path)
    if df.empty:
        return pd.DataFrame(
            columns=[
                "city",
                "commodity",
                "first_date",
                "last_date",
                "days_present",
                "longest_gap_days",
            ]
        )

    work = df.copy()
    work["date"] = pd.to_datetime(work["date"])
    rows = []
    for (city, commodity), g in work.groupby(["city", "commodity"]):
        days = sorted(g["date"].drop_duplicates())
        gaps = [0]
        for a, b in zip(days, days[1:]):
            gaps.append(int((b - a).days) - 1)
        rows.append(
            {
                "city": city,
                "commodity": commodity,
                "first_date": days[0].date().isoformat(),
                "last_date": days[-1].date().isoformat(),
                "days_present": len(days),
                "longest_gap_days": max(gaps),
            }
        )
    return pd.DataFrame(rows).sort_values(["city", "commodity"]).reset_index(drop=True)
