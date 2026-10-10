"""SYNTHETIC-AUDIO eval: gTTS → Gemini audio parse path."""

from __future__ import annotations

import csv
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from llm_client import resolve_api_key  # noqa: E402
from voice_engine import parse_audio_to_request  # noqa: E402

OUT = ROOT / "reports" / "voice_synth.md"
CASES = ROOT / "tests" / "voice_cases.csv"
SYNTH_DIR = ROOT / "tests" / "voice_audio_synth"
SYNTH_IDS = {"3", "4", "9", "14", "15"}


def _field_ok(req, row: dict, field: str) -> bool:
    if req is None:
        return False
    if field == "crop":
        return req.crop == row["expected_crop"]
    if field == "district":
        return req.district == row["expected_district"]
    if field == "quantity_maunds":
        return abs(req.quantity_maunds - float(row["expected_quantity_maunds"])) < 1e-6
    if field == "quote":
        exp = row["expected_quote_per_maund"].strip()
        if exp == "":
            return req.quoted_price_per_maund is None
        if req.quoted_price_per_maund is None:
            return False
        return abs(req.quoted_price_per_maund - float(exp)) < 1e-6
    return False


def main() -> int:
    rows = {r["id"]: r for r in csv.DictReader(CASES.open(encoding="utf-8"))}
    SYNTH_DIR.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Voice synth metrics (SYNTHETIC-AUDIO)",
        "",
        "**SYNTHETIC-AUDIO:** gTTS Urdu/English clips, not human mandi speech.",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Output dir: `{SYNTH_DIR.relative_to(ROOT)}`",
        "",
    ]

    if not resolve_api_key():
        lines.append("_Skipped live audio parse — no GEMINI_API_KEY._")
        OUT.write_text("\n".join(lines), encoding="utf-8")
        print("SKIP — no API key")
        return 0

    try:
        from gtts import gTTS
    except ImportError:
        lines.append("_gTTS not installed._")
        OUT.write_text("\n".join(lines), encoding="utf-8")
        return 1

    lines.append("| id | lang hint | full row OK | notes |")
    lines.append("| ---: | --- | --- | --- |")

    ok = 0
    for cid in sorted(SYNTH_IDS, key=int):
        row = rows.get(cid)
        if not row:
            continue
        text = row["spoken_text"].strip()
        lang = "ur" if any("\u0600" <= ch <= "\u06ff" for ch in text) else "en"
        mp3_path = SYNTH_DIR / f"{cid}.mp3"
        buf = __import__("io").BytesIO()
        gTTS(text=text, lang=lang).write_to_fp(buf)
        audio = buf.getvalue()
        mp3_path.write_bytes(audio)

        outcome = parse_audio_to_request(audio, mime_type="audio/mp3", use_llm=True)
        req = outcome.request if outcome.status == "ok" else None
        full = req is not None and all(
            _field_ok(req, row, f)
            for f in ("crop", "district", "quantity_maunds", "quote")
        )
        if full:
            ok += 1
        note = outcome.message if outcome.status != "ok" else "OK"
        lines.append(f"| {cid} | {lang} | {'yes' if full else 'no'} | {note} |")

    lines.append("")
    lines.append(f"Full-row accuracy: **{ok}/{len(SYNTH_IDS)}** (SYNTHETIC-AUDIO)")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} ({ok}/{len(SYNTH_IDS)} OK)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
