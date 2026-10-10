"""Write reports/data_quality.md from data/amis_prices.csv (MEASURED)."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import RS_100KG_TO_MAUND, TARGET_CITIES, TARGET_COMMODITIES  # noqa: E402
from data.store import load_prices  # noqa: E402

OUT = ROOT / "reports" / "data_quality.md"
THIN_DAYS = 90


def _longest_gap(dates: list) -> int:
    if len(dates) < 2:
        return 0
    ds = sorted(dates)
    return max((ds[i + 1] - ds[i]).days for i in range(len(ds) - 1))


def main() -> int:
    df = load_prices()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if df is None or df.empty:
        OUT.write_text("# Data quality\n\nNo data.\n", encoding="utf-8")
        print("No data")
        return 1

    work = df.copy()
    work["date"] = pd.to_datetime(work["date"]).dt.date
    dmin, dmax = work["date"].min(), work["date"].max()
    n = len(work)
    dup = int(work.duplicated(subset=["date", "city", "commodity"]).sum())
    # unit sanity: per-maund ≈ FQP_100kg * 0.4
    unit_bad = 0
    if "fqp_rs_100kg" in work.columns and "fqp_rs_maund" in work.columns:
        expected = work["fqp_rs_100kg"].astype(float) * RS_100KG_TO_MAUND
        unit_bad = int(
            ((work["fqp_rs_maund"].astype(float) - expected).abs() > 0.05).sum()
        )
    suspect = int(work["is_suspect"].sum()) if "is_suspect" in work.columns else 0

    lines = [
        "# AMIS data quality (MEASURED)",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Source file: `data/amis_prices.csv`",
        f"Date range: **{dmin}** … **{dmax}**",
        f"Total rows: **{n}**",
        f"Duplicate (date,city,commodity) rows: **{dup}**",
        f"Suspect rows (`is_suspect`): **{suspect}**",
        f"Unit sanity failures (|maund − 100kg×{RS_100KG_TO_MAUND}| > 0.05): **{unit_bad}**",
        "",
        f"Thin-pair threshold for demo/model: **<{THIN_DAYS} days present**.",
        "",
        "| Commodity | City | Days present | Longest gap (days) | Suspect | Thin? |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    thin_pairs: list[str] = []
    for commodity in TARGET_COMMODITIES.values():
        for city in TARGET_CITIES:
            sub = work[(work["city"] == city) & (work["commodity"] == commodity)]
            days = int(sub["date"].nunique())
            gap = _longest_gap(list(sub["date"].unique()))
            sus = int(sub["is_suspect"].sum()) if "is_suspect" in sub.columns else 0
            thin = days < THIN_DAYS
            if thin:
                thin_pairs.append(f"{commodity}/{city} ({days}d)")
            lines.append(
                f"| {commodity} | {city} | {days} | {gap} | {sus} | "
                f"{'YES' if thin else 'no'} |"
            )

    lines += [
        "",
        f"## Thin pairs ({len(thin_pairs)})",
        "",
    ]
    if thin_pairs:
        for p in thin_pairs:
            lines.append(f"- {p}")
        lines.append("")
        lines.append(
            "Action: run `python -m scripts.collect_amis` for missing ranges "
            "in resumable ~60-day chunks. Never fabricate or interpolate rows."
        )
    else:
        lines.append("None — all target pairs have ≥ 90 days present.")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
