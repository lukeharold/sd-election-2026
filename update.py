#!/usr/bin/env python3
"""Check for a new Registrar post. If there is one, rebuild and republish the maps.

    python3 update.py              # publish only when the file has changed
    python3 update.py --dry-run    # download and check, but publish and save nothing

The last post's time and vote totals are kept in state/last_post.json. It is
only saved after publishing succeeds, so a failed run is retried on the next one.
"""
import argparse
import json
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state" / "last_post.json"
SUMMARY = ROOT / "output" / "summary.json"
RESULTS_URL = "https://www.livevoterturnout.com/ENR/sandiegocaenr/25/Precincts_25.csv"
HEADERS = {"User-Agent": "sd-election-maps"}
SMALLEST_REAL_FILE = 1_000_000  # bytes; a blocked or partial download is much smaller
LARGEST_ALLOWED_DROP = 0.01  # a contest's total can fall by 1% before the run stops

MONTHS = ["Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."]


def as_of_text(last_modified):
    """Turn the file's timestamp into wording like "Nov. 4, 2:51 a.m." in Pacific time."""
    when = parsedate_to_datetime(last_modified).astimezone(ZoneInfo("America/Los_Angeles"))
    hour = when.hour % 12 or 12
    period = "a.m." if when.hour < 12 else "p.m."
    return f"{MONTHS[when.month - 1]} {when.day}, {hour}:{when.minute:02d} {period}"


def remote_timestamp():
    request = urllib.request.Request(RESULTS_URL, method="HEAD", headers=HEADERS)
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.headers["Last-Modified"]


def download(path):
    """Save the results file and return the timestamp of the copy we actually got."""
    request = urllib.request.Request(RESULTS_URL, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=300) as response:
        path.write_bytes(response.read())
        last_modified = response.headers["Last-Modified"]
    if path.stat().st_size < SMALLEST_REAL_FILE:
        raise SystemExit(f"Download is only {path.stat().st_size:,} bytes, so it isn't the results file.")
    return last_modified


def contest_totals():
    maps = json.loads(SUMMARY.read_text())["maps"]
    return {slug: sum(info["totals"].values()) for slug, info in maps.items()}


def check_totals(previous, current):
    """Stop if a contest lost votes beyond a small correction, or if a contest went missing."""
    for slug, before in previous.items():
        after = current.get(slug, 0)
        if after < before * (1 - LARGEST_ALLOWED_DROP):
            raise SystemExit(f"{slug} fell from {before:,} votes to {after:,}. Stopping so the live maps stay as they are.")


def run(*args):
    subprocess.run([sys.executable, *map(str, args)], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    state = json.loads(STATE.read_text())
    if remote_timestamp() == state["last_modified"] and not args.dry_run:
        print(f"No new post since {state['last_modified']}.")
        return

    with tempfile.TemporaryDirectory() as folder:
        results = Path(folder) / "Precincts_25.csv"
        last_modified = download(results)
        print(f"Downloaded {results.stat().st_size:,} bytes, posted {last_modified}")
        run(ROOT / "build_maps.py", results)

    totals = contest_totals()
    check_totals(state["totals"], totals)
    as_of = as_of_text(last_modified)
    print(f"Checks passed. Results as of {as_of}: {totals}")

    if args.dry_run:
        print("Dry run: nothing published or saved.")
        return

    run(ROOT / "push_datawrapper.py", "--as-of", as_of, "--publish")
    STATE.write_text(json.dumps({"last_modified": last_modified, "as_of": as_of, "totals": totals}, indent=2) + "\n")


if __name__ == "__main__":
    main()
