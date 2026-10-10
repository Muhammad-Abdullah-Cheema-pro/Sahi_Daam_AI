"""PASS/FAIL preflight checklist for deploy (never prints secrets)."""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    re.compile(r"GEMINI_API_KEY\s*=\s*['\"]?[A-Za-z0-9_\-]{10,}"),
    re.compile(r"\bAQ\.[A-Za-z0-9_\-]{20,}"),
]


def _check(name: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    extra = f" — {detail}" if detail else ""
    print(f"{status} {name}{extra}")
    return ok


def main() -> int:
    results = []

    # .env untracked
    r = subprocess.run(
        ["git", "ls-files", ".env"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    results.append(_check(".env untracked", not (r.stdout or "").strip()))

    # secrets in tree (tracked files only)
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    leak_hits = []
    for rel in tracked:
        if rel.endswith((".png", ".jpg", ".wav", ".mp3", ".db")):
            continue
        path = ROOT / rel
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pat in SECRET_PATTERNS:
            if pat.search(text):
                leak_hits.append(f"{rel}:pattern")
                break
    results.append(_check("no secrets in tracked tree", not leak_hits, str(leak_hits[:3])))

    # data file
    csv_path = ROOT / "data" / "amis_prices.csv"
    latest = ""
    if csv_path.exists():
        import pandas as pd

        df = pd.read_csv(csv_path)
        latest = str(pd.to_datetime(df["date"]).max().date()) if not df.empty else "empty"
    results.append(_check("data/amis_prices.csv present", csv_path.exists(), f"latest={latest}"))

    # README markers
    readme = (ROOT / "README.md").read_text(encoding="utf-8", errors="ignore")
    bad = []
    if "TODO" in readme and "team" not in readme.lower():
        pass
    # Allow DEPLOYED_URL fill and blank team table
    for marker in ("TBD_METRIC", "FIXME", "<invent"):
        if marker in readme:
            bad.append(marker)
    results.append(_check("README has no invented-metric placeholders", not bad, str(bad)))
    results.append(_check("README mentions DEPLOYED_URL", "DEPLOYED_URL" in readme))

    # reports exist
    reports = [
        "reports/data_quality.md",
        "reports/metrics.md",
        "reports/spread.md",
    ]
    missing = [p for p in reports if not (ROOT / p).exists()]
    results.append(_check("core reports exist", not missing, str(missing)))

    # tests
    t = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=no"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    results.append(_check("pytest green", t.returncode == 0, (t.stdout or "")[-120:]))

    # check_env (may FAIL without key — report honestly)
    ce = subprocess.run(
        [sys.executable, "-m", "scripts.check_env"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    results.append(
        _check(
            "check_env",
            ce.returncode == 0,
            "see scripts.check_env output (key/model)",
        )
    )

    print(f"\nPreflight finished {datetime.now().isoformat(timespec='seconds')}")
    print(f"PASS={sum(results)} FAIL={len(results) - sum(results)}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
