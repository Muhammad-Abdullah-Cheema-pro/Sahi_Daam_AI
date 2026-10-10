"""Run Phase 6 evaluation scripts and print PASS/FAIL/SKIPPED summary."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def _run(name: str, *args: str, optional: bool = False) -> str:
    cmd = [PY, str(ROOT / "scripts" / name), *args]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        print(f"FAIL {name} — timeout")
        return "FAIL"
    except Exception as exc:
        print(f"FAIL {name} — {exc}")
        return "FAIL"

    tail = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == 0:
        print(f"PASS {name}")
        return "PASS"
    if optional and "SKIP" in tail.upper():
        print(f"SKIPPED {name}")
        return "SKIPPED"
    if name == "check_env.py" and proc.returncode != 0:
        print(f"SKIPPED {name} (no key or API)")
        return "SKIPPED"
    print(f"FAIL {name} (exit {proc.returncode})")
    if tail.strip():
        print(tail.strip()[-500:])
    return "FAIL"


def main() -> int:
    checks: list[tuple[str, tuple[str, ...], bool]] = [
        ("check_env.py", (), True),
        ("evaluate.py", (), False),
        ("estimate_spread.py", (), False),
        ("eval_simulated_quotes.py", (), False),
        ("eval_llm_text.py", ("--sleep", "0.5"), True),
        ("eval_voice_synth.py", (), True),
        ("bench_latency.py", (), True),
        ("data_quality.py", (), False),
        ("check_weather.py", (), True),
        ("eval_trend.py", (), False),
        ("eval_voice.py", (), False),
    ]

    summary: dict[str, str] = {}
    proc = subprocess.run(
        [PY, "-m", "pytest", "-q"],
        cwd=str(ROOT),
        timeout=600,
    )
    summary["pytest"] = "PASS" if proc.returncode == 0 else "FAIL"
    print(f"{summary['pytest']} pytest")

    for script, args, optional in checks:
        summary[script.replace(".py", "")] = _run(script, *args, optional=optional)

    print("\n=== Summary ===")
    for k, v in summary.items():
        print(f"{v:8} {k}")

    fails = [k for k, v in summary.items() if v == "FAIL"]
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
