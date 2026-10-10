"""Optional Streamlit AppTest smoke (skipped if AppTest unavailable)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit")

try:
    from streamlit.testing.v1 import AppTest
except Exception:  # pragma: no cover
    AppTest = None  # type: ignore

APP = Path(__file__).resolve().parents[1] / "app.py"


@pytest.mark.skipif(AppTest is None, reason="streamlit.testing.v1.AppTest unavailable")
def test_app_smoke_runs() -> None:
    at = AppTest.from_file(str(APP), default_timeout=10)
    at.run()
    assert not at.exception
