#!/usr/bin/env python3
"""Resolve place coordinates from OpenStreetMap, with provenance.

Why this exists as a separate step: the container this dataset was written in cannot reach
Nominatim (the environment's network policy blocks it), and typing in a coordinate from memory
produces a pin that looks right and lands on the wrong lane. So coordinates are left null and
filled here, by a machine, from a named OSM object — `osm:node/123456`. The validator refuses a
coordinate that has no such source, which makes the honest path the only path.

Run this anywhere with network access: your laptop, or CI.

    python3 tools/resolve_geo.py --dry-run     # show what would be queried
    python3 tools/resolve_geo.py               # resolve everything still unresolved
    python3 tools/resolve_geo.py --id dadar-flower-market
    python3 tools/resolve_geo.py --force       # re-resolve entries already done

Nominatim's usage policy requires an identifying User-Agent and at most one request per second.
Both are honoured below. Do not raise the rate; you will be blocked, and rightly.

After running, EVERY resolved pin needs a human to look at it. A geocoder happily returns the
neighbourhood centroid for a query it half-understands, and `precision: "area"` is the flag for
exactly that — the validator warns on it. Open the lat/lng on a map, confirm it is the building
and not the postcode, and only then treat the entry as map-ready.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACES = ROOT / "data" / "places.mumbai.json"

NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "MumbaiTripCompanion/0.1 (+https://github.com/rixscx/Mumbai) dataset-geocoding"
RATE_LIMIT_SECONDS = 1.1

# Greater Mumbai. Passed to Nominatim as a viewbox and re-checked on the way back, so a query
# that drifts to a same-named place in another city fails loudly instead of quietly.
VIEWBOX = (72.75, 19.35, 73.15, 18.85)  # left, top, right, bottom
BBOX_LAT = (18.85, 19.35)
BBOX_LNG = (72.75, 73.15)

# Nominatim's `type`/`class` mapped to how much we trust the pin. Anything not listed is
# treated as an area, which is the pessimistic assumption on purpose.
BUILDING_TYPES = {
    "restaurant", "cafe", "fast_food", "museum", "place_of_worship", "attraction",
    "marketplace", "bar", "pub", "bakery", "shop", "supermarket", "library",
    "theatre", "artwork", "monument", "memorial", "station", "building", "house",
}
STREET_TYPES = {"residential", "pedestrian", "footway", "road", "street", "path", "park",
                "garden", "recreation_ground"}


def query_nominatim(q: str) -> list[dict]:
    params = urllib.parse.urlencode({
        "q": q,
        "format": "jsonv2",
        "limit": "3",
        "addressdetails": "1",
        "viewbox": ",".join(str(v) for v in VIEWBOX),
        "bounded": "1",
    })
    req = urllib.request.Request(
        f"{NOMINATIM}?{params}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def classify(hit: dict) -> str:
    t, cls = hit.get("type", ""), hit.get("class", "")
    if t in BUILDING_TYPES or cls in ("amenity", "tourism", "shop", "historic"):
        return "building"
    if t in STREET_TYPES or cls in ("highway", "leisure"):
        return "street"
    return "area"


def resolve_one(place: dict, verbose: bool = True) -> bool:
    pid = place["id"]
    geo = place["geo"]
    q = geo["osm_query"]
    try:
        hits = query_nominatim(q)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        print(f"  {pid}: request failed ({exc}) — left unresolved", file=sys.stderr)
        geo["status"] = "failed"
        return False

    if not hits:
        print(f"  {pid}: no OSM match for {q!r} — left unresolved", file=sys.stderr)
        geo["status"] = "failed"
        return False

    hit = hits[0]
    lat, lng = float(hit["lat"]), float(hit["lon"])
    if not (BBOX_LAT[0] <= lat <= BBOX_LAT[1] and BBOX_LNG[0] <= lng <= BBOX_LNG[1]):
        print(f"  {pid}: match outside Mumbai ({lat},{lng}) — rejected", file=sys.stderr)
        geo["status"] = "failed"
        return False

    precision = classify(hit)
    geo.update({
        "status": "resolved",
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "source": f"osm:{hit['osm_type']}/{hit['osm_id']}",
        "resolved_at": date.today().isoformat(),
        "precision": precision,
    })
    if verbose:
        flag = "  <-- CHECK: centroid, not a building" if precision == "area" else ""
        print(f"  {pid}: {lat:.6f},{lng:.6f} {precision} "
              f"osm:{hit['osm_type']}/{hit['osm_id']}{flag}")
        print(f"      matched: {hit.get('display_name', '')[:110]}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print queries, change nothing")
    ap.add_argument("--force", action="store_true", help="re-resolve already-resolved entries")
    ap.add_argument("--id", action="append", help="restrict to these ids (repeatable)")
    args = ap.parse_args()

    doc = json.loads(PLACES.read_text())
    places = doc["places"]

    todo = [
        p for p in places
        if (args.force or p["geo"]["status"] != "resolved")
        and (not args.id or p["id"] in args.id)
    ]

    if not todo:
        print("nothing to resolve")
        return 0

    if args.dry_run:
        print(f"would query Nominatim for {len(todo)} entries "
              f"at {RATE_LIMIT_SECONDS}s intervals "
              f"(~{len(todo) * RATE_LIMIT_SECONDS:.0f}s):")
        for p in todo:
            print(f"  {p['id']:<32} {p['geo']['osm_query']}")
        return 0

    print(f"resolving {len(todo)} entries against OpenStreetMap "
          f"(~{len(todo) * RATE_LIMIT_SECONDS:.0f}s at the required 1 req/s):")
    resolved = 0
    for i, p in enumerate(todo):
        if i:
            time.sleep(RATE_LIMIT_SECONDS)
        if resolve_one(p):
            resolved += 1

    PLACES.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    failed = len(todo) - resolved
    areas = sum(1 for p in todo if p["geo"].get("precision") == "area")
    print(f"\nresolved {resolved}/{len(todo)}; {failed} failed")
    if areas:
        print(f"{areas} landed on an area centroid rather than a building — hand-check these "
              f"before trusting the map")
    print("Coordinates are now OSM-derived: the geo block is ODbL 1.0 and the attribution "
          "requirement applies.")
    print("Re-run tools/validate_places.py.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
