"""AI config single-source-of-truth and LLMError cause classification."""

from __future__ import annotations

import warnings

import llm_client as lc
from config import DEFAULT_MODEL
from llm_client import LLMError, classify_exception, resolve_model_name


def test_default_model_constant(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    assert DEFAULT_MODEL == "gemini-3.8-flash"
    assert resolve_model_name() == DEFAULT_MODEL


def test_gemini_model_precedence(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-flash-test")
    monkeypatch.setenv("LLM_MODEL", "gemini-legacy")
    assert resolve_model_name() == "gemini-flash-test"


def test_llm_model_deprecated_warns_once(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setenv("LLM_MODEL", "gemini-legacy-only")
    lc._LLM_MODEL_WARNED = False
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        assert resolve_model_name() == "gemini-legacy-only"
        assert resolve_model_name() == "gemini-legacy-only"
    assert any(issubclass(x.category, DeprecationWarning) for x in w)


def test_missing_key_cause(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    try:
        lc._api_key()
        assert False, "expected LLMError"
    except LLMError as exc:
        assert exc.cause == "missing_key"
        assert "GEMINI_API_KEY" in exc.hint or "OPENROUTER" in exc.hint


def test_openrouter_model_normalization(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")
    assert resolve_model_name() == "google/gemini-3.8-flash"
    monkeypatch.setenv("GEMINI_MODEL", "google/gemini-3.8-flash")
    assert resolve_model_name() == "google/gemini-3.8-flash"


def test_gemini_strips_openrouter_prefix(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_MODEL", "google/gemini-3.8-flash")
    assert resolve_model_name() == "gemini-3.8-flash"


def test_openrouter_key_resolution(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")
    assert lc.resolve_api_key() == "sk-or-test-key"


def test_classify_causes() -> None:
    assert classify_exception(Exception("401 unauthorized api key")) == "auth"
    assert classify_exception(Exception("model xyz is not found")) == "model_not_found"
    assert classify_exception(Exception("429 RESOURCE_EXHAUSTED quota")) == "quota"
    assert classify_exception(Exception("request timed out")) == "timeout"
    assert classify_exception(Exception("empty model response")) == "bad_output"
