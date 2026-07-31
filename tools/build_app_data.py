#!/usr/bin/env python3
"""Generate the installable web app's static assets, and the Android module's assets.

The app in web/ is hand-written source, not generated — only its *data* and its icons come from
here, plus the service-worker cache version, which has to change whenever a precached file changes
or phones will serve a stale app forever.

  web/places.json   the curated dataset, stripped to the fields the UI actually reads
  web/trip.json     trip dates, the itinerary, the seed category tree, the two real ticket fares
  web/icons/*.png   written with a minimal PNG encoder (no Pillow in this container)
  web/sw.js         CACHE version line rewritten from a hash of the precached files

Nothing here invents data. The two ticket fares are the real ones off the IRCTC slips and they are
offered to the user as an optional import rather than seeded silently, because the user asked for
nothing hardcoded — they can decline them, edit them, or delete them.

Usage:
    python3 tools/build_app_data.py
    python3 tools/build_app_data.py --check    # fail if anything is stale (for CI)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACES_SRC = ROOT / "data" / "places.mumbai.json"
FARES_SRC = ROOT / "data" / "fares.mumbai.json"
WEB = ROOT / "web"
ANDROID_ASSETS = ROOT / "android" / "src" / "main" / "assets"

# Fields the UI reads. Everything else in the entry (underrated_basis, diet flags we don't surface
# yet) is dropped to keep the payload small — this is the whole dataset on a phone, over a hotel
# wifi, so it is worth being deliberate about.
KEEP = [
    "id", "name", "name_local", "cluster", "type", "geo", "what_it_is", "why_locals_rate_it",
    "insider_rules", "hours", "season", "cost", "duration_minutes", "how_to_get_there",
    "monsoon_safe", "monsoon_note", "diet", "safety_notes", "accessibility", "toilet_nearby",
    "photography_allowed", "reservation_needed", "crowd_level_by_time", "pairs_with",
    "confidence", "confidence_note", "sources", "last_reviewed",
]

DAYS = [
    ("2026-08-10", "Mon 10 Aug", "Arrive Dadar 05:45"),
    ("2026-08-11", "Tue 11 Aug", "Fort & Kala Ghoda"),
    ("2026-08-12", "Wed 12 Aug", "Novena, then Aarey"),
    ("2026-08-13", "Thu 13 Aug", "Kanheri Caves"),
    ("2026-08-14", "Fri 14 Aug", "Girgaon & Malabar Hill"),
    ("2026-08-15", "Sat 15 Aug", "Independence Day + Pateti"),
    ("2026-08-16", "Sun 16 Aug", "Navroz — last real day"),
]

# Mirrors docs/ITINERARY.md, which stays authoritative.
PLAN = {
    "2026-08-10": [
        ["06:00", "dadar-flower-market", "Only morning you are guaranteed to be here in time."],
        ["07:00", "asthika-samaj-matunga", "Open from 05:00."],
        ["07:30", "ram-ashraya-matunga", "Order idli, not dosa — full menu not until ~06:30."],
        ["14:00", "bhau-daji-lad-museum", "Closed Wednesdays, so today is the day for it."],
        ["18:00", "shivaji-park-dadar", "Sit on the katta rather than walking laps."],
    ],
    "2026-08-11": [
        ["07:15", "yazdani-bakery-fort", "Opens 07:00. Brun is hard-crusted on purpose: dunk it."],
        ["10:15", "csmvs-kala-ghoda", "Upper galleries first. Confirm the ₹200 fee at the counter."],
        ["13:00", "ideal-corner-fort", "Tuesday specials are the reason to come."],
        ["15:00", "david-sassoon-library-kala-ghoda", "Hours unverified — opportunistic."],
        ["17:30", "marine-drive-promenade", "Stay behind the railing and off the tetrapods."],
        ["19:00", "kyani-and-co-marine-lines", "Chai and bun maska together."],
    ],
    "2026-08-12": [
        ["06:00", "st-michaels-church-mahim", "Wednesday is the entire point. Take the 06:00 slot."],
        ["08:30", "aarey-picnic-point", "August is the point here. Keep to roads and garden."],
        ["17:30", "ghatkopar-khau-galli", "Nothing before ~16:30. Metro-1 east from Andheri."],
    ],
    "2026-08-13": [
        ["07:30", "kanheri-caves-sgnp", "Gate fee and cave ticket are separate."],
        ["19:00", "cafe-madras-matunga", "Open today — the Monday problem does not apply."],
    ],
    "2026-08-14": [
        ["09:30", "khotachiwadi-girgaon", "Somebody's street, not a site. Ask before photographing."],
        ["11:00", "banganga-tank-walkeshwar", "Tank is open ground; temple hours conflict."],
        ["13:00", "britannia-and-co-fort", "Lunch only, cash only. Deliberately before Navroz."],
        ["17:00", "marine-drive-promenade", "Worth timing to a high tide — table not yet sourced."],
    ],
    "2026-08-15": [
        ["09:30", "ranwar-village-bandra", "North of the likely Independence Day restrictions."],
        ["14:00", "nehru-science-centre-worli", "Open every day of the year, holidays included."],
        ["15:00", "nehru-planetarium-worli", "Separate ticket. 15:00 is the English show."],
    ],
    "2026-08-16": [
        ["05:00", "sassoon-dock-colaba", "Peak 03:30–07:30. Fishing ban may thin landings."],
        ["11:00", "chor-bazaar-mutton-street", "Close at 35–45% of the first quote on antiques."],
        ["15:00", "sewri-fort", "Free and unstaffed. No flamingos in August."],
        ["19:00", "five-gardens-matunga", "A last easy evening before packing."],
    ],
}

# Seed taxonomy only. The user can add, rename and delete nodes at runtime; deleting reparents
# children and reassigns expenses to the parent, per ADR-004. Depth 3 here on purpose — the brief's
# own example (Travel ▸ Local ▸ Suburban train) already needs it, which is why the cap was dropped.
CATEGORIES = [
    ("food", None, "Food & Drink"),
    ("food-breakfast", "food", "Breakfast"),
    ("food-street", "food", "Street food"),
    ("food-restaurant", "food", "Restaurant"),
    ("food-chai", "food", "Chai & snacks"),
    ("travel", None, "Travel"),
    ("travel-local", "travel", "Local"),
    ("travel-local-train", "travel-local", "Suburban train"),
    ("travel-local-auto", "travel-local", "Auto rickshaw"),
    ("travel-local-taxi", "travel-local", "Kaali-peeli / cab"),
    ("travel-local-bus", "travel-local", "BEST bus"),
    ("travel-local-metro", "travel-local", "Metro"),
    ("travel-long", "travel", "Long distance"),
    ("travel-long-train", "travel-long", "Intercity train"),
    ("stay", None, "Stay"),
    ("entry", None, "Entry & tickets"),
    ("shopping", None, "Shopping"),
    ("other", None, "Other"),
]

# The only two expenses that exist, off the IRCTC slips (docs/TRIP.md). Offered as an import.
SEED_EXPENSES = [
    {"date": "2026-08-09", "paise": 76800, "categoryId": "travel-long-train",
     "note": "11036 Sharavati Express · Mysuru → Dadar · PNR 4762122976 · RAC/18", "method": "upi"},
    {"date": "2026-08-17", "paise": 74300, "categoryId": "travel-long-train",
     "note": "11301 Udyan Express · CSMT → Bengaluru · PNR 8751562744 · RAC/5", "method": "upi"},
]


# ---------------------------------------------------------------- PNG


def png(path: Path, size: int, pad: float) -> None:
    """Write the app mark: a warm-black field with the ochre taxi roofline across it.

    Hand-rolled because there is no Pillow here. PNG is just zlib-compressed scanlines with
    CRC-checked chunks, so a solid-colour mark is a few lines rather than a dependency.
    `pad` is the maskable safe-zone inset — Android crops maskable icons to a circle.
    """
    ink, ochre, plate = (0x17, 0x15, 0x0F), (0xD9, 0xA2, 0x1B), (0xF2, 0xF3, 0xF1)
    inset = int(size * pad)
    band_top, band_h = int(size * 0.40), max(1, int(size * 0.13))
    body_top = band_top + band_h + max(1, int(size * 0.045))
    body_h = int(size * 0.20)

    rows = bytearray()
    for y in range(size):
        rows.append(0)  # filter type 0
        for x in range(size):
            c = ink
            if inset <= x < size - inset:
                if band_top <= y < band_top + band_h:
                    c = ochre
                elif body_top <= y < body_top + body_h and x < size - inset - int(size * 0.30):
                    c = plate
            rows.extend(c)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8-bit truecolour
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
                     + chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b""))


# ---------------------------------------------------------------- data


def build_places() -> dict:
    doc = json.loads(PLACES_SRC.read_text())
    out = []
    for p in doc["places"]:
        out.append({k: p[k] for k in KEEP if k in p})
    return {
        "version": doc.get("version", 1),
        "generated": doc.get("generated", ""),
        "licence": doc.get("licence", {}),
        "places": out,
    }


def build_trip() -> dict:
    return {
        "city": "Mumbai",
        "tz": "Asia/Kolkata",
        "start": "2026-08-10",
        "end": "2026-08-16",
        "days": [{"date": d, "label": l, "theme": t} for d, l, t in DAYS],
        "plan": PLAN,
        "categories": [{"id": i, "parentId": p, "name": n} for i, p, n in CATEGORIES],
        "seedExpenses": SEED_EXPENSES,
        "fares": json.loads(FARES_SRC.read_text()),
    }


PRECACHE = ["index.html", "app.css", "app.js", "places.json", "trip.json",
            "manifest.webmanifest", "icons/icon-192.png", "icons/icon-512.png",
            "icons/maskable-512.png"]


def stamp_sw() -> str:
    """Rewrite sw.js's CACHE constant from a hash of everything it precaches.

    Without this a phone keeps the first version it ever installed. This is the whole reason the
    service worker is generated rather than hand-maintained.
    """
    h = hashlib.sha256()
    for name in PRECACHE:
        f = WEB / name
        h.update(name.encode())
        h.update(f.read_bytes() if f.exists() else b"")
    ver = h.hexdigest()[:12]

    sw = WEB / "sw.js"
    lines = sw.read_text().splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("const CACHE ="):
            lines[i] = f'const CACHE = "mumbai-{ver}";\n'
            break
    else:
        raise SystemExit("sw.js has no `const CACHE =` line to stamp")
    sw.write_text("".join(lines))
    return ver


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    ids = {p["id"] for p in json.loads(PLACES_SRC.read_text())["places"]}
    missing = {s[1] for stops in PLAN.values() for s in stops} - ids
    if missing:
        print(f"ERROR itinerary references unknown ids: {sorted(missing)}", file=sys.stderr)
        return 1
    cat_ids = {c[0] for c in CATEGORIES}
    bad_parents = {c[1] for c in CATEGORIES if c[1] and c[1] not in cat_ids}
    if bad_parents:
        print(f"ERROR categories have unknown parents: {sorted(bad_parents)}", file=sys.stderr)
        return 1
    bad_cats = {e["categoryId"] for e in SEED_EXPENSES} - cat_ids
    if bad_cats:
        print(f"ERROR seed expenses use unknown categories: {sorted(bad_cats)}", file=sys.stderr)
        return 1

    places_json = json.dumps(build_places(), ensure_ascii=False, separators=(",", ":")) + "\n"
    targets = {
        WEB / "places.json": places_json,
        # The Android module reads the same bytes from assets, so the two front-ends can never
        # drift apart on what the dataset says.
        ANDROID_ASSETS / "places.json": places_json,
        WEB / "trip.json": json.dumps(build_trip(), ensure_ascii=False, separators=(",", ":")) + "\n",
    }

    if args.check:
        stale = [p.name for p, c in targets.items() if not p.exists() or p.read_text() != c]
        if stale:
            print(f"stale: {stale} — run tools/build_app_data.py", file=sys.stderr)
            return 1
        print("app data up to date")
        return 0

    WEB.mkdir(parents=True, exist_ok=True)
    for path, content in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        print(f"wrote {path.relative_to(ROOT)} ({len(content):,} bytes)")

    png(WEB / "icons" / "icon-192.png", 192, 0.14)
    png(WEB / "icons" / "icon-512.png", 512, 0.14)
    png(WEB / "icons" / "maskable-512.png", 512, 0.22)
    print("wrote 3 icons")

    if (WEB / "sw.js").exists():
        print(f"stamped sw.js cache version: mumbai-{stamp_sw()}")
    else:
        print("note: web/sw.js not present yet, skipped version stamp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
