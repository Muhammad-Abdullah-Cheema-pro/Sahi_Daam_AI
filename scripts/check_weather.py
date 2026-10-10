"""LIVE weather health check for 3 districts (not run in CI)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from advisory_engine import fetch_district_weather  # noqa: E402
from config import WEATHER_TIMEOUT_S  # noqa: E402

DISTRICTS = ("Lahore", "Multan", "Okara")
REQUIRED = (
    "forecast_date",
    "precip_mm_48h",
    "max_precip_prob",
    "temp_min_c",
    "temp_max_c",
)


def main() -> int:
    ok = True
    for d in DISTRICTS:
        t0 = time.perf_counter()
        try:
            w = fetch_district_weather(d)
            elapsed = time.perf_counter() - t0
            fields_ok = all(hasattr(w, f) for f in REQUIRED)
            print(
                f"{d}: date={w.forecast_date} precip={w.precip_mm_48h:.1f} "
                f"prob={w.max_precip_prob:.0f} temp={w.temp_min_c:.0f}-{w.temp_max_c:.0f} "
                f"cache={w.from_cache} latency={elapsed:.2f}s fields={'OK' if fields_ok else 'FAIL'}"
            )
            if elapsed > WEATHER_TIMEOUT_S:
                print(f"FAIL: {d} exceeded {WEATHER_TIMEOUT_S}s")
                ok = False
            if not fields_ok:
                ok = False
        except Exception as exc:
            print(f"FAIL: {d}: {exc}")
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
