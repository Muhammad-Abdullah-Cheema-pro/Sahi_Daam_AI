"""Phase 1 exploration of Punjab AMIS wholesale price pages.

Fetches real HTML only. Does not invent or hard-code price data.
"""

from __future__ import annotations

import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "_inspect"
BASE = "http://www.amis.pk"
VIEW_PRICES = f"{BASE}/ViewPrices.aspx"
PRINTER = f"{BASE}/Printer.aspx"
USER_AGENT = (
    "SahiDaamAI/0.1 (+AICON26; research scraper for agricultural fair-price advisor; "
    "contact: local project; polite 1.5s delay)"
)
TIMEOUT = 20


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return s


def save_html(name: str, text: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / name
    path.write_text(text, encoding="utf-8", errors="replace")
    return path


def days_since_2000(d: date) -> int:
    return (d - date(2000, 1, 1)).days


def extract_hidden_fields(soup: BeautifulSoup) -> dict[str, str]:
    fields: dict[str, str] = {}
    for inp in soup.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        itype = (inp.get("type") or "").lower()
        if itype in {"hidden", "text", "submit"} or name.startswith("__"):
            fields[name] = inp.get("value") or ""
    return fields


def find_calendar_targets(html: str, soup: BeautifulSoup) -> list[str]:
    targets: list[str] = []
    for m in re.finditer(
        r"__doPostBack\('([^']*[Cc]alendar[^']*)'\s*,\s*'([^']*)'\)",
        html,
    ):
        targets.append(f"target={m.group(1)!r} arg={m.group(2)!r}")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "__doPostBack" in href and "alendar" in href.lower():
            targets.append(href[:200])
    # also look for aspNetHidden / client IDs
    for el in soup.find_all(id=re.compile(r"Calendar", re.I)):
        targets.append(f"element id={el.get('id')} name={el.get('name')}")
    return list(dict.fromkeys(targets))


def summarize_table(soup: BeautifulSoup, label: str) -> None:
    tables = soup.find_all("table")
    print(f"\n=== Tables on {label}: {len(tables)} ===")
    for i, table in enumerate(tables):
        rows = table.find_all("tr")
        if not rows:
            continue
        # collect text rows
        text_rows: list[list[str]] = []
        for tr in rows[:12]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            if any(cells):
                text_rows.append(cells)
        if not text_rows:
            continue
        # skip tiny decorative tables
        if len(text_rows) < 2 and max(len(r) for r in text_rows) < 3:
            continue
        print(f"\n-- table[{i}] rows_shown={len(text_rows)} cols={max(len(r) for r in text_rows)} --")
        for r in text_rows[:8]:
            print(" | ".join(r)[:240])


def list_selects(soup: BeautifulSoup) -> None:
    selects = soup.find_all("select")
    print(f"\n=== <select> controls: {len(selects)} ===")
    for sel in selects:
        name = sel.get("name") or sel.get("id") or "?"
        options = []
        for opt in sel.find_all("option"):
            options.append(f"{opt.get('value')!r}={opt.get_text(strip=True)!r}")
        print(f"\nselect name/id={name} count={len(options)}")
        for line in options[:40]:
            print(" ", line)
        if len(options) > 40:
            print(f"  ... ({len(options) - 40} more)")


def fetch_robots(s: requests.Session) -> str:
    url = urljoin(BASE + "/", "robots.txt")
    try:
        r = s.get(url, timeout=TIMEOUT)
        path = save_html("robots.txt", r.text)
        print(f"\n=== robots.txt status={r.status_code} saved={path} ===")
        print(r.text[:2000] if r.text else "(empty)")
        return r.text
    except requests.RequestException as exc:
        print(f"\n=== robots.txt FETCH FAILED: {exc} ===")
        return ""


def fetch_about_terms(s: requests.Session) -> None:
    candidates = [
        f"{BASE}/",
        f"{BASE}/Default.aspx",
        f"{BASE}/AboutUs.aspx",
        f"{BASE}/About.aspx",
        f"{BASE}/Terms.aspx",
        f"{BASE}/Disclaimer.aspx",
        f"{BASE}/ContactUs.aspx",
    ]
    print("\n=== About / terms / disclaimer probes ===")
    for url in candidates:
        try:
            r = s.get(url, timeout=TIMEOUT)
            soup = BeautifulSoup(r.text, "lxml")
            title = (soup.title.get_text(strip=True) if soup.title else "")[:120]
            # look for terms-like language
            text = soup.get_text(" ", strip=True).lower()
            hits = [
                k
                for k in (
                    "terms",
                    "copyright",
                    "disclaimer",
                    "scrap",
                    "robot",
                    "reproduce",
                    "unauthorized",
                    "data",
                )
                if k in text
            ]
            fname = "home_or_" + re.sub(r"[^a-zA-Z0-9]+", "_", url.split("/")[-1] or "root") + ".html"
            save_html(fname, r.text)
            print(f"  {url} -> {r.status_code} title={title!r} keyword_hits={hits}")
            # print a short snippet around disclaimer/copyright if present
            for kw in ("disclaimer", "copyright", "terms of use", "all rights"):
                idx = text.find(kw)
                if idx >= 0:
                    snippet = text[max(0, idx - 40) : idx + 160]
                    print(f"    snippet[{kw}]: ...{snippet}...")
        except requests.RequestException as exc:
            print(f"  {url} -> FAILED {exc}")


def inspect_get(s: requests.Session, url: str, save_as: str) -> BeautifulSoup:
    print(f"\n########## GET {url}")
    r = s.get(url, timeout=TIMEOUT)
    path = save_html(save_as, r.text)
    print(f"status={r.status_code} bytes={len(r.content)} saved={path}")
    soup = BeautifulSoup(r.text, "lxml")
    if soup.title:
        print(f"title: {soup.title.get_text(strip=True)}")
    fields = extract_hidden_fields(soup)
    interesting = {
        k: (v[:80] + "..." if len(v) > 80 else v)
        for k, v in fields.items()
        if k.startswith("__") or "viewstate" in k.lower() or "event" in k.lower()
    }
    print(f"\n=== ASP.NET / hidden fields (truncated) count={len(fields)} ===")
    for k, v in sorted(interesting.items()):
        print(f"  {k}: {v!r}")
    other = [k for k in fields if k not in interesting]
    if other:
        print("other input names:", ", ".join(other[:40]))

    cals = find_calendar_targets(r.text, soup)
    print(f"\n=== Calendar postback targets / ids ({len(cals)}) ===")
    for line in cals[:30]:
        print(" ", line)

    list_selects(soup)
    summarize_table(soup, save_as)
    return soup


def try_calendar_postback(
    s: requests.Session,
    start_url: str,
    target_day: date,
    save_as: str,
) -> None:
    """Attempt ASP.NET calendar postback for a past date."""
    print(f"\n########## Calendar postback experiment for {target_day.isoformat()}")
    r0 = s.get(start_url, timeout=TIMEOUT)
    soup0 = BeautifulSoup(r0.text, "lxml")
    fields = extract_hidden_fields(soup0)

    # Discover actual calendar target from page
    m = re.search(
        r"__doPostBack\('([^']*[Cc]alendar[^']*)'\s*,\s*'([^']*)'\)",
        r0.text,
    )
    if m:
        target = m.group(1)
        sample_arg = m.group(2)
        print(f"discovered calendar target={target!r} sample_arg={sample_arg!r}")
    else:
        target = "ctl00$cphPage$Calendar1"
        print(f"no calendar __doPostBack found; hypothesis fallback target={target!r}")

    arg = str(days_since_2000(target_day))
    print(
        f"hypothesis: days since 2000-01-01 for {target_day} = {arg} "
        f"(also Oct 1 2026 would be {days_since_2000(date(2026, 10, 1))})"
    )

    payload = dict(fields)
    payload["__EVENTTARGET"] = target
    payload["__EVENTARGUMENT"] = arg

    # May need to navigate calendar months first; try direct day select
    r1 = s.post(start_url, data=payload, timeout=TIMEOUT)
    path = save_html(save_as, r1.text)
    print(f"post status={r1.status_code} bytes={len(r1.content)} saved={path}")
    soup1 = BeautifulSoup(r1.text, "lxml")
    summarize_table(soup1, save_as)

    # Also try common alternate arg formats
    alts = [
        target_day.strftime("%Y-%m-%d"),
        target_day.strftime("%d/%m/%Y"),
        str(target_day.toordinal()),
    ]
    for i, alt in enumerate(alts):
        payload2 = dict(fields)
        payload2["__EVENTTARGET"] = target
        payload2["__EVENTARGUMENT"] = alt
        r2 = s.post(start_url, data=payload2, timeout=TIMEOUT)
        save_html(f"{save_as}.alt{i}.html", r2.text)
        soup2 = BeautifulSoup(r2.text, "lxml")
        # quick signal: does page mention the date?
        hit = target_day.strftime("%d") in soup2.get_text(" ", strip=True)
        print(f"  alt arg={alt!r} status={r2.status_code} date_day_in_text={hit}")


def probe_commodity_ids(s: requests.Session) -> None:
    print("\n########## commodityId / city id probe (searchType=1)")
    for cid in [1, 2, 3, 7, 11, 16, 20]:
        url = f"{VIEW_PRICES}?searchType=1&commodityId={cid}"
        try:
            r = s.get(url, timeout=TIMEOUT)
            soup = BeautifulSoup(r.text, "lxml")
            title = soup.title.get_text(strip=True) if soup.title else ""
            # look for city name hints in headings / selected options / bold text
            h = soup.find(["h1", "h2", "h3", "span", "td"], string=re.compile(r"Faisalabad|Multan|Lahore|Sargodha|Gujranwala|City|Market", re.I))
            hint = h.get_text(" ", strip=True) if h else ""
            # first meaningful table cell texts
            cells = [c.get_text(" ", strip=True) for c in soup.find_all("td")[:15]]
            cells = [c for c in cells if c][:8]
            save_html(f"viewprices_commodityId_{cid}.html", r.text)
            print(f"  id={cid} status={r.status_code} title={title!r} hint={hint!r}")
            print(f"       early_cells={cells}")
        except requests.RequestException as exc:
            print(f"  id={cid} FAILED {exc}")


def main() -> int:
    print("Sahi Daam AI — AMIS Phase 1 inspection")
    print(f"today (local): {datetime.now().isoformat(timespec='seconds')}")
    print(f"days_since_2000(2026-10-01) = {days_since_2000(date(2026, 10, 1))} (hypothesis: 9770)")
    print(f"days_since_2000(2026-09-24) = {days_since_2000(date(2026, 9, 24))}")

    s = session()

    fetch_robots(s)
    fetch_about_terms(s)

    url_faisalabad = f"{VIEW_PRICES}?searchType=1&commodityId=2"
    inspect_get(s, url_faisalabad, "viewprices_searchType1_commodityId2.html")

    printer_url = f"{PRINTER}?searchType=1&commodityId=2"
    try:
        inspect_get(s, printer_url, "printer_searchType1_commodityId2.html")
    except requests.RequestException as exc:
        print(f"Printer.aspx failed: {exc}")

    probe_commodity_ids(s)

    # Past date test — 24 Sep 2026 (may have data when "today" is empty)
    past = date(2026, 9, 24)
    try_calendar_postback(
        s,
        url_faisalabad,
        past,
        f"viewprices_post_2026-09-24.html",
    )

    # Also try printer with past date if printer supports query params
    for extra in [
        f"{PRINTER}?searchType=1&commodityId=2&date=24/09/2026",
        f"{PRINTER}?searchType=1&commodityId=2&day=24&month=9&year=2026",
        f"{VIEW_PRICES}?searchType=1&commodityId=2&date=24/09/2026",
    ]:
        try:
            r = s.get(extra, timeout=TIMEOUT)
            save_html(
                "probe_" + re.sub(r"[^a-zA-Z0-9]+", "_", extra.split("?")[-1])[:80] + ".html",
                r.text,
            )
            soup = BeautifulSoup(r.text, "lxml")
            print(f"\nprobe GET {extra} -> {r.status_code} title={(soup.title.get_text(strip=True) if soup.title else '')!r}")
            summarize_table(soup, extra)
        except requests.RequestException as exc:
            print(f"probe failed {extra}: {exc}")

    print("\n########## Phase 1 complete. Review findings above before Phase 2.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except requests.RequestException as exc:
        print(f"FATAL network error: {exc}", file=sys.stderr)
        raise SystemExit(2)
