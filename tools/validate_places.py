#!/usr/bin/env python3
"""Validate data/places.mumbai.json.

This is the anti-fabrication gate. It runs in CI and fails the build, because "don't invent
opening hours" is a rule that only means something if a machine enforces it.

The checks that matter are the semantic ones, not the shape ones:

  * a coordinate may not exist without machine provenance (so a plausible-looking lat/lng that
    is 400 m off the right lane cannot be committed);
  * a claim-bearing field must be reachable from the sources array;
  * an entry must satisfy at least two of the brief's four "underrated" criteria, so a
    tourist-trap default cannot pass without someone lying in the data;
  * marketing adjectives are rejected, because "vibrant hidden gem" is not information;
  * pairs_with must reference entries that exist, or "build my day" silently drops stops.

Usage:
    python3 tools/validate_places.py            # validate, print a report, exit non-zero on error
    python3 tools/validate_places.py --quiet    # errors only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACES = ROOT / "data" / "places.mumbai.json"
SCHEMA = ROOT / "data" / "schema" / "place.schema.json"

# Greater Mumbai, generously bounded. A coordinate outside this is a resolver failure,
# not a place.
BBOX = {"lat": (18.85, 19.35), "lng": (72.75, 73.15)}

# Words that describe the writer's enthusiasm rather than the place. The brief bans
# "adjectives-as-substance"; this is that ban, made executable.
BANNED_WORDS = [
    "iconic", "vibrant", "hidden gem", "must-visit", "must visit", "bustling",
    "quaint", "charming", "nestled", "stunning", "breathtaking", "unforgettable",
    "picturesque", "eclectic", "vibe", "instagrammable", "world-class", "authentic",
    "a feast for the senses", "step back in time", "off the beaten path",
]

# Fields whose values are factual claims about the world. Each must appear in at least one
# source's `supports` list, or be explicitly marked unknown.
CLAIM_FIELDS = ["hours", "cost", "geo"]

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, place_id: str, msg: str) -> None:
        self.errors.append(f"{place_id}: {msg}")

    def warn(self, place_id: str, msg: str) -> None:
        self.warnings.append(f"{place_id}: {msg}")


def check_geo(p: dict, r: Report) -> None:
    """The core rule: no coordinate without provenance."""
    pid = p["id"]
    geo = p.get("geo", {})
    lat, lng = geo.get("lat"), geo.get("lng")
    has_coords = lat is not None or lng is not None

    if has_coords:
        if lat is None or lng is None:
            r.error(pid, "geo has one of lat/lng but not both")
        if not geo.get("source"):
            r.error(
                pid,
                "geo.lat/lng are set but geo.source is empty. A coordinate without OSM "
                "provenance is a fabricated address — run tools/resolve_geo.py instead of "
                "typing one in.",
            )
        if not geo.get("resolved_at"):
            r.error(pid, "geo.lat/lng are set but geo.resolved_at is empty")
        if geo.get("status") != "resolved":
            r.error(pid, f"geo.lat/lng are set but status is {geo.get('status')!r}")
        if geo.get("precision") is None:
            r.error(pid, "geo.lat/lng are set but precision is null")
        if lat is not None and not (BBOX["lat"][0] <= lat <= BBOX["lat"][1]):
            r.error(pid, f"geo.lat {lat} is outside Greater Mumbai")
        if lng is not None and not (BBOX["lng"][0] <= lng <= BBOX["lng"][1]):
            r.error(pid, f"geo.lng {lng} is outside Greater Mumbai")
        if geo.get("precision") == "area":
            r.warn(
                pid,
                "geo.precision is 'area' — the pin is a neighbourhood centroid, not the "
                "building. Needs hand-verification before the map is trustworthy.",
            )
    else:
        if geo.get("status") == "resolved":
            r.error(pid, "geo.status is 'resolved' but lat/lng are null")
        if not geo.get("osm_query"):
            r.error(pid, "geo has no coordinates and no osm_query — nothing can resolve it")


def check_hours(p: dict, r: Report) -> None:
    pid = p["id"]
    h = p.get("hours", {})
    if h.get("known"):
        if not h.get("windows") and not h.get("opens_at") and not h.get("always_open"):
            r.error(
                pid,
                "hours.known is true but there is neither a window nor an opens_at. Set "
                "known=false rather than implying hours you do not have.",
            )
        for w in h.get("windows", []):
            if w["open"] >= w["close"]:
                r.error(pid, f"hours window {w['open']}-{w['close']} does not advance")
        if h.get("closed_days") and not h.get("closed_days_verified"):
            r.warn(pid, "closed_days is populated but closed_days_verified is false")
        if not h.get("closed_days") and h.get("closed_days_verified") is False:
            r.warn(
                pid,
                "no known weekly closure and closed_days_verified is false — the app must "
                "not promise this is open every day",
            )
    else:
        if h.get("windows") or h.get("opens_at"):
            r.error(pid, "hours.known is false but hours data is present — contradictory")
        if not h.get("note"):
            r.error(pid, "hours.known is false with no note explaining what is unknown")


def check_cost(p: dict, r: Report) -> None:
    pid = p["id"]
    c = p.get("cost", {})
    avg, band = c.get("avg_paise"), c.get("band")
    if avg is None and band != "unknown":
        r.error(pid, f"cost.avg_paise is null but band is {band!r}; band must be 'unknown'")
    if avg is not None:
        if isinstance(avg, bool) or not isinstance(avg, int):
            r.error(pid, "cost.avg_paise must be an integer number of paise, never a float")
        if avg == 0 and band != "free":
            r.error(pid, "cost.avg_paise is 0 but band is not 'free'")
        if avg > 0 and band == "free":
            r.error(pid, "band is 'free' but avg_paise is non-zero")


def check_prose(p: dict, r: Report) -> None:
    pid = p["id"]
    blob = " ".join(
        [p.get("what_it_is", ""), p.get("why_locals_rate_it", "")]
        + p.get("insider_rules", [])
    ).lower()
    for word in BANNED_WORDS:
        if word in blob:
            r.error(
                pid,
                f"prose contains banned marketing word {word!r} — say what the place is, "
                "not how it makes you feel",
            )
    what = p.get("what_it_is", "")
    if len(what) > 240:
        r.error(pid, f"what_it_is is {len(what)} chars, over the 240 limit")


def check_sources(p: dict, r: Report) -> None:
    pid = p["id"]
    sources = p.get("sources", [])
    if not sources:
        r.error(pid, "no sources. Every entry must be traceable.")
        return

    supported: set[str] = set()
    for s in sources:
        supported.update(s.get("supports", []))
        if not s.get("url", "").startswith(("http://", "https://")):
            r.error(pid, f"source url {s.get('url')!r} is not a URL")

    # A claim field must either be sourced or be explicitly unknown.
    for field in CLAIM_FIELDS:
        sourced = any(sup == field or sup.startswith(field + ".") for sup in supported)
        if sourced:
            continue
        if field == "hours" and not p.get("hours", {}).get("known"):
            continue
        if field == "hours" and p.get("hours", {}).get("always_open"):
            continue  # a public street has no opening hour to cite
        if field == "cost" and p.get("cost", {}).get("band") == "unknown":
            continue
        if field == "cost" and p.get("cost", {}).get("band") == "free":
            continue  # "it costs nothing to walk down a public street" needs no citation
        if field == "geo":
            continue  # provenance is enforced by check_geo, not by an editorial source
        r.error(
            pid,
            f"field {field!r} carries a claim but no source lists it in `supports`",
        )

    if p.get("confidence") in ("medium", "low") and not p.get("confidence_note"):
        r.error(pid, f"confidence is {p['confidence']!r} with no confidence_note")


def check_underrated(p: dict, r: Report) -> None:
    basis = p.get("underrated_basis", [])
    if len(set(basis)) < 2:
        r.error(
            p["id"],
            "fewer than two distinct underrated_basis values — the brief's filter requires "
            "at least two to hold, so this entry does not qualify",
        )


def check_season(p: dict, r: Report) -> None:
    pid = p["id"]
    months = p.get("season", {}).get("months", [])
    if not months:
        r.error(pid, "season.months is empty")
    if len(months) != len(set(months)):
        r.error(pid, "season.months has duplicates")
    if p.get("monsoon_safe") == "no" and set(range(6, 10)).issubset(set(months)):
        r.warn(
            pid,
            "monsoon_safe is 'no' but season.months includes all of Jun-Sep — one of the two "
            "is wrong",
        )


def check_dates(p: dict, r: Report) -> None:
    pid = p["id"]
    today = date.today()
    try:
        reviewed = date.fromisoformat(p["last_reviewed"])
        if reviewed > today:
            r.error(pid, f"last_reviewed {reviewed} is in the future")
    except (KeyError, ValueError):
        r.error(pid, "last_reviewed is missing or not an ISO date")
    for s in p.get("sources", []):
        try:
            if date.fromisoformat(s["retrieved"]) > today:
                r.error(pid, f"source retrieved date {s['retrieved']} is in the future")
        except (KeyError, ValueError):
            r.error(pid, f"source {s.get('url')} has a missing or malformed retrieved date")


def check_required(p: dict, schema: dict, r: Report) -> None:
    pid = p.get("id", "<no id>")
    for field in schema.get("required", []):
        if field not in p:
            r.error(pid, f"missing required field {field!r}")
    allowed = set(schema.get("properties", {}))
    for field in p:
        if field not in allowed:
            r.error(pid, f"unknown field {field!r} (schema forbids additional properties)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    schema = json.loads(SCHEMA.read_text())
    doc = json.loads(PLACES.read_text())
    places = doc["places"]
    r = Report()

    ids = [p.get("id") for p in places]
    for dup, n in Counter(ids).items():
        if n > 1:
            r.errors.append(f"duplicate id {dup!r} appears {n} times")

    id_set = set(ids)
    slug = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

    for p in places:
        pid = p.get("id", "<no id>")
        if not slug.match(pid):
            r.error(pid, "id is not a lowercase slug")
        check_required(p, schema, r)
        check_geo(p, r)
        check_hours(p, r)
        check_cost(p, r)
        check_prose(p, r)
        check_sources(p, r)
        check_underrated(p, r)
        check_season(p, r)
        check_dates(p, r)
        for ref in p.get("pairs_with", []):
            if ref not in id_set:
                r.error(pid, f"pairs_with references unknown id {ref!r}")
            if ref == pid:
                r.error(pid, "pairs_with references itself")

    # ---- report ----
    by_cluster: dict[str, list[dict]] = defaultdict(list)
    for p in places:
        by_cluster[p.get("cluster", "?")].append(p)
    conf = Counter(p.get("confidence") for p in places)
    unresolved = sum(1 for p in places if p.get("geo", {}).get("status") != "resolved")
    hours_unknown = sum(1 for p in places if not p.get("hours", {}).get("known"))
    cost_unknown = sum(1 for p in places if p.get("cost", {}).get("avg_paise") is None)

    if not args.quiet:
        print(f"places: {len(places)} across {len(by_cluster)} clusters")
        for cluster in sorted(by_cluster):
            entries = by_cluster[cluster]
            c = Counter(e.get("confidence") for e in entries)
            print(
                f"  {cluster:<28} {len(entries):>3}  "
                f"high={c['high']} med={c['medium']} low={c['low']}"
            )
        print(
            f"confidence: high={conf['high']} medium={conf['medium']} low={conf['low']}"
        )
        print(f"geo unresolved: {unresolved}/{len(places)} (run tools/resolve_geo.py)")
        print(f"hours unknown:  {hours_unknown}/{len(places)}")
        print(f"cost unknown:   {cost_unknown}/{len(places)}")

    for w in r.warnings:
        print(f"WARN  {w}", file=sys.stderr)
    for e in r.errors:
        print(f"ERROR {e}", file=sys.stderr)

    if r.errors:
        print(f"\nFAILED: {len(r.errors)} error(s)", file=sys.stderr)
        return 1
    print(f"\nOK: {len(places)} entries valid, {len(r.warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
