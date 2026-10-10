"""STT fallback unit tests (no network required)."""

from __future__ import annotations

import io
import wave

from stt_fallback import _ensure_wav_bytes


def _tiny_wav(duration_s: float = 0.3, rate: int = 16000) -> bytes:
    nframes = int(rate * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * nframes)
    return buf.getvalue()


def test_ensure_wav_accepts_riff() -> None:
    wav = _tiny_wav()
    assert _ensure_wav_bytes(wav, "audio/wav") == wav
    assert _ensure_wav_bytes(wav, "audio/mpeg") == wav  # magic wins


def test_ensure_wav_rejects_mp3_magic() -> None:
    assert _ensure_wav_bytes(b"ID3fake-mp3", "audio/mpeg") is None


def test_openrouter_audio_uses_stt_path(monkeypatch) -> None:
    import llm_client as lc

    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("GEMINI_MODEL", "google/gemini-2.5-flash")

    monkeypatch.setattr(
        lc,
        "_extract_via_stt_then_text",
        lambda audio, mime: {
            "crop": "Tomato",
            "quantity": 40.0,
            "quantity_unit": "maund",
            "district": "Okara",
            "quoted_price": 2800.0,
            "price_unit": "per_maund",
            "crop_stage": None,
            "raw_transcript": "40 maund tamatar Okara",
            "language_detected": "ur",
            "confidence": 0.8,
        },
    )

    def _boom(*a, **k):
        raise lc.LLMError("should not call openrouter audio", cause="quota")

    monkeypatch.setattr(lc, "_generate_openrouter", _boom)
    out = lc.extract_from_audio(_tiny_wav(), "audio/wav")
    assert out["crop"] == "Tomato"
    assert out["district"] == "Okara"


def test_openrouter_skips_native_audio_without_flag(monkeypatch) -> None:
    import llm_client as lc

    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.delenv("OPENROUTER_AUDIO", raising=False)
    monkeypatch.setattr(lc, "_extract_via_stt_then_text", lambda *a, **k: None)

    called = {"n": 0}

    def _boom(*a, **k):
        called["n"] += 1
        raise lc.LLMError("should not call", cause="quota")

    monkeypatch.setattr(lc, "_generate_openrouter", _boom)
    try:
        lc.extract_from_audio(_tiny_wav(), "audio/wav")
        assert False, "expected LLMError"
    except lc.LLMError as exc:
        assert exc.cause == "quota"
        assert called["n"] == 0
