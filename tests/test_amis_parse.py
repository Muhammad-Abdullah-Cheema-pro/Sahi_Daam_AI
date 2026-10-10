"""Tests for AMIS HTML parsing and cache skip behaviour."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from data.amis_scraper import (
    AmisDateMismatchError,
    cache_path,
    fetch_city_day,
    parse_city_day,
    parse_dated_header,
)

FIXTURE = Path(__file__).parent / "fixtures" / "amis_sample.html"


@pytest.fixture(scope="module")
def sample_html() -> str:
    assert FIXTURE.is_file(), "tests/fixtures/amis_sample.html missing (real fetched page)"
    return FIXTURE.read_text(encoding="utf-8", errors="replace")


def test_parse_sample_has_rows_and_columns(sample_html: str) -> None:
    day = parse_dated_header(sample_html)
    assert day is not None
    rows = parse_city_day(sample_html, city="Faisalabad", day=day, commodities=None)
    assert len(rows) > 0
    required = {
        "date",
        "city",
        "commodity",
        "min_rs_100kg",
        "max_rs_100kg",
        "fqp_rs_100kg",
        "quantity",
    }
    assert required.issubset(rows[0].keys())
    wheat = [r for r in rows if r["commodity"] == "Wheat"]
    assert wheat
    assert wheat[0]["fqp_rs_100kg"] == 11750.0


def test_parse_rejects_date_mismatch(sample_html: str) -> None:
    with pytest.raises(AmisDateMismatchError):
        parse_city_day(sample_html, city="Faisalabad", day=date(2001, 1, 1))


def test_cached_day_skips_network(tmp_path: Path, sample_html: str, monkeypatch: pytest.MonkeyPatch) -> None:
    city = "Faisalabad"
    day = date(2026, 9, 24)
    path = cache_path(city, day, tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(sample_html, encoding="utf-8")

    def _boom(*_a, **_k):  # pragma: no cover
        raise AssertionError("network should not be called on cache hit")

    monkeypatch.setattr("data.amis_scraper._post_for_day", _boom)
    html = fetch_city_day(city, day, raw_dir=tmp_path, polite_delay_s=0)
    assert "Dated:24-09-2026" in html or parse_dated_header(html) == day


def test_empty_recent_day_not_cached(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty HTML for a recent day must not be written to the cache."""
    city = "Lahore"
    day = date.today() - timedelta(days=1)
    empty_html = """
    <html><body><table>
      <tr><td>Dated:{:%d-%m-%Y}</td><td>Graph</td><td>Min</td><td>Max</td><td>FQP</td><td>Quantity</td></tr>
      <tr><td>1&nbsp Wheat</td><td>Graph</td><td>-</td><td>-</td><td>-</td><td>-</td></tr>
    </table></body></html>
    """.format(day)

    monkeypatch.setattr(
        "data.amis_scraper._post_for_day",
        lambda *_a, **_k: empty_html,
    )
    html = fetch_city_day(city, day, raw_dir=tmp_path, polite_delay_s=0)
    assert html == empty_html
    assert not cache_path(city, day, tmp_path).is_file()
