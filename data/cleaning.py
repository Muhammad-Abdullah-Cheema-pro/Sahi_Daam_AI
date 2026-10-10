"""Unit conversion and cleaning for AMIS wholesale price frames."""

from __future__ import annotations

from typing import Optional, Union

import pandas as pd

from config import RS_100KG_TO_MAUND

Number = Union[int, float]


def to_per_maund(rs_per_100kg: Optional[Number]) -> Optional[float]:
    """Convert AMIS Rs/100 kg to Rs/maund (maund = 40 kg → × 0.4).

    ``None`` stays ``None``. ``0`` stays ``0.0``.
    """
    if rs_per_100kg is None:
        return None
    return float(rs_per_100kg) * RS_100KG_TO_MAUND


def rs_maund_to_100kg(rs_per_maund: Optional[Number]) -> Optional[float]:
    """Inverse of :func:`to_per_maund` (÷ 0.4)."""
    if rs_per_maund is None:
        return None
    return float(rs_per_maund) / RS_100KG_TO_MAUND


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Clean a long-format AMIS price frame.

    - Drop exact duplicate rows
    - Add per-maund columns from Rs/100 kg
    - Flag (do not delete) rows where min <= fqp <= max is violated, or where
      fqp is outside 0.3×–3× the rolling 14-day median for that city+commodity
      (``is_suspect``)
    - Missing calendar days stay missing (no forward-fill)
    """
    if df.empty:
        out = df.copy()
        for col in (
            "min_rs_maund",
            "max_rs_maund",
            "fqp_rs_maund",
            "is_suspect",
        ):
            if col not in out.columns:
                out[col] = pd.Series(dtype="float64" if col != "is_suspect" else "bool")
        return out

    out = df.copy()
    out = out.drop_duplicates()

    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"]).dt.date

    out["min_rs_maund"] = out["min_rs_100kg"].map(to_per_maund)
    out["max_rs_maund"] = out["max_rs_100kg"].map(to_per_maund)
    out["fqp_rs_maund"] = out["fqp_rs_100kg"].map(to_per_maund)

    work = out.sort_values(["city", "commodity", "date"]).copy()
    band_ok = (
        work["min_rs_100kg"].isna()
        | work["fqp_rs_100kg"].isna()
        | work["max_rs_100kg"].isna()
        | (
            (work["min_rs_100kg"] <= work["fqp_rs_100kg"])
            & (work["fqp_rs_100kg"] <= work["max_rs_100kg"])
        )
    )
    work["_median14"] = work.groupby(["city", "commodity"], group_keys=False)[
        "fqp_rs_100kg"
    ].transform(lambda s: s.rolling(window=14, min_periods=1).median())
    median = work["_median14"]
    fqp = work["fqp_rs_100kg"]
    median_ok = (
        fqp.isna()
        | median.isna()
        | ((fqp >= 0.3 * median) & (fqp <= 3.0 * median))
    )
    work["is_suspect"] = ~(band_ok & median_ok)
    work = work.drop(columns=["_median14"])
    return work.reset_index(drop=True)
