"""CLI: try parsing a farmer sale message."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from voice_parser import parse_request  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    p = argparse.ArgumentParser(description="Parse a farmer sale request")
    p.add_argument("text", nargs="?", default=None, help="Spoken/typed message")
    p.add_argument("--audio", type=Path, default=None, help="Path to audio file")
    p.add_argument("--mime", default=None, help="Audio MIME type (optional)")
    p.add_argument("--offline", action="store_true", help="Skip LLM; rule-based only")
    args = p.parse_args(argv)

    audio_bytes = None
    mime = args.mime
    if args.audio is not None:
        audio_bytes = args.audio.read_bytes()
        if mime is None:
            suffix = args.audio.suffix.lower()
            mime = {
                ".wav": "audio/wav",
                ".mp3": "audio/mpeg",
                ".flac": "audio/flac",
                ".ogg": "audio/ogg",
                ".aac": "audio/aac",
                ".aiff": "audio/aiff",
            }.get(suffix, "application/octet-stream")

    outcome = parse_request(
        text=args.text,
        audio_bytes=audio_bytes,
        mime_type=mime,
        use_llm=not args.offline,
    )
    print(outcome.model_dump_json(indent=2))
    return 1 if outcome.status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
