"""Evaluate human voice recordings under tests/voice_audio/ (HUMAN)."""

from __future__ import annotations

import csv
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from voice_engine import mime_from_upload, parse_audio_to_request  # noqa: E402

OUT = ROOT / "reports" / "voice_metrics.md"
CASES = ROOT / "tests" / "voice_cases.csv"
AUDIO_DIR = ROOT / "tests" / "voice_audio"
EXTS = (".wav", ".mp3", ".m4a", ".ogg", ".flac")


def _find_audio(case_id: str) -> Path | None:
    for ext in EXTS:
        p = AUDIO_DIR / f"{case_id}{ext}"
        if p.is_file():
            return p
    return None


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
    rows = list(csv.DictReader(CASES.open(encoding="utf-8")))
    OUT.parent.mkdir(parents=True, exist_ok=True)

    found = [r for r in rows if _find_audio(r["id"])]
    lines = [
        "# Voice metrics (human recordings)",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
    ]
    if not found:
        lines.append("**no human recordings yet**")
        lines.append("")
        lines.append(
            f"Add files under `{AUDIO_DIR.relative_to(ROOT)}/<id>.wav` "
            "(see README for exact phrases)."
        )
        OUT.write_text("\n".join(lines), encoding="utf-8")
        print("No human recordings")
        return 0

    lines.append(f"Recordings found: **{len(found)}/{len(rows)}**")
    lines.append("")
    lines.append("| id | full row OK | status |")
    lines.append("| ---: | --- | --- |")

    full_ok = 0
    for row in found:
        path = _find_audio(row["id"])
        assert path is not None
        audio = path.read_bytes()
        mime = mime_from_upload(type("F", (), {"name": path.name})())
        outcome = parse_audio_to_request(audio, mime_type=mime, use_llm=True)
        req = outcome.request if outcome.status == "ok" else None
        full = req is not None and all(
            _field_ok(req, row, f)
            for f in ("crop", "district", "quantity_maunds", "quote")
        )
        if full:
            full_ok += 1
        lines.append(
            f"| {row['id']} | {'yes' if full else 'no'} | {outcome.status} |"
        )

    lines.append("")
    lines.append(f"Full-row accuracy (present clips only): **{full_ok}/{len(found)}**")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
