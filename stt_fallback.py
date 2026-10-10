"""Free speech-to-text fallback when OpenRouter audio credits are unavailable.

Uses the SpeechRecognition package + Google's public web endpoint (no API key).
Works best with WAV from Streamlit ``audio_input``.
"""

from __future__ import annotations

import io
import logging
import wave
from typing import Optional

logger = logging.getLogger(__name__)

_LANGS = ("ur-PK", "en-IN", "hi-IN", "en-US")


def _ensure_wav_bytes(audio_bytes: bytes, mime: str) -> Optional[bytes]:
    """Return WAV bytes if we can feed SpeechRecognition without ffmpeg."""
    mime = (mime or "").strip().lower()
    if audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
        return audio_bytes
    if mime in {"audio/wav", "audio/x-wav"}:
        return audio_bytes
    # MP3/OGG need ffmpeg — not available in the lightweight deploy path
    return None


def transcribe_audio_bytes(audio_bytes: bytes, mime_type: str = "audio/wav") -> Optional[str]:
    """Return a transcript string, or None if STT is unavailable / failed."""
    if not audio_bytes:
        return None
    wav = _ensure_wav_bytes(audio_bytes, mime_type)
    if wav is None:
        logger.info("STT fallback skipped — need WAV (got mime=%s)", mime_type)
        return None
    try:
        import speech_recognition as sr
    except ImportError:
        logger.warning("SpeechRecognition not installed — STT fallback unavailable")
        return None

    # Reject empty / corrupt WAV early
    try:
        with wave.open(io.BytesIO(wav), "rb") as wf:
            if wf.getnframes() <= 0 or wf.getframerate() <= 0:
                return None
    except Exception as exc:
        logger.info("STT WAV probe failed: %s", exc)
        return None

    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(io.BytesIO(wav)) as source:
            try:
                recognizer.adjust_for_ambient_noise(source, duration=0.15)
            except Exception:
                pass
            audio = recognizer.record(source)
    except Exception as exc:
        logger.warning("STT AudioFile read failed: %s", exc)
        return None

    last_err: Optional[Exception] = None
    for lang in _LANGS:
        try:
            text = recognizer.recognize_google(audio, language=lang)
            text = (text or "").strip()
            if text:
                logger.info("STT fallback ok lang=%s chars=%s", lang, len(text))
                return text
        except sr.UnknownValueError as exc:
            last_err = exc
            continue
        except sr.RequestError as exc:
            logger.warning("STT Google request failed: %s", exc)
            return None
        except Exception as exc:
            last_err = exc
            continue
    if last_err:
        logger.info("STT produced no transcript: %s", type(last_err).__name__)
    return None
