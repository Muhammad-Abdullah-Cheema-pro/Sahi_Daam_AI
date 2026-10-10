"""Hypothesis fuzz + no-leakage + determinism (offline)."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from model.price_band import get_band
from schema import ParseOutcome
from voice_parser import parse_request

try:
    from hypothesis import given, settings, strategies as st

    HAS_HYPOTHESIS = True
except ImportError:  # pragma: no cover
    HAS_HYPOTHESIS = False


@pytest.mark.skipif(not HAS_HYPOTHESIS, reason="hypothesis not installed")
def test_offline_parser_never_raises() -> None:
    @given(st.text(min_size=0, max_size=500))
    @settings(max_examples=40, deadline=None)
    def _inner(text: str) -> None:
        out = parse_request(text=text, use_llm=False)
        assert isinstance(out, ParseOutcome)
        assert out.status in {"ok", "needs_clarification", "failed"}

    _inner()


def test_no_leakage_get_band() -> None:
    rows = []
    base = date(2026, 8, 1)
    for i in range(40):
        rows.append(
            {
                "date": base + timedelta(days=i),
                "city": "Lahore",
                "commodity": "Tomato",
                "fqp_rs_maund": 3000.0 + i,
                "fqp_rs_100kg": (3000.0 + i) / 0.4,
                "min_rs_maund": 2900.0,
                "max_rs_maund": 3100.0,
                "is_suspect": False,
            }
        )
    df = pd.DataFrame(rows)
    as_of = base + timedelta(days=30)
    before = get_band("Lahore", "Tomato", as_of=as_of, df=df)
    future = pd.DataFrame(
        [
            {
                "date": as_of + timedelta(days=5),
                "city": "Lahore",
                "commodity": "Tomato",
                "fqp_rs_maund": 99999.0,
                "fqp_rs_100kg": 99999.0 / 0.4,
                "min_rs_maund": 99999.0,
                "max_rs_maund": 99999.0,
                "is_suspect": False,
            }
        ]
    )
    df2 = pd.concat([df, future], ignore_index=True)
    after = get_band("Lahore", "Tomato", as_of=as_of, df=df2)
    assert before.avg == after.avg
    assert before.low == after.low
    assert before.high == after.high
    assert before.basis == after.basis


def test_determinism_same_input_same_band() -> None:
    rows = []
    base = date(2026, 8, 1)
    for i in range(40):
        rows.append(
            {
                "date": base + timedelta(days=i),
                "city": "Multan",
                "commodity": "Onion",
                "fqp_rs_maund": 2000.0 + (i % 5) * 10,
                "fqp_rs_100kg": (2000.0 + (i % 5) * 10) / 0.4,
                "min_rs_maund": 1900.0,
                "max_rs_maund": 2100.0,
                "is_suspect": False,
            }
        )
    df = pd.DataFrame(rows)
    as_of = base + timedelta(days=35)
    a = get_band("Multan", "Onion", as_of=as_of, df=df)
    b = get_band("Multan", "Onion", as_of=as_of, df=df)
    assert a.basis == b.basis
    assert a.avg == b.avg
    assert a.low == b.low
    assert a.high == b.high
