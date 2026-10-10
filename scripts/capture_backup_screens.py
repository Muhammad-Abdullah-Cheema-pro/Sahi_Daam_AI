"""Capture backup UI screenshots via Playwright + Streamlit (dev)."""

from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "backup"
MANIFEST = OUT / "MANIFEST.md"


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("SKIP: playwright not installed")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    port = 8510
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(ROOT / "app.py"),
            "--server.port",
            str(port),
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    entries: list[str] = [
        "# Backup screenshots MANIFEST",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "| File | Viewport | Timestamp (UTC) | Mode |",
        "| --- | --- | --- | --- |",
    ]
    try:
        time.sleep(8)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            for name, w, h in (("phone", 390, 844), ("desktop", 1280, 800)):
                page = browser.new_page(viewport={"width": w, "height": h})
                page.goto(url, wait_until="networkidle", timeout=60000)
                ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                path = OUT / f"landing_{name}.png"
                page.screenshot(path=str(path), full_page=True)
                entries.append(
                    f"| `{path.name}` | {w}x{h} | {ts} | LIVE run (real app, real data) |"
                )
                # typed confirmation path — fill text and process
                try:
                    page.get_by_role("tab", name="Typed").click()
                    page.locator("textarea").fill(
                        "40 maund tamatar hain Okara mein, broker 2800 de raha hai"
                    )
                    page.get_by_role("button", name="Process text").click()
                    page.wait_for_timeout(4000)
                    path2 = OUT / f"typed_confirm_{name}.png"
                    page.screenshot(path=str(path2), full_page=True)
                    entries.append(
                        f"| `{path2.name}` | {w}x{h} | {ts} | LIVE run |"
                    )
                except Exception as exc:
                    entries.append(f"| (typed_{name}) | {w}x{h} | {ts} | SKIP: {exc} |")
                page.close()
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()

    MANIFEST.write_text("\n".join(entries) + "\n", encoding="utf-8")
    print(MANIFEST.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
