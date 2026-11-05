#!/usr/bin/env python3
"""Turn the San Diego Registrar's by-precinct results file into one CSV per Datawrapper map.

Usage: python3 build_maps.py path/to/Precincts_25.csv

Margin is percentage points of the votes in that precinct: positive means the
"positive" option below is ahead. Precincts with no votes are left out so that
Datawrapper hides them.
"""
import collections
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOUNDARIES = ROOT / "boundaries" / "sd_precincts_2026_11_03.json"
OUTPUT = ROOT / "output"

HOUSE = "UNITED STATES REPRESENTATIVE "

# slug, contest name in the results file, option counted as a positive margin.
# The House direction follows the June maps.
MAPS = [
    ("governor", "GOVERNOR", "XAVIER BECERRA"),
    ("prop_39", "PROP 39 - REQUIRES GOVERNMENT IDENTIFICATION TO VOTE", "YES"),
    ("prop_40", "PROP 40 - IMPOSES ONE-TIME TAX ON CERTAIN TAXPAYERS", "YES"),
    ("prop_41", "PROP 41 - PROHIBITS NEW STATE TAXES THAT EXCLUDE REVENUES FROM STATE SPENDING LIMIT", "YES"),
    ("prop_42", "PROP 42 - PROHIBITS NEW STATE PERSONAL PROPERTY TAXES", "YES"),
    ("house_48", HOUSE + "48TH DISTRICT (SAN DIEGO PORTION ONLY)", "MARNI VON WILPERT"),
    ("house_49", HOUSE + "49TH DISTRICT (SAN DIEGO PORTION ONLY)", "MIKE LEVIN"),
    ("house_50", HOUSE + "50TH DISTRICT", "SCOTT PETERS"),
    ("house_51", HOUSE + "51ST DISTRICT", "SARA JACOBS"),
    ("house_52", HOUSE + "52ND DISTRICT", "JUAN VARGAS"),
]

COLUMNS = ["CONSNUM", "Precinct_Name", "margin", "place_1", "place_2", "total_votes", "turnout"]


def read_results(path):
    """Return the banner line and the result rows. The first two lines aren't part of the table."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        banner = f.readline().strip()
        f.readline()
        return banner, list(csv.DictReader(f))


def outstanding_ballots(banner):
    match = re.search(r"OUTSTANDING BALLOTS:\s*([\d,]+)", banner)
    return int(match.group(1).replace(",", "")) if match else None


def boundary_ids():
    features = json.loads(BOUNDARIES.read_text())["features"]
    return {f["properties"]["CONSNUM"] for f in features}


def display_name(option):
    return option.title()


def build_map(rows, contest, positive, known_ids):
    """Return the CSV rows and the summary for one contest."""
    votes = collections.defaultdict(dict)
    turnout = {}
    for row in rows:
        if row["Contest Name"] == contest:
            precinct = row["Precinct"]
            votes[precinct][row["Candidate Name"]] = int(row["Votes"].replace(",", ""))
            turnout[precinct] = row["Voter Turnout"]
    if not votes:
        raise SystemExit(f"Contest not found in results: {contest}")

    options = {option for counts in votes.values() for option in counts}
    if len(options) != 2 or positive not in options:
        raise SystemExit(f"Unexpected options for {contest}: {sorted(options)}")

    output = []
    totals = collections.Counter()
    mapped = collections.Counter()
    hidden = 0
    for precinct, counts in votes.items():
        totals.update(counts)
        # VBM-AV rows have no shape on the map, so they only count toward the totals.
        if "VBM-AV" in precinct:
            continue
        _, consnum, name = precinct.split("-", 2)
        consnum = int(consnum)
        if consnum not in known_ids:
            raise SystemExit(f"Precinct is not in the boundary file: {precinct}")
        mapped.update(counts)
        total = sum(counts.values())
        if total == 0:
            hidden += 1
            continue
        negative = (options - {positive}).pop()
        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        output.append({
            "CONSNUM": consnum,
            "Precinct_Name": name,
            "margin": round(100 * (counts[positive] - counts[negative]) / total, 1),
            "place_1": f"{display_name(ranked[0][0])}: {ranked[0][1]:,} votes",
            "place_2": f"{display_name(ranked[1][0])}: {ranked[1][1]:,} votes",
            "total_votes": total,
            "turnout": turnout[precinct],
        })

    output.sort(key=lambda row: row["CONSNUM"])
    summary = {
        "contest": contest,
        "totals": dict(totals.most_common()),
        "on_map": dict(mapped.most_common()),
        "precincts_shown": len(output),
        "precincts_hidden_no_votes": hidden,
    }
    return output, summary


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    banner, rows = read_results(sys.argv[1])
    known_ids = boundary_ids()
    OUTPUT.mkdir(exist_ok=True)

    summary = {"banner": banner, "outstanding_ballots": outstanding_ballots(banner), "maps": {}}
    for slug, contest, positive in MAPS:
        output, summary["maps"][slug] = build_map(rows, contest, positive, known_ids)
        with open(OUTPUT / f"{slug}.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(output)
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
