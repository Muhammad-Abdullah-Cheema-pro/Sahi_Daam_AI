"""Audio validation tests with generated WAV bytes (offline)."""

from __future__ import annotations

import io
import math
import struct
import wave
from types import SimpleNamespace

from voice_engine import mime_from_upload, parse_audio_to_request, validate_audio


def _make_wav(
    duration_s: float = 1.0,
    *,
    rate: int = 16000,
    freq: float = 440.0,
    amplitude: int = 8000,
) -> bytes:
    nframes = int(rate * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        frames = bytearray()
        for i in range(nframes):
            val = int(amplitude * math.sin(2 * math.pi * freq * i / rate))
            frames += struct.pack("<h", val)
        wf.writeframes(frames)
    return buf.getvalue()


def _make_silent_wav(duration_s: float = 1.0, rate: int = 16000) -> bytes:
    return _make_wav(duration_s, rate=rate, amplitude=0)


def test_valid_wav_ok() -> None:
    data = _make_wav(1.0)
    assert validate_audio(data, "audio/wav") is None


def test_too_short_duration() -> None:
    data = _make_wav(0.1)
    err = validate_audio(data, "audio/wav")
    assert err is not None
    assert "short" in err.lower()


def test_silent_rejected() -> None:
    data = _make_silent_wav(1.0)
    err = validate_audio(data, "audio/wav")
    assert err is not None
    assert "silent" in err.lower()


def test_too_large() -> None:
    # Bypass duration by using non-wav mime with huge payload
    huge = b"\x00" * (5 * 1024 * 1024 + 10)
    err = validate_audio(huge, "audio/mp3")
    assert err is not None
    assert "large" in err.lower()


def test_truncated_wav() -> None:
    data = _make_wav(1.0)[:40]  # header fragment
    err = validate_audio(data, "audio/wav")
    # either too short by bytes or fails duration — must not crash
    assert err is not None


def test_wrong_extension_mime() -> None:
    data = _make_wav(1.0)
    err = validate_audio(data, "audio/unknown")
    assert err is not None
    assert "Unsupported" in err or "unsupported" in err.lower()


def test_mime_from_fake_recorded_object() -> None:
    obj = SimpleNamespace(type="audio/wav", name="recording.wav")
    assert mime_from_upload(obj) == "audio/wav"
    obj2 = SimpleNamespace(type=None, name="clip.mp3")
    assert mime_from_upload(obj2) == "audio/mp3"


def test_parse_audio_rejects_silent_without_llm() -> None:
    data = _make_silent_wav(1.0)
    out = parse_audio_to_request(data, "audio/wav", use_llm=False)
    assert out.status == "failed"
    assert "silent" in (out.message or "").lower() or "Typed" in (out.message or "")
