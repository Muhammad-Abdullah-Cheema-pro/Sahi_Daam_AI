"""CLI: parse a farmer message and run fair-price + routing analysis."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.analyze import analyze  # noqa: E402
from voice_parser import parse_request  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    p = argparse.ArgumentParser(description="Demo parse + analyze")
    p.add_argument("text", help="Farmer message")
    p.add_argument("--offline", action="store_true", help="Skip LLM for parsing")
    args = p.parse_args(argv)

    outcome = parse_request(args.text, use_llm=not args.offline)
    if outcome.status != "ok" or outcome.request is None:
        print(outcome.model_dump_json(indent=2))
        return 1 if outcome.status == "failed" else 0

    result = analyze(outcome.request)
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
