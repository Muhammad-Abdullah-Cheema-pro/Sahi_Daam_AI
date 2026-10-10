"""Mocked slow/failed external-call paths (offline)."""

from __future__ import annotations

from concurrent.futures import TimeoutError as FuturesTimeout
from unittest.mock import MagicMock, patch

import pytest

from advisory_engine import AdvisoryError, fetch_district_weather
from llm_client import LLMError, classify_exception


def test_weather_timeout_no_cache(tmp_path, monkeypatch) -> None:
    import advisory_engine as ae

    monkeypatch.setattr(ae, "CACHE_DB", tmp_path / "w.db")

    def slow(*a, **k):
        raise TimeoutError("simulated slow weather")

    with patch("advisory_engine.requests.get", side_effect=slow):
        with pytest.raises(AdvisoryError):
            fetch_district_weather("Lahore")


def test_gemini_timeout_cause_and_hint() -> None:
    assert classify_exception(TimeoutError("deadline exceeded")) == "timeout"
    err = LLMError("request timed out", cause="timeout")
    assert err.cause == "timeout"
    assert err.hint


def test_gtts_timeout() -> None:
    from voice_engine import generate_urdu_audio

    class FakeFut:
        def result(self, timeout=None):
            raise FuturesTimeout()

    class FakePool:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def submit(self, fn):
            return FakeFut()

    with patch("gtts.gTTS", MagicMock()):
        with patch("concurrent.futures.ThreadPoolExecutor", FakePool):
            with pytest.raises(TimeoutError):
                generate_urdu_audio("ٹیسٹ", timeout_s=0.01)
