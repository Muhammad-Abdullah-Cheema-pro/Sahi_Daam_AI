"""Rebuild data/amis_prices.csv from cached HTML under data/raw/ (no network)."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import TARGET_CITIES, TARGET_COMMODITIES  # noqa: E402
from data.amis_scraper import parse_city_day, table_has_any_numeric_price  # noqa: E402
from data.cleaning import clean  # noqa: E402
from data.store import coverage_report, save_prices  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("rebuild_from_cache")


def main() -> int:
    raw = ROOT / "data" / "raw"
    commodities = set(TARGET_COMMODITIES.values())
    rows: list[dict] = []
    for city_dir in sorted(raw.iterdir()) if raw.is_dir() else []:
        if not city_dir.is_dir():
            continue
        city = city_dir.name
        if city not in TARGET_CITIES:
            continue
        for html_path in sorted(city_dir.glob("*.html")):
            try:
                day = datetime.strptime(html_path.stem, "%Y-%m-%d").date()
            except ValueError:
                continue
            html = html_path.read_text(encoding="utf-8", errors="replace")
            if not table_has_any_numeric_price(html):
                continue
            parsed = parse_city_day(html, city=city, day=day, commodities=commodities)
            kept = [
                r
                for r in parsed
                if r["min_rs_100kg"] is not None
                or r["max_rs_100kg"] is not None
                or r["fqp_rs_100kg"] is not None
            ]
            rows.extend(kept)
    if not rows:
        logger.error("No rows from cache")
        return 1
    df = clean(pd.DataFrame(rows))
    out = save_prices(df, ROOT / "data" / "amis_prices.csv")
    logger.info("Wrote %s rows to %s", len(df), out)
    print(coverage_report(df).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
