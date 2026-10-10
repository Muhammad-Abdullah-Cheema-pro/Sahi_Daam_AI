"""CLI: collect real AMIS wholesale prices into data/amis_prices.csv."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import TARGET_CITIES, TARGET_COMMODITIES  # noqa: E402
from data.amis_scraper import (  # noqa: E402
    AmisScraperError,
    cache_path,
    fetch_city_day,
    make_session,
    parse_city_day,
    table_has_any_numeric_price,
)
from data.cleaning import clean  # noqa: E402
from data.store import coverage_report, save_prices  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("collect_amis")


def _parse_day(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _daterange(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Collect Punjab AMIS wholesale prices.")
    p.add_argument("--start", required=True, type=_parse_day, help="YYYY-MM-DD inclusive")
    p.add_argument("--end", required=True, type=_parse_day, help="YYYY-MM-DD inclusive")
    p.add_argument(
        "--cities",
        nargs="*",
        default=list(TARGET_CITIES.keys()),
        help="City names (default: all TARGET_CITIES)",
    )
    p.add_argument(
        "--commodities",
        nargs="*",
        default=list(TARGET_COMMODITIES.values()),
        help="Exact AMIS commodity row names",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data" / "amis_prices.csv",
        help="Output CSV path",
    )
    p.add_argument(
        "--raw-dir",
        type=Path,
        default=ROOT / "data" / "raw",
        help="HTML cache directory",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.end < args.start:
        logger.error("--end must be >= --start")
        return 2

    for city in args.cities:
        if city not in TARGET_CITIES:
            logger.error("Unknown city %r. Known: %s", city, sorted(TARGET_CITIES))
            return 2

    commodities = set(args.commodities)
    days = list(_daterange(args.start, args.end))
    total = len(args.cities) * len(days)
    logger.info(
        "Collecting %s city-days (%s cities × %s days), commodities=%s",
        total,
        len(args.cities),
        len(days),
        sorted(commodities),
    )

    session = make_session()
    all_rows: list[dict] = []
    done = 0
    errors = 0

    try:
        for city in args.cities:
            for day in days:
                done += 1
                cached = cache_path(city, day, args.raw_dir).is_file()
                label = "cache" if cached else "fetch"
                logger.info("[%s/%s] %s %s (%s)", done, total, city, day.isoformat(), label)
                try:
                    html = fetch_city_day(
                        city,
                        day,
                        session=session,
                        raw_dir=args.raw_dir,
                    )
                    if not table_has_any_numeric_price(html):
                        logger.info(
                            "  empty table → missing day for %s %s", city, day.isoformat()
                        )
                        continue
                    rows = parse_city_day(
                        html,
                        city=city,
                        day=day,
                        commodities=commodities,
                    )
                    # Keep rows even if target commodities are all blank that day
                    # (still records the day only when some numeric prices existed
                    # page-wide). Filter to rows with any price among targets.
                    kept = [
                        r
                        for r in rows
                        if r["min_rs_100kg"] is not None
                        or r["max_rs_100kg"] is not None
                        or r["fqp_rs_100kg"] is not None
                    ]
                    logger.info("  parsed %s target rows with prices", len(kept))
                    all_rows.extend(kept)
                except AmisScraperError as exc:
                    errors += 1
                    logger.error("  FAILED %s %s: %s", city, day.isoformat(), exc)
    finally:
        session.close()

    if not all_rows:
        logger.error("Zero rows collected; not writing CSV (errors=%s)", errors)
        return 1

    import pandas as pd

    df = clean(pd.DataFrame(all_rows))
    out_path = save_prices(df, args.out)
    logger.info("Wrote %s rows to %s", len(df), out_path)

    report = coverage_report(df)
    print("\n=== coverage_report ===")
    print(report.to_string(index=False))
    print("\n=== first 10 rows ===")
    print(df.head(10).to_string(index=False))

    thin = report[report["days_present"] < len(days)]
    if not thin.empty:
        print(
            f"\n=== city/commodity with fewer than {len(days)} of {len(days)} days ==="
        )
        print(thin.to_string(index=False))

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
