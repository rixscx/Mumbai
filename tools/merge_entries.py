#!/usr/bin/env python3
"""Merge researched place entries into data/places.mumbai.json.

The dataset is built in passes, by several researchers working on disjoint clusters at the same
time. That parallelism has two predictable failure modes, and this tool exists to make both of
them loud rather than silent:

  * **Duplicate ids.** Two researchers writing up the same place under different slugs, or the
    same slug twice. A duplicate id is fatal — `place_visits` rows will reference it, so an id
    collision is a data-corruption bug waiting for a user.
  * **Dangling `pairs_with`.** A researcher can only see their own file, so a reference to an
    entry in someone else's file cannot be checked at write time. The validator rejects these,
    and "build my day" silently drops stops if they survive. With --prune-dangling they are
    removed and every removal is printed, because a quietly dropped reference is the thing that
    makes an itinerary feature look broken for no visible reason.

Nothing here invents or edits a field. It is a merge and a referential-integrity check; the
anti-fabrication rules live in tools/validate_places.py, which should be run straight after.

Usage:
    python3 tools/merge_entries.py NEW.json [NEW2.json ...]
    python3 tools/merge_entries.py --prune-dangling --dry-run NEW.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACES = ROOT / "data" / "places.mumbai.json"


def load_array(path: Path) -> list[dict]:
    """Read a researcher's output file, which is a bare JSON array of entries."""
    with path.open() as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        sys.exit(f"{path}: expected a JSON array of entries, got {type(data).__name__}")
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            sys.exit(f"{path}: item {i} is {type(entry).__name__}, not an object")
        if "id" not in entry:
            sys.exit(f"{path}: item {i} has no id")
    return data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument(
        "--prune-dangling",
        action="store_true",
        help="drop pairs_with ids that do not exist, printing each removal",
    )
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    args = ap.parse_args()

    with PLACES.open() as fh:
        doc = json.load(fh)
    existing = doc["places"]
    seen = {p["id"] for p in existing}
    print(f"existing: {len(existing)} entries")

    incoming: list[dict] = []
    fatal = False
    for path in args.files:
        entries = load_array(path)
        added_here = 0
        for entry in entries:
            pid = entry["id"]
            if pid in seen:
                print(f"ERROR  duplicate id {pid!r} (from {path.name}) — already in the dataset")
                fatal = True
                continue
            seen.add(pid)
            incoming.append(entry)
            added_here += 1
        print(f"  {path.name}: {added_here} new entries")

    dupes = [i for i, n in Counter(p["id"] for p in incoming).items() if n > 1]
    if dupes:
        print(f"ERROR  ids duplicated within the incoming batch: {sorted(dupes)}")
        fatal = True

    if fatal:
        print("\nrefusing to merge: fix the id collisions above first")
        return 1

    # Referential integrity for pairs_with, checked against the union of old and new so a
    # cross-file reference that happens to be valid is kept.
    merged = existing + incoming
    all_ids = {p["id"] for p in merged}
    dangling_total = 0
    for entry in merged:
        refs = entry.get("pairs_with")
        if not refs:
            continue
        bad = [r for r in refs if r not in all_ids]
        if not bad:
            continue
        dangling_total += len(bad)
        if args.prune_dangling:
            entry["pairs_with"] = [r for r in refs if r in all_ids]
            for ref in bad:
                print(f"PRUNED {entry['id']}: pairs_with -> {ref!r} (no such entry)")
            if not entry["pairs_with"]:
                del entry["pairs_with"]
        else:
            for ref in bad:
                print(f"ERROR  {entry['id']}: pairs_with -> {ref!r} (no such entry)")

    if dangling_total and not args.prune_dangling:
        print(
            f"\n{dangling_total} dangling pairs_with reference(s). Re-run with --prune-dangling "
            "to drop them, or fix the ids by hand if the reference was meant to resolve."
        )
        return 1

    clusters = Counter(p["cluster"] for p in merged)
    print(f"\nmerged: {len(merged)} entries across {len(clusters)} clusters")
    for cluster, n in sorted(clusters.items()):
        print(f"  {cluster:<32} {n}")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0

    doc["places"] = merged
    with PLACES.open("w") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"\nwrote {PLACES.relative_to(ROOT)}")
    print("now run: python3 tools/validate_places.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
