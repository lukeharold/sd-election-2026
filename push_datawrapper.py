#!/usr/bin/env python3
"""Create (first run) or update (every later run) the 10 Datawrapper maps from output/.

New maps are copied from BASE_CHART, which holds the uploaded precinct file.
Chart IDs are saved to datawrapper_charts.json so embed links never change.
Maps stay as drafts unless --publish is passed.

Needs DATAWRAPPER_TOKEN in the environment, or the token in ~/.datawrapper_token_sd.

    python3 push_datawrapper.py --as-of "Nov. 4, 2:51 a.m."
    python3 push_datawrapper.py --as-of "Nov. 4, 2:51 a.m." --publish
"""
import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
IDS_FILE = ROOT / "datawrapper_charts.json"
API = "https://api.datawrapper.de/v3"
BASE_CHART = "KuqHL"
SOURCE_URL = "https://www.livevoterturnout.com/ENR/sandiegocaenr/25/en/Index_25.html"

# Each scale runs dark, pale, pale, dark so the color changes sharply at a zero margin.
RED_BLUE = ["#c0152a", "#f5a8b0", "#a8c8f0", "#0a4fa6"]  # same as the June maps
TEAL_AMBER = ["#0f5e57", "#a8dcd4", "#f7d58a", "#b87900"]  # No is teal, Yes is amber

# slug: (title, scale, positive option, negative option, color of each, is it a partial district)
MAPS = {
    "governor": ("Governor", RED_BLUE, "Xavier Becerra", "Steve Hilton", "blue", "red", False),
    "prop_39": ("Prop 39: voting ID requirements", TEAL_AMBER, "Yes", "No", "amber", "teal", False),
    "prop_40": ("Prop 40: the billionaire tax", TEAL_AMBER, "Yes", "No", "amber", "teal", False),
    "prop_41": ("Prop 41: making it harder to pass new special taxes", TEAL_AMBER, "Yes", "No", "amber", "teal", False),
    "prop_42": ("Prop 42: prevents new statewide personal property taxes", TEAL_AMBER, "Yes", "No", "amber", "teal", False),
    "house_48": ("48th congressional district", RED_BLUE, "Marni Von Wilpert", "Jim Desmond", "blue", "red", True),
    "house_49": ("49th congressional district", RED_BLUE, "Mike Levin", "Armen Kurdian", "blue", "red", True),
    "house_50": ("50th congressional district", RED_BLUE, "Scott Peters", "Steve Cohen", "blue", "red", False),
    "house_51": ("51st congressional district", RED_BLUE, "Sara Jacobs", "Ricardo Cabrera", "blue", "red", False),
    "house_52": ("52nd congressional district", RED_BLUE, "Juan Vargas", "Jeff Belle", "blue", "red", False),
}


def read_token():
    token = os.environ.get("DATAWRAPPER_TOKEN")
    return (token or Path("~/.datawrapper_token_sd").expanduser().read_text()).strip()


TOKEN = read_token()


def call(method, path, body=None, content_type="application/json"):
    data = None
    if body is not None:
        data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
    request = urllib.request.Request(API + path, data=data, method=method)
    request.add_header("Authorization", f"Bearer {TOKEN}")
    if data is not None:
        request.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(request) as response:
            text = response.read().decode()
    except urllib.error.HTTPError as error:
        raise SystemExit(f"{method} {path} failed: {error.code} {error.read().decode()[:400]}")
    return json.loads(text) if text else None


def intro(slug, totals):
    """The contest's totals, leader first, so they match the Registrar's figures."""
    votes = sum(totals.values())
    parts = [f"{name.title()}: {count:,} ({100 * count / votes:.1f}%)" for name, count in totals.items()]
    results = f"{', '.join(parts)}."
    if MAPS[slug][6]:
        return f"San Diego County portion only. {results}"
    return f"San Diego County results. {results}" if slug.startswith("prop") else results


def notes(slug, as_of, outstanding):
    """The ballots sentence drops out if the Registrar's file stops giving a count."""
    if slug.startswith("house"):
        ballots = f" There are about {outstanding:,} ballots outstanding countywide." if outstanding is not None else ""
        return (
            f"Unofficial results as of {as_of.rstrip('.')}., according to the San Diego County Registrar of Voters."
            f"{ballots}"
        )
    ballots = f" The Registrar projects about {outstanding:,} ballots outstanding countywide." if outstanding is not None else ""
    return f"Unofficial results as of {as_of.rstrip('.')}.{ballots}"


def legend(slug):
    """Prop maps label the legend No to Yes. The House maps have no legend."""
    if slug.startswith("prop"):
        return {"enabled": True, "labels": "custom", "labelMin": "No", "labelCenter": "", "labelMax": "Yes"}
    return {"enabled": not slug.startswith("house")}


def settings(slug, summary, as_of):
    title, scale, *_ = MAPS[slug]
    # City labels on the prop maps are set in Datawrapper. PATCH leaves them in place.
    custom_stops = [None, 0, None, 20, 60, None, "", "", ""] if slug.startswith("prop") else [None, 0, None, "", "", "", "", "", ""]
    return {
        "title": title,
        "metadata": {
            "axes": {"keys": "CONSNUM", "labels": "Precinct_Name", "values": "margin"},
            "data": {"column-format": {
                "CONSNUM": {"type": "text"}, "Precinct_Name": {"type": "text"}, "margin": {"type": "number"},
                "place_1": {"type": "text"}, "place_2": {"type": "text"},
                "total_votes": {"type": "number"}, "turnout": {"type": "text"},
            }},
            "describe": {
                "intro": intro(slug, summary["maps"][slug]["totals"]),
                "source-name": "San Diego County Registrar of Voters",
                "source-url": SOURCE_URL,
                "byline": "Luke Harold",
            },
            "annotate": {"notes": notes(slug, as_of, summary["outstanding_ballots"])},
            "visualize": {
                "map-key-attr": "CONSNUM",
                "map-key-column": "CONSNUM",
                "chart-type-set": True,
                "hide-empty-regions": True,
                "mapView": "crop",
                "zoomable": True,
                "legends": {"color": legend(slug)},
                "tooltip": {
                    "title": "{{ precinct_name }}",
                    "body": "Precinct {{ consnum }}<br>{{ place_1 }}<br>{{ place_2 }}<br>Turnout: {{ turnout }}",
                    "sticky": True,
                    "enabled": True,
                },
                "colorscale": {
                    "mode": "continuous",
                    "type": "diverging",
                    "stops": "equidistant",
                    "colors": [
                        {"color": scale[0], "position": 0},
                        {"color": scale[1], "position": 0.5},
                        {"color": scale[2], "position": 0.5},
                        {"color": scale[3], "position": 1},
                    ],
                    "column": "margin",
                    "rangeMin": -100,
                    "rangeCenter": 0,
                    "rangeMax": 100,
                    "customStops": custom_stops,
                },
            },
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", required=True, help='time of the results post, like "Nov. 4, 2:51 a.m."')
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()

    summary = json.loads((OUTPUT / "summary.json").read_text())
    ids = json.loads(IDS_FILE.read_text()) if IDS_FILE.exists() else {}

    for slug in MAPS:
        if slug not in ids:
            ids[slug] = call("POST", f"/charts/{BASE_CHART}/copy")["id"]
            IDS_FILE.write_text(json.dumps(ids, indent=2) + "\n")
        chart = ids[slug]
        call("PUT", f"/charts/{chart}/data", (OUTPUT / f"{slug}.csv").read_text(), "text/csv")
        call("PATCH", f"/charts/{chart}", settings(slug, summary, args.as_of))
        if args.publish:
            call("POST", f"/charts/{chart}/publish")
        print(f"{'published' if args.publish else 'updated draft'} {slug}: {chart}")


if __name__ == "__main__":
    main()
