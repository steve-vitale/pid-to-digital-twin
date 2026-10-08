"""Acceptance test for the Docker demo, from what a newcomer would see in the browser (used by CI).

Run after `docker compose up -d` and the gateway reports RUNNING. Checks:
  1. the Tennessee Eastman screen: live values on every instrument with data; only SC-212 (no data) not connected;
  2. extracted sheet 0: 24 mapped points live, 12 not connected;
  3. fault 6: switching the replay turns the reactor pressure label red within 2 minutes.
Screenshots go to the folder given by --shots (CI keeps them as an artifact).

Usage: python scripts/check_docker_demo.py [--url http://localhost:8088] [--shots out-shots]
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

LABELS = '[data-component="ia.display.label"]'
COUNT_JS = """els => els.map(e => e.querySelector('.ia_qualityOverlay') ? 'bad' : 'good')
                     .reduce((a, k) => (a[k] = (a[k] || 0) + 1, a), {good: 0, bad: 0})"""
RED_JS = "els => els.filter(e => e.style.backgroundColor === 'rgb(254, 202, 202)').length"


def wait_counts(page, want_good, want_bad, seconds=180):
    t0, counts = time.time(), {}
    while time.time() - t0 < seconds:
        counts = page.locator(LABELS).evaluate_all(COUNT_JS)
        if counts["good"] >= want_good and counts["bad"] <= want_bad and counts["good"] + counts["bad"] > 0:
            return True, counts
        time.sleep(3)
    # Say what the page showed, so a failure explains itself on the run page.
    text = " ".join(page.locator("body").inner_text().split())[:160]
    counts["page_text"] = text
    return False, counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8088")
    ap.add_argument("--shots", default="out-shots")
    a = ap.parse_args()
    shots = Path(a.shots)
    shots.mkdir(parents=True, exist_ok=True)
    failures = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1400, "height": 960})

        page.goto(f"{a.url}/data/perspective/client/PIDTwin")
        ok, c = wait_counts(page, 36, 1)
        page.screenshot(path=shots / "1-te-overview.png")
        print(f"TE overview: {c} -> {'PASS' if ok else 'FAIL'} (want 36 live, 1 not connected)")
        if not ok:
            failures.append("TE overview")

        page.goto(f"{a.url}/data/perspective/client/PIDTwin/open100/0")
        ok, c = wait_counts(page, 24, 12)
        page.screenshot(path=shots / "2-open100-sheet0.png")
        print(f"OPEN100 sheet 0: {c} -> {'PASS' if ok else 'FAIL'} (want 24 live, 12 not connected)")
        if not ok:
            failures.append("sheet 0")

        # The same switch fault-demo.bat makes: tell the running replay to start fault 6.
        subprocess.run(["docker", "compose", "exec", "-T", "te-sim", "sh", "-c", "echo fault6 236 > /tmp/te-run"],
                       check=True)
        page.goto(f"{a.url}/data/perspective/client/PIDTwin")
        t0, red = time.time(), 0
        while time.time() - t0 < 120 and not red:
            red = page.locator(LABELS).evaluate_all(RED_JS)
            time.sleep(2)
        page.screenshot(path=shots / "3-fault6.png")
        pi = page.locator(LABELS).nth(7).inner_text() if page.locator(LABELS).count() > 7 else "?"
        print(f"fault 6: {red} red label(s) after {time.time() - t0:.0f} s (PI-107 shows {pi!r}) -> "
              f"{'PASS' if red else 'FAIL'}")
        if not red:
            failures.append("fault alarm")
        b.close()
    print("ALL PASS" if not failures else f"FAILED: {', '.join(failures)}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
