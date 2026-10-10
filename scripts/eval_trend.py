"""Evaluate observed price-trend labels vs next-window median change (MEASURED)."""

from __future__ import annotations

import random
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.trend import get_price_trend  # noqa: E402
from config import (  # noqa: E402
    TARGET_CITIES,
    TARGET_COMMODITIES,
    TREND_THRESHOLD_PCT,
    TREND_WINDOW,
)
from data.store import load_prices  # noqa: E402

OUT = ROOT / "reports" / "trend_metrics.md"


def _next_window_sign(values: list[float]) -> str:
    """Sign of median(next TREND_WINDOW) vs median(last TREND_WINDOW) of past."""
    if len(values) < 2 * TREND_WINDOW:
        return "Flat"
    # values already include history up through as_of; next window is AFTER as_of
    return "n/a"


def main() -> int:
    df = load_prices()
    if df is None or df.empty:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text("# Trend metrics\n\nNo price data.\n", encoding="utf-8")
        print("No data")
        return 1

    work = df.copy()
    work["date"] = pd.to_datetime(work["date"]).dt.date
    if "is_suspect" in work.columns:
        work = work[work["is_suspect"] == False]  # noqa: E712

    lines = [
        "# Price trend evaluation (MEASURED)",
        "",
        "Method: at each eligible as_of, compare `get_price_trend` label with the sign of",
        f"the NEXT-{TREND_WINDOW}-observation median change (held-out). Threshold ±{TREND_THRESHOLD_PCT}%.",
        "Baselines: always-Flat; shuffled labels (same marginal distribution).",
        "",
    ]

    overall = {"agree": 0, "n": 0, "flat_agree": 0, "shuf_agree": 0}
    per_comm: dict[str, dict[str, int]] = {}

    rng = random.Random(0)

    for commodity in TARGET_COMMODITIES.values():
        cstats = {"agree": 0, "n": 0, "flat_agree": 0, "shuf_agree": 0}
        for city in TARGET_CITIES:
            sub = work[(work["city"] == city) & (work["commodity"] == commodity)]
            sub = sub.dropna(subset=["fqp_rs_maund"])
            sub = sub[sub["fqp_rs_maund"] > 0].sort_values("date")
            if len(sub) < 2 * TREND_WINDOW + TREND_WINDOW:
                continue
            fqp = sub["fqp_rs_maund"].astype(float).tolist()
            dates = sub["date"].tolist()
            # Slide: need 14 past + 7 future
            for i in range(2 * TREND_WINDOW - 1, len(fqp) - TREND_WINDOW):
                as_of = dates[i]
                hist = sub[sub["date"] <= as_of]
                tr = get_price_trend(city, commodity, as_of=as_of, df=hist)
                if tr.label is None:
                    continue
                next_med = float(pd.Series(fqp[i + 1 : i + 1 + TREND_WINDOW]).median())
                cur_med = float(pd.Series(fqp[i + 1 - TREND_WINDOW : i + 1]).median())
                if cur_med <= 0:
                    continue
                pct = (next_med - cur_med) / cur_med * 100.0
                if pct > TREND_THRESHOLD_PCT:
                    truth = "Rising"
                elif pct < -TREND_THRESHOLD_PCT:
                    truth = "Falling"
                else:
                    truth = "Flat"
                agree = int(tr.label == truth)
                flat_agree = int("Flat" == truth)
                # shuffled baseline uses random label from {Rising,Flat,Falling}
                shuf = rng.choice(["Rising", "Flat", "Falling"])
                shuf_agree = int(shuf == truth)
                for bucket in (overall, cstats):
                    bucket["agree"] += agree
                    bucket["n"] += 1
                    bucket["flat_agree"] += flat_agree
                    bucket["shuf_agree"] += shuf_agree
        per_comm[commodity] = cstats

    def _row(name: str, s: dict[str, int]) -> str:
        n = s["n"]
        if n == 0:
            return f"| {name} | 0 | n/a | n/a | n/a |"
        return (
            f"| {name} | {n} | {s['agree']/n:.1%} | "
            f"{s['flat_agree']/n:.1%} | {s['shuf_agree']/n:.1%} |"
        )

    lines += [
        "| Commodity | n | Trend agree | Always-Flat | Shuffled |",
        "| --- | ---: | ---: | ---: | ---: |",
        _row("ALL", overall),
    ]
    for com, s in per_comm.items():
        lines.append(_row(com, s))

    lines.append("")
    if overall["n"] == 0:
        lines.append(
            "**Insufficient history** for held-out next-window evaluation "
            f"(need >= {3 * TREND_WINDOW} observations per pair). Descriptive only."
        )
    else:
        trend_acc = overall["agree"] / overall["n"]
        flat_acc = overall["flat_agree"] / overall["n"]
        shuf_acc = overall["shuf_agree"] / overall["n"]
        if trend_acc <= flat_acc and trend_acc <= max(shuf_acc, flat_acc):
            lines.append(
                f"**Verdict (MEASURED, n={overall['n']})**: trend labels are **no better** "
                f"than baselines (trend={trend_acc:.1%}, always-Flat={flat_acc:.1%}, "
                f"shuffled={shuf_acc:.1%}). Treat as **descriptive only**, not a forecast."
            )
        else:
            lines.append(
                f"**Verdict (MEASURED, n={overall['n']})**: trend agree={trend_acc:.1%} "
                f"vs always-Flat={flat_acc:.1%} vs shuffled={shuf_acc:.1%}."
            )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
