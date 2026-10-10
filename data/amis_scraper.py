"""Fetch and parse Punjab AMIS ViewPrices wholesale tables (real HTML only)."""

from __future__ import annotations

import logging
import re
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup, Tag

from config import (
    AMIS_MAX_RETRIES,
    AMIS_POLITE_DELAY_S,
    AMIS_REQUEST_TIMEOUT_S,
    AMIS_USER_AGENT,
    AMIS_VIEW_PRICES_URL,
    TARGET_CITIES,
)

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = ROOT / "data" / "raw"

_DATE_HEADER_RE = re.compile(r"Dated:\s*(\d{1,2})-(\d{1,2})-(\d{4})", re.I)
# AMIS cells look like "1&nbsp Wheat" (literal &nbsp, not always a real NBSP).
_COMMODITY_PREFIX_RE = re.compile(
    r"^\d+\s*(?:&nbsp;?|&nbsp|\xa0)?\s*",
    re.I,
)


class AmisScraperError(Exception):
    """Base error for AMIS scraping failures."""


class AmisFetchError(AmisScraperError):
    """Network or HTTP failure fetching an AMIS page."""


class AmisDateMismatchError(AmisScraperError):
    """Returned Dated: header does not match the requested calendar day."""


class AmisParseError(AmisScraperError):
    """HTML could not be parsed into price rows."""


def _city_id(city: str) -> int:
    if city not in TARGET_CITIES:
        raise AmisScraperError(f"Unknown city {city!r}; expected one of {sorted(TARGET_CITIES)}")
    return TARGET_CITIES[city]


def cache_path(city: str, day: date, raw_dir: Path = DEFAULT_RAW_DIR) -> Path:
    return raw_dir / city / f"{day.isoformat()}.html"


def _extract_hidden_fields(soup: BeautifulSoup) -> dict[str, str]:
    fields: dict[str, str] = {}
    for inp in soup.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        itype = (inp.get("type") or "").lower()
        if itype in {"hidden", "text"} or name.startswith("__"):
            fields[name] = inp.get("value") or ""
    return fields


def parse_dated_header(html: str) -> Optional[date]:
    """Return the Dated:DD-MM-YYYY value from a ViewPrices page, if present."""
    text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    m = _DATE_HEADER_RE.search(text)
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return date(y, mo, d)


def _assert_dated_matches(html: str, day: date) -> None:
    found = parse_dated_header(html)
    if found is None:
        raise AmisDateMismatchError(
            f"No Dated: header found; expected {day.isoformat()}"
        )
    if found != day:
        raise AmisDateMismatchError(
            f"Dated header {found.isoformat()} does not match requested {day.isoformat()}"
        )


def _parse_price_cell(raw: str) -> Optional[float]:
    text = (raw or "").strip().replace("\xa0", " ").replace(",", "")
    if not text or text == "-":
        return None
    try:
        return float(text)
    except ValueError as exc:
        raise AmisParseError(f"Unparseable price cell {raw!r}") from exc


def _normalize_commodity_name(raw: str) -> str:
    name = raw.replace("\xa0", " ").replace("&nbsp;", " ").replace("&nbsp", " ")
    name = re.sub(r"\s+", " ", name).strip()
    name = _COMMODITY_PREFIX_RE.sub("", name).strip()
    return name


def _find_price_table(soup: BeautifulSoup) -> Tag:
    """Locate the ViewPrices commodity table with Min/Max/FQP/Quantity headers.

    Prefers the table with the most well-formed 6-column commodity rows (the page
    embeds a duplicate wide nested table that is harder to walk).
    """
    candidates: list[tuple[int, Tag]] = []
    for table in soup.find_all("table"):
        header_hit = False
        good_rows = 0
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if not cells:
                continue
            joined = " ".join(cells)
            if "Min" in joined and "Max" in joined and "FQP" in joined:
                header_hit = True
            if len(cells) == 6 and cells[1] == "Graph":
                good_rows += 1
        if header_hit and good_rows > 0:
            candidates.append((good_rows, table))
    if not candidates:
        raise AmisParseError("Could not find ViewPrices Min/Max/FQP table")
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def table_has_any_numeric_price(html: str) -> bool:
    """True if at least one commodity row has a numeric Min, Max, or FQP."""
    try:
        rows = parse_city_day(
            html,
            city="__",
            day=date(2000, 1, 1),
            require_dated=False,
            commodities=None,  # all commodities
        )
    except AmisParseError:
        return False
    for row in rows:
        if (
            row.get("min_rs_100kg") is not None
            or row.get("max_rs_100kg") is not None
            or row.get("fqp_rs_100kg") is not None
        ):
            return True
    return False


def parse_city_day(
    html: str,
    city: str,
    day: date,
    *,
    require_dated: bool = True,
    commodities: Optional[set[str]] = None,
) -> list[dict[str, Any]]:
    """Parse ViewPrices HTML into long-format price row dicts.

    Columns: date, city, commodity, min_rs_100kg, max_rs_100kg, fqp_rs_100kg, quantity.

    If ``commodities`` is None, keep every commodity row; otherwise keep only names
    in that set (exact AMIS row names).
    """
    if require_dated:
        _assert_dated_matches(html, day)

    soup = BeautifulSoup(html, "lxml")
    try:
        table = _find_price_table(soup)
    except AmisParseError:
        # Empty / missing table → missing day (zero rows), not a hard parse failure
        # when the page rendered but has no price grid.
        if parse_dated_header(html) is not None:
            logger.warning("Dated header present but no price table for %s %s", city, day)
            return []
        raise

    wanted = commodities
    rows: list[dict[str, Any]] = []

    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        # Canonical ViewPrices row: name | Graph | Min | Max | FQP | Quantity
        if len(cells) != 6 or cells[1] != "Graph":
            continue
        name_raw, min_s, max_s, fqp_s, qty_s = (
            cells[0],
            cells[2],
            cells[3],
            cells[4],
            cells[5],
        )
        if name_raw.startswith("Dated:") or "Min" in cells:
            continue

        commodity = _normalize_commodity_name(name_raw)
        if not commodity or commodity in {
            "Grains",
            "Vegetables",
            "Fruits",
            "Others",
            "Other",
            "Pulses",
        }:
            continue
        if wanted is not None and commodity not in wanted:
            continue

        rows.append(
            {
                "date": day.isoformat(),
                "city": city,
                "commodity": commodity,
                "min_rs_100kg": _parse_price_cell(min_s),
                "max_rs_100kg": _parse_price_cell(max_s),
                "fqp_rs_100kg": _parse_price_cell(fqp_s),
                "quantity": _parse_price_cell(qty_s),
            }
        )

    return rows


def _should_cache_html(html: str, day: date, today: Optional[date] = None) -> bool:
    """Cache non-empty pages always; cache empties only if older than 2 days."""
    today = today or date.today()
    if table_has_any_numeric_price(html):
        return True
    return day < (today - timedelta(days=2))


def _post_for_day(
    session: requests.Session,
    city: str,
    day: date,
) -> str:
    city_id = _city_id(city)
    url = f"{AMIS_VIEW_PRICES_URL}?searchType=1&commodityId={city_id}"
    try:
        r0 = session.get(url, timeout=AMIS_REQUEST_TIMEOUT_S)
        r0.raise_for_status()
    except requests.RequestException as exc:
        raise AmisFetchError(f"GET failed for {city} ({url}): {exc}") from exc

    soup = BeautifulSoup(r0.text, "lxml")
    fields = _extract_hidden_fields(soup)
    payload = dict(fields)
    payload["ctl00$cphPage$DateTextBox"] = day.strftime("%m/%d/%Y")
    payload["ctl00$cphPage$ReminderButton"] = "Show prices"

    try:
        r1 = session.post(url, data=payload, timeout=AMIS_REQUEST_TIMEOUT_S)
        r1.raise_for_status()
    except requests.RequestException as exc:
        raise AmisFetchError(f"POST Show prices failed for {city} {day}: {exc}") from exc

    _assert_dated_matches(r1.text, day)
    return r1.text


def fetch_city_day(
    city: str,
    day: date,
    *,
    session: Optional[requests.Session] = None,
    raw_dir: Path = DEFAULT_RAW_DIR,
    polite_delay_s: float = AMIS_POLITE_DELAY_S,
    use_cache: bool = True,
) -> str:
    """Fetch ViewPrices HTML for one city/day.

    Uses one requests.Session (created if omitted), ASP.NET VIEWSTATE handling,
    DateTextBox + Show prices, 3 retries with exponential backoff, 20 s timeout.
    Cached under data/raw/{city}/{YYYY-MM-DD}.html when appropriate.
    """
    path = cache_path(city, day, raw_dir)
    if use_cache and path.is_file():
        logger.info("Cache hit %s", path)
        return path.read_text(encoding="utf-8", errors="replace")

    owns_session = session is None
    if session is None:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": AMIS_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    last_exc: Optional[Exception] = None
    try:
        for attempt in range(AMIS_MAX_RETRIES):
            try:
                if polite_delay_s > 0:
                    time.sleep(polite_delay_s)
                html = _post_for_day(session, city, day)
                if use_cache and _should_cache_html(html, day):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(html, encoding="utf-8", errors="replace")
                    logger.info("Cached %s", path)
                elif use_cache:
                    logger.info(
                        "Skipping cache for empty/recent day %s %s", city, day.isoformat()
                    )
                return html
            except (AmisFetchError, AmisDateMismatchError) as exc:
                last_exc = exc
                backoff = 2**attempt
                logger.warning(
                    "Attempt %s/%s failed for %s %s: %s; backoff %ss",
                    attempt + 1,
                    AMIS_MAX_RETRIES,
                    city,
                    day,
                    exc,
                    backoff,
                )
                time.sleep(backoff)
        assert last_exc is not None
        raise last_exc
    finally:
        if owns_session:
            session.close()


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": AMIS_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return session
