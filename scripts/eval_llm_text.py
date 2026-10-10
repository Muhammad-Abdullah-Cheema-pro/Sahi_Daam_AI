"""Evaluate typed-text parsing: live Gemini vs offline fallback."""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from llm_client import LLMError, extract_from_text, resolve_api_key  # noqa: E402
from voice_parser import build_outcome, rule_based_extract  # noqa: E402

OUT = ROOT / "reports" / "llm_text_metrics.md"
CASES = ROOT / "tests" / "voice_cases.csv"


def _field_ok(req, row: dict, field: str) -> bool:
    if req is None:
        return False
    if field == "crop":
        return req.crop == row["expected_crop"]
    if field == "district":
        return req.district == row["expected_district"]
    if field == "quantity_maunds":
        return abs(req.quantity_maunds - float(row["expected_quantity_maunds"])) < 1e-6
    if field == "quote":
        exp = row["expected_quote_per_maund"].strip()
        if exp == "":
            return req.quoted_price_per_maund is None
        if req.quoted_price_per_maund is None:
            return False
        return abs(req.quoted_price_per_maund - float(exp)) < 1e-6
    return False


def _full_row(req, row: dict) -> bool:
    return all(_field_ok(req, row, f) for f in ("crop", "district", "quantity_maunds", "quote"))


def _eval_rows(rows: list[dict], *, live: bool, sleep_s: float) -> dict:
    fields = ["crop", "district", "quantity_maunds", "quote"]
    stats = {f: {"ok": 0, "n": 0} for f in fields}
    full_ok = 0
    errors: list[str] = []
    for row in rows:
        text = row["spoken_text"]
        req = None
        if live:
            try:
                ext = extract_from_text(text)
                out = build_outcome(ext)
                req = out.request if out.status == "ok" else None
            except LLMError as exc:
                errors.append(f"id={row['id']}: {exc.cause}")
            if sleep_s > 0:
                time.sleep(sleep_s)
        else:
            ext = rule_based_extract(text)
            out = build_outcome(ext)
            req = out.request if out.status == "ok" else None

        for f in fields:
            stats[f]["n"] += 1
            if _field_ok(req, row, f):
                stats[f]["ok"] += 1
        if _full_row(req, row):
            full_ok += 1

    return {
        "n": len(rows),
        "field_stats": stats,
        "full_row_ok": full_ok,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sleep", type=float, default=1.0, help="Seconds between live API calls")
    args = parser.parse_args()

    rows = list(csv.DictReader(CASES.open(encoding="utf-8")))
    OUT.parent.mkdir(parents=True, exist_ok=True)

    offline = _eval_rows(rows, live=False, sleep_s=0.0)
    key = resolve_api_key()
    live_stats = None
    live_note = "SKIPPED (no GEMINI_API_KEY)"
    if key:
        live_stats = _eval_rows(rows, live=True, sleep_s=args.sleep)
        live_note = f"LIVE Gemini ({len(rows)} rows, sleep={args.sleep}s)"
    else:
        print("SKIP live LLM — no API key")

    lines = [
        "# LLM typed-text metrics",
        "",
        "**Label: typed text, NOT speech accuracy.**",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Cases: `tests/voice_cases.csv` (n={len(rows)})",
        "",
        "## Offline fallback (rule_based_extract)",
        "",
        f"- Full-row accuracy: **{offline['full_row_ok']}/{offline['n']}**",
    ]
    for f, st in offline["field_stats"].items():
        lines.append(f"- `{f}`: **{st['ok']}/{st['n']}**")
    lines.append("")
    lines.append(f"## Live Gemini text path ({live_note})")
    lines.append("")
    if live_stats is None:
        lines.append("_Skipped — set GEMINI_API_KEY to measure live path._")
    else:
        lines.append(
            f"- Full-row accuracy: **{live_stats['full_row_ok']}/{live_stats['n']}**"
        )
        for f, st in live_stats["field_stats"].items():
            lines.append(f"- `{f}`: **{st['ok']}/{st['n']}**")
        if live_stats["errors"]:
            lines.append("- Errors:")
            for e in live_stats["errors"][:10]:
                lines.append(f"  - {e}")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
