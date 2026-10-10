"""Simulated broker quotes vs next-day FQP bands (SIMULATED)."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.verdict import assess_quote  # noqa: E402
from model.price_band import _build_training_table, _prepare_frame, get_band  # noqa: E402
from data.store import load_prices  # noqa: E402

OUT = ROOT / "reports" / "simulated_quotes.md"
OFFSETS = [-0.05, -0.10, -0.20, -0.30, 0.05]
FLAG_LABELS = {"Low", "Very low", "Unable to assess"}


def _as_date(d: Any) -> date:
    return pd.to_datetime(d).date()


def main() -> int:
    raw = load_prices()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Simulated quote verdict rates (SIMULATED)",
        "",
        "Quotes are offsets from **actual next FQP** on held-out one-step pairs; "
        "verdict via `assess_quote` + `get_band` at prediction date.",
        "",
    ]
    if raw.empty:
        lines.append("No AMIS data.")
        OUT.write_text("\n".join(lines), encoding="utf-8")
        return 1

    as_of = max(pd.to_datetime(raw["date"]).dt.date)
    work = _prepare_frame(raw, as_of)

    by_offset: dict[str, dict[str, Any]] = {}
    for off in OFFSETS:
        labels: list[str] = []
        for commodity in sorted(work["commodity"].unique()):
            table, _ = _build_training_table(work, commodity)
            if table.empty:
                continue
            for city, g in table.groupby("city"):
                r = g.sort_values("target_date").iloc[-1]
                actual_next = float(r["next_fqp"])
                quote = actual_next * (1.0 + off)
                pred_date = _as_date(r["date"])
                band = get_band(str(city), commodity, as_of=pred_date, df=work)
                v = assess_quote(quote, band, reference_market=str(city))
                labels.append(v.verdict_status)
        key = f"{int(off * 100):+d}%"
        if not labels:
            by_offset[key] = {"n": 0, "rates": {}, "flag_rate": float("nan")}
            continue
        counts: dict[str, int] = {}
        for lab in labels:
            counts[lab] = counts.get(lab, 0) + 1
        rates = {k: round(v / len(labels), 3) for k, v in sorted(counts.items())}
        flagged = sum(1 for lab in labels if lab in FLAG_LABELS)
        by_offset[key] = {
            "n": len(labels),
            "flag_rate": round(flagged / len(labels), 3),
            "rates": rates,
        }

    lines.append("## Flag rate by offset\n")
    lines.append("| offset | n | any-flag rate | verdict mix |")
    lines.append("| --- | ---: | ---: | --- |")
    for key in [f"{int(o * 100):+d}%" for o in OFFSETS]:
        row = by_offset.get(key, {})
        mix = ", ".join(f"{k}={v}" for k, v in (row.get("rates") or {}).items())
        lines.append(
            f"| {key} | {row.get('n', 0)} | {row.get('flag_rate', 'n/a')} | {mix or '—'} |"
        )

    pos = by_offset.get("+5%", {})
    fair_rate = float(pos.get("rates", {}).get("Fair", 0) or 0)
    lines.append("")
    lines.append("## False-flag on +5% (SIMULATED)")
    lines.append("")
    if pos.get("n", 0) == 0:
        lines.append("_No pairs evaluated._")
    else:
        not_fair = 1.0 - fair_rate
        lines.append(
            f"- At **+5%** of actual next FQP, non-Fair (false-flag) rate ≈ **{not_fair:.1%}** "
            f"(Fair rate={fair_rate:.1%}, n={pos.get('n')})."
        )
        lines.append(
            "- Expected: quotes above wholesale should usually be **Fair**; "
            "Low/Very low here count as false flags."
        )

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
