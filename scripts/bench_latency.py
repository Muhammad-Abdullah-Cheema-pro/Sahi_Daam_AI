"""Latency bench for analyze() and optional live parse paths."""

from __future__ import annotations

import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from advisory_engine import DistrictWeather  # noqa: E402
from analysis.analyze import analyze  # noqa: E402
from llm_client import LLMError, extract_from_text, resolve_api_key  # noqa: E402
from schema import ParsedFarmerRequest  # noqa: E402
from voice_engine import parse_audio_to_request  # noqa: E402

OUT = ROOT / "reports" / "latency.md"

_STUB_WEATHER = DistrictWeather(
    district="Okara",
    forecast_date="stub",
    precip_mm_48h=0.0,
    max_precip_prob=0.0,
    temp_max_c=30.0,
    temp_min_c=20.0,
    source="stub",
    from_cache=True,
    fetched_at=time.time(),
)

_SAMPLE_REQ = ParsedFarmerRequest(
    crop="Tomato",
    quantity_maunds=40,
    district="Okara",
    quoted_price_per_maund=2800,
)

_PROBE = "40 maund tamatar hain Okara mein, broker 2800 de raha hai"


def _pctl(samples: list[float], p: float) -> float:
    if not samples:
        return float("nan")
    s = sorted(samples)
    k = (len(s) - 1) * p / 100.0
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def _bench_analyze(n: int = 20) -> list[float]:
    analyze(_SAMPLE_REQ, weather_fn=lambda d: _STUB_WEATHER)
    times: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        analyze(_SAMPLE_REQ, weather_fn=lambda d: _STUB_WEATHER)
        times.append(time.perf_counter() - t0)
    return times


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Latency bench",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## analyze() — weather stubbed (MEASURED on this machine)",
        "",
    ]

    samples = _bench_analyze(20)
    lines.append("- n=20 warm runs")
    lines.append(f"- p50: **{statistics.median(samples) * 1000:.1f} ms**")
    lines.append(f"- p95: **{_pctl(samples, 95) * 1000:.1f} ms**")
    lines.append("")

    key = resolve_api_key()
    if not key:
        lines.append("## Live LLM parse — SKIPPED (no API key)")
    else:
        live_ok = True
        try:
            extract_from_text(_PROBE)
        except LLMError as exc:
            live_ok = False
            lines.append(f"## Live LLM parse — SKIPPED ({exc.cause})")

        if live_ok:
            text_times: list[float] = []
            for _ in range(10):
                t0 = time.perf_counter()
                extract_from_text(_PROBE)
                text_times.append(time.perf_counter() - t0)
            lines.append("## Live typed parse (10 calls)")
            lines.append(f"- p50: **{statistics.median(text_times) * 1000:.1f} ms**")
            lines.append(f"- p95: **{_pctl(text_times, 95) * 1000:.1f} ms**")
            lines.append("")

            synth = ROOT / "tests" / "voice_audio_synth" / "3.mp3"
            if not synth.is_file():
                lines.append("## Live audio parse — SKIPPED (run eval_voice_synth first)")
            else:
                audio = synth.read_bytes()
                audio_times: list[float] = []
                for _ in range(5):
                    t0 = time.perf_counter()
                    parse_audio_to_request(audio, mime_type="audio/mp3", use_llm=True)
                    audio_times.append(time.perf_counter() - t0)
                lines.append("## Live audio parse (5 calls, synth clip id=3)")
                lines.append(f"- p50: **{statistics.median(audio_times) * 1000:.1f} ms**")
                lines.append(f"- p95: **{_pctl(audio_times, 95) * 1000:.1f} ms**")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
