"""Cross-market spread upper bounds from same-day AMIS FQP (ESTIMATE)."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import COMMISSION_PCT, TARGET_CITIES, TRANSPORT_RS_PER_MAUND_KM  # noqa: E402
from data.store import load_prices  # noqa: E402
from geo import distance_km  # noqa: E402

OUT = ROOT / "reports" / "spread.md"
MIN_MARKETS = 3


def main() -> int:
    df = load_prices()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Cross-market spread\n\n"
        "**ESTIMATE, upper bound. Wholesale prices, assumed costs, "
        "not realised farmer income.**\n\n"
        f"Formulas reuse `analysis/routing.py` helpers: "
        f"`net_j = FQP_j×(1-{COMMISSION_PCT:.0%}) − distance_km×"
        f"{TRANSPORT_RS_PER_MAUND_KM}`; "
        f"`net_gain = max_j(net_j) − origin_FQP`. "
        f"`is_suspect` rows ignored. Need ≥{MIN_MARKETS} markets/day.\n\n"
    )
    if df is None or df.empty:
        OUT.write_text(header + "No price data.\n", encoding="utf-8")
        print("No data")
        return 1

    work = df.copy()
    work["date"] = pd.to_datetime(work["date"]).dt.date
    if "is_suspect" in work.columns:
        work = work[work["is_suspect"] == False]  # noqa: E712
    work = work.dropna(subset=["fqp_rs_maund"])
    work = work[work["fqp_rs_maund"] > 0]
    work = work[work["city"].isin(TARGET_CITIES.keys())]

    origin_days: list[dict] = []
    for commodity in sorted(work["commodity"].unique()):
        sub = work[work["commodity"] == commodity]
        for d, day in sub.groupby("date"):
            prices = {
                str(r["city"]): float(r["fqp_rs_maund"])
                for _, r in day.iterrows()
            }
            if len(prices) < MIN_MARKETS:
                continue
            for origin, o_fqp in prices.items():
                best_other = max(v for c, v in prices.items() if c != origin)
                gross_gap_pct = (best_other - o_fqp) / o_fqp * 100.0
                nets = []
                for dest, d_fqp in prices.items():
                    if dest == origin:
                        continue
                    try:
                        dist = distance_km(origin, dest)
                    except KeyError:
                        continue
                    net_j = d_fqp * (1.0 - COMMISSION_PCT) - dist * TRANSPORT_RS_PER_MAUND_KM
                    nets.append(net_j)
                if not nets:
                    continue
                net_gain = max(nets) - o_fqp
                origin_days.append(
                    {
                        "commodity": commodity,
                        "date": d,
                        "origin": origin,
                        "gross_gap_pct": gross_gap_pct,
                        "net_gain_rs_maund": net_gain,
                    }
                )

    lines = [header, f"Generated: {datetime.now().isoformat(timespec='seconds')}\n"]
    if not origin_days:
        lines.append(f"No dates with ≥{MIN_MARKETS} reporting markets.\n")
        OUT.write_text("\n".join(lines), encoding="utf-8")
        print("No spread pairs")
        return 0

    tab = pd.DataFrame(origin_days)
    lines.append(f"Total origin-days: **{len(tab)}**\n")
    lines.append("## Per commodity (ESTIMATE)\n")
    lines.append(
        "| Commodity | n origin-days | median gross gap % | "
        "share net gain > 0 | median net gain among >0 (Rs/maund) |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for commodity in sorted(tab["commodity"].unique()):
        c = tab[tab["commodity"] == commodity]
        pos = c[c["net_gain_rs_maund"] > 0]
        share = float(len(pos) / len(c) * 100) if len(c) else 0.0
        med_pos = float(pos["net_gain_rs_maund"].median()) if len(pos) else float("nan")
        lines.append(
            f"| {commodity} | {len(c)} | {c['gross_gap_pct'].median():.2f} | "
            f"{share:.1f}% | {med_pos:.1f} |"
        )

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} ({len(tab)} origin-days)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
