"""Environment / LLM smoke checks. Prints only OK/FAIL lines (never the key)."""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from config import DEFAULT_MODEL  # noqa: E402
from llm_client import (  # noqa: E402
    extract_from_text,
    resolve_api_key,
    resolve_model_name,
    resolve_provider,
)


def _ok(label: str) -> None:
    print(f"OK  {label}")


def _fail(label: str, detail: str = "") -> None:
    extra = f" — {detail}" if detail else ""
    print(f"FAIL {label}{extra}")


def _list_models(client):
    models = []
    for m in client.models.list():
        models.append(m)
    return models


def _model_ids(models) -> set[str]:
    ids = set()
    for m in models:
        name = getattr(m, "name", None) or ""
        ids.add(name)
        ids.add(name.split("/")[-1] if name else "")
        dn = getattr(m, "display_name", None)
        if dn:
            ids.add(str(dn))
    return ids


def _flash_candidates(models) -> list[str]:
    out = []
    for m in models:
        name = getattr(m, "name", "") or ""
        mid = name.split("/")[-1] if name else ""
        if "flash" in mid.lower():
            out.append(mid)
    return out


def _test_text(client, model: str) -> bool:
    from google.genai import types

    resp = client.models.generate_content(
        model=model,
        contents="Reply with exactly: OK",
        config=types.GenerateContentConfig(temperature=0.0),
    )
    text = (getattr(resp, "text", None) or "").strip()
    return bool(text)


def _csv_row(n: int) -> dict:
    path = ROOT / "tests" / "voice_cases.csv"
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        if str(r.get("id", "")) == "9":
            return r
    return rows[min(8, len(rows) - 1)]


def _test_audio(client, model: str) -> tuple[bool, str]:
    from gtts import gTTS
    from google.genai import types

    from llm_client import LLMExtraction, SYSTEM_PROMPT

    row = _csv_row(9)
    phrase = (row.get("spoken_urdu_script") or row.get("spoken_text") or "").strip()
    if not phrase:
        return False, "no phrase in voice_cases row 9"
    buf = io.BytesIO()
    gTTS(text=phrase, lang="ur").write_to_fp(buf)
    audio = buf.getvalue()
    part = types.Part.from_bytes(data=audio, mime_type="audio/mp3")
    cfg = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=LLMExtraction,
        temperature=0.0,
    )
    resp = client.models.generate_content(
        model=model,
        contents=["Transcribe and extract the farmer sale request from this audio.", part],
        config=cfg,
    )
    text = (getattr(resp, "text", None) or "").strip()
    if not text:
        return False, "empty audio response"
    ext = LLMExtraction.model_validate_json(text)
    exp_crop = (row.get("crop") or "").strip().lower()
    exp_dist = (row.get("district") or "").strip().lower()
    exp_qty = row.get("quantity_maunds")
    crop_ok = ext.crop and exp_crop in ext.crop.lower()
    dist_ok = ext.district and exp_dist in ext.district.lower()
    qty_ok = True
    if exp_qty not in (None, ""):
        try:
            qty_ok = ext.quantity is not None and abs(float(ext.quantity) - float(exp_qty)) < 0.6
        except ValueError:
            qty_ok = False
    if crop_ok and dist_ok and qty_ok:
        return True, "crop/qty/district match"
    return False, f"got crop={ext.crop} qty={ext.quantity} dist={ext.district}"


def _check_openrouter() -> int:
    key = resolve_api_key()
    if key:
        _ok("API key present (OpenRouter)")
    else:
        _fail("API key present", "set OPENROUTER_API_KEY")
        return 1

    model = resolve_model_name()
    _ok(f"provider=openrouter model={model}")

    try:
        out = extract_from_text(
            "40 maund tamatar hain Okara mein, broker 2800 de raha hai"
        )
        if out.get("crop") or out.get("district") or out.get("quantity"):
            _ok(f"TEXT extract_from_text ({model})")
            print(
                f"INFO fields crop={out.get('crop')} qty={out.get('quantity')} "
                f"dist={out.get('district')}"
            )
            return 0
        _fail(f"TEXT extract_from_text ({model})", "empty fields")
        return 1
    except Exception as exc:
        _fail(f"TEXT extract_from_text ({model})", type(exc).__name__)
        print(f"INFO {type(exc).__name__}: {exc}")
        print(
            "RECOMMEND try GEMINI_MODEL=google/gemini-2.5-flash or "
            "google/gemini-flash-1.5"
        )
        return 1


def _check_gemini() -> int:
    key = resolve_api_key()
    if key:
        _ok("API key present")
    else:
        _fail("API key present", "set GEMINI_API_KEY")
        return 1

    model = resolve_model_name()
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=key,
            http_options=types.HttpOptions(timeout=30000),
        )
        models = _list_models(client)
        ids = _model_ids(models)
        if model in ids or f"models/{model}" in ids:
            _ok(f"GEMINI_MODEL exists ({model})")
        else:
            _fail(f"GEMINI_MODEL exists ({model})", "not in listing")
    except Exception as exc:
        _fail("list models", type(exc).__name__)
        return 1

    text_ok = False
    try:
        text_ok = _test_text(client, model)
        if text_ok:
            _ok(f"TEXT generate_content ({model})")
        else:
            _fail(f"TEXT generate_content ({model})", "empty")
    except Exception as exc:
        _fail(f"TEXT generate_content ({model})", type(exc).__name__)

    audio_ok = False
    try:
        audio_ok, detail = _test_audio(client, model)
        if audio_ok:
            _ok(f"AUDIO extract ({model})")
        else:
            _fail(f"AUDIO extract ({model})", detail)
    except Exception as exc:
        _fail(f"AUDIO extract ({model})", type(exc).__name__)

    if text_ok and audio_ok:
        return 0

    cands = _flash_candidates(models)
    print(f"INFO trying other flash models: {cands[:8]}")
    for mid in cands:
        if mid == model:
            continue
        try:
            t_ok = _test_text(client, mid)
            a_ok, _ = _test_audio(client, mid) if t_ok else (False, "")
            print(
                f"INFO flash candidate {mid}: "
                f"text={'OK' if t_ok else 'FAIL'} audio={'OK' if a_ok else 'FAIL'}"
            )
            if t_ok and a_ok:
                print(f"RECOMMEND set GEMINI_MODEL={mid}  (do not auto-edit .env)")
                return 0
        except Exception as exc:
            print(f"INFO flash candidate {mid}: error {type(exc).__name__}")
    print(f"RECOMMEND keep trying flash models; current DEFAULT_MODEL={DEFAULT_MODEL}")
    return 1


def main() -> int:
    provider = resolve_provider()
    print(f"INFO LLM_PROVIDER={provider}")
    if provider == "openrouter":
        return _check_openrouter()
    return _check_gemini()


if __name__ == "__main__":
    raise SystemExit(main())
