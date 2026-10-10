"""Voice/text parse facade + Urdu TTS for the Streamlit UI.

Audio validation:
- Size: rejects > MAX_AUDIO_UPLOAD_BYTES (5 MB) and < MIN_AUDIO_BYTES.
- Duration: for WAV, uses stdlib wave to read frames/rate; rejects outside
  [MIN_AUDIO_DURATION_S, MAX_AUDIO_DURATION_S] and near-silent clips (RMS).
- MP3/other compressed formats: size check only (stdlib cannot decode duration);
  duration/silence checks are skipped with a log note — Gemini still receives bytes.
- st.audio_input (Streamlit): typically returns a BytesIO-like UploadedFile with
  type audio/wav (browser MediaRecorder often webm on some browsers — those are
  rejected with a clear message unless MIME is in ALLOWED_AUDIO_MIME).
"""

from __future__ import annotations

import io
import logging
import math
import os
import struct
import wave
from typing import Any, Optional

from dotenv import load_dotenv

from config import (
    AUDIO_SILENCE_RMS,
    MAX_AUDIO_DURATION_S,
    MAX_AUDIO_UPLOAD_BYTES,
    MIN_AUDIO_BYTES,
    MIN_AUDIO_DURATION_S,
)
from llm_client import ALLOWED_AUDIO_MIME, LLMError, resolve_api_key, resolve_model_name
from schema import ParseOutcome
from voice_parser import parse_request

logger = logging.getLogger(__name__)
load_dotenv()

# Browser / Streamlit aliases that may need conversion
_BROWSER_MIME_FALLBACK = {"audio/webm", "audio/mp4", "audio/x-m4a"}


def gemini_model_name() -> str:
    """Resolved model ID (GEMINI_MODEL > LLM_MODEL > DEFAULT_MODEL)."""
    return resolve_model_name()


def ensure_gemini_env() -> None:
    """Push resolved key/model into env for llm_client (never log the key)."""
    key = resolve_api_key()
    if key and not os.getenv("GEMINI_API_KEY"):
        os.environ["GEMINI_API_KEY"] = key
    model = gemini_model_name()
    os.environ.setdefault("GEMINI_MODEL", model)


def _wav_duration_and_rms(audio_bytes: bytes) -> tuple[Optional[float], Optional[float]]:
    """Return (duration_s, rms) for WAV; (None, None) if not parseable as WAV."""
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            nframes = wf.getnframes()
            rate = wf.getframerate()
            nch = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            if rate <= 0 or nframes <= 0:
                return 0.0, 0.0
            duration = nframes / float(rate)
            raw = wf.readframes(nframes)
        if sampwidth != 2:
            # Only RMS-check 16-bit PCM; duration still valid
            return duration, None
        # Interpret as signed 16-bit little-endian
        count = len(raw) // 2
        if count == 0:
            return duration, 0.0
        fmt = "<" + "h" * count
        samples = struct.unpack(fmt, raw[: count * 2])
        # Mixdown: average absolute across channels roughly via all samples
        mean_sq = sum(s * s for s in samples) / float(count)
        rms = math.sqrt(mean_sq)
        return duration, rms
    except Exception as exc:
        logger.debug("WAV parse failed: %s", exc)
        return None, None


def validate_audio(audio_bytes: bytes, mime_type: str) -> Optional[str]:
    """Return an error message if audio is unusable, else None."""
    if not audio_bytes:
        return "Audio is empty. Please record or upload again."
    if len(audio_bytes) < MIN_AUDIO_BYTES:
        return "Audio is too short or empty. Please record again (a few seconds)."
    if len(audio_bytes) > MAX_AUDIO_UPLOAD_BYTES:
        mb = MAX_AUDIO_UPLOAD_BYTES / (1024 * 1024)
        return f"Audio is too large (max {mb:.0f} MB). Please upload a shorter clip."

    mime = (mime_type or "").strip().lower()
    if mime and mime not in ALLOWED_AUDIO_MIME and mime not in _BROWSER_MIME_FALLBACK:
        return "Unsupported audio format. Please upload WAV or MP3."

    # Duration / silence: stdlib wave only for WAV
    is_wav = mime in {"audio/wav", "audio/x-wav", ""} or audio_bytes[:4] == b"RIFF"
    if is_wav and (not mime or mime in {"audio/wav", "audio/x-wav"}):
        duration, rms = _wav_duration_and_rms(audio_bytes)
        if duration is not None:
            if duration < MIN_AUDIO_DURATION_S:
                return (
                    f"Audio is too short ({duration:.1f}s). "
                    f"Please record at least {MIN_AUDIO_DURATION_S:.1f}s."
                )
            if duration > MAX_AUDIO_DURATION_S:
                return (
                    f"Audio is too long ({duration:.0f}s). "
                    f"Please keep recordings under {MAX_AUDIO_DURATION_S:.0f}s."
                )
            if rms is not None and rms < AUDIO_SILENCE_RMS:
                return "Audio appears silent. Please speak closer to the mic and try again."
    else:
        logger.debug(
            "Skipping duration/silence check for non-WAV mime=%s (size-only validation)",
            mime,
        )
    return None


def mime_from_upload(obj: Any, fallback: str = "audio/wav") -> str:
    """Infer MIME from a Streamlit UploadedFile / audio_input object."""
    if obj is None:
        return fallback
    t = getattr(obj, "type", None) or getattr(obj, "mime_type", None)
    if t:
        return str(t).strip().lower()
    name = str(getattr(obj, "name", "") or "").lower()
    if name.endswith(".wav"):
        return "audio/wav"
    if name.endswith(".mp3"):
        return "audio/mp3"
    if name.endswith(".ogg"):
        return "audio/ogg"
    if name.endswith(".flac"):
        return "audio/flac"
    if name.endswith(".aac") or name.endswith(".m4a"):
        return "audio/aac"
    if name.endswith(".webm"):
        return "audio/webm"
    return fallback


def parse_text_to_request(text: str, *, use_llm: bool = True) -> ParseOutcome:
    """Parse typed farmer text into ParseOutcome."""
    ensure_gemini_env()
    return parse_request(text=text, use_llm=use_llm)


def parse_audio_to_request(
    audio_bytes: bytes,
    mime_type: str = "audio/wav",
    *,
    use_llm: bool = True,
) -> ParseOutcome:
    """Parse audio bytes into ParseOutcome (LLM path)."""
    ensure_gemini_env()
    err = validate_audio(audio_bytes, mime_type)
    if err:
        return ParseOutcome(
            status="failed",
            request=None,
            missing_fields=["crop", "quantity_maunds", "district"],
            message=err + " Or type your request in the Typed tab.",
        )
    mime = (mime_type or "audio/wav").strip().lower()
    if mime in _BROWSER_MIME_FALLBACK:
        return ParseOutcome(
            status="failed",
            request=None,
            missing_fields=["crop", "quantity_maunds", "district"],
            message=(
                "This recording format needs conversion. "
                "Please upload WAV/MP3 or type your request."
            ),
        )
    return parse_request(
        audio_bytes=audio_bytes,
        mime_type=mime,
        use_llm=use_llm,
    )


def generate_urdu_audio(text: str, *, timeout_s: float = 5.0) -> bytes:
    """Synthesize Urdu speech with gTTS; returns MP3 bytes. 5 s timeout."""
    if not (text or "").strip():
        raise ValueError("empty text for TTS")
    try:
        from gtts import gTTS
    except ImportError as exc:
        raise RuntimeError("gTTS is not installed") from exc

    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

    def _synth() -> bytes:
        buf = io.BytesIO()
        tts = gTTS(text=text.strip(), lang="ur")
        tts.write_to_fp(buf)
        data = buf.getvalue()
        if not data:
            raise RuntimeError("gTTS returned empty audio")
        return data

    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(_synth)
        try:
            return fut.result(timeout=timeout_s)
        except FuturesTimeout as exc:
            raise TimeoutError(f"gTTS timed out after {timeout_s}s") from exc


# Re-export for callers that imported LLMError from here historically
__all__ = [
    "LLMError",
    "ensure_gemini_env",
    "gemini_model_name",
    "generate_urdu_audio",
    "mime_from_upload",
    "parse_audio_to_request",
    "parse_text_to_request",
    "validate_audio",
]
