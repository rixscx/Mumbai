# Mumbai — offline-first trip companion

An Android app that does two things without a network: logs every rupee in about five seconds, and
carries a checklist of the Mumbai that locals actually use.

## Status

**TB1 — the dataset. In progress: 29 places across 13 of 21 clusters, plus a 7-day itinerary.**
Phase 0 is signed off. A Gradle scaffold exists with a JVM-only `:domain` module; **no Android code
has been compiled**, because this container has no Android SDK and cannot reach Google's Maven
(ADR-009 — CI is the compiler).

The dataset comes first on purpose: it is the one deliverable that is **useful even if no app ever
ships**, and the trip it serves boards on 09 August.

Read, in order:

1. [`docs/TRIP.md`](docs/TRIP.md) — the real trip, off two IRCTC tickets. Arrive Dadar 05:45 Mon
   10 Aug 2026, depart CSMT 07:55 Mon 17 Aug. Seven days, peak monsoon. This file sets every
   deadline in the project.
2. [`docs/ITINERARY.md`](docs/ITINERARY.md) — the seven days, built only from sourced dataset
   entries, with the closures and hazards that decided the ordering and an explicit list of what is
   missing.
3. [`data/VERIFICATION.md`](data/VERIFICATION.md) — per-cluster coverage, the confidence
   distribution, the findings that change the trip, source conflicts left visible rather than
   resolved by guesswork, and everything still unverified.
4. [`docs/PHASE-0-ALIGNMENT.md`](docs/PHASE-0-ALIGNMENT.md) — the stack contradiction and its
   resolution, the eight other contradictions found between the briefs, every assumption in force,
   the three requirements that are not deliverable as written and why, the tile/routing decision
   with costs, the design plan, and the phase plan (§9 is the pre-trip re-cut).
5. [`DECISIONS.md`](DECISIONS.md) — ADRs for the non-obvious choices, each stating what was chosen,
   why, what was rejected, and what it costs later.

`ARCHITECTURE.md` arrives with the D2 record. Build instructions arrive with M0, at which point
this file gets the one documented command that produces a signed AAB from a clean clone.

### Working on the dataset

```bash
python3 tools/validate_places.py                 # the anti-fabrication gate; fails the build
python3 tools/merge_entries.py NEW.json --dry-run # ingest a research pass, checking ids and refs
python3 tools/build_preview.py                   # regenerate preview/index.html from the dataset
python3 tools/resolve_geo.py                     # needs network: fills lat/lng from OSM objects
```

Every coordinate in the dataset is currently `null` by design — `resolve_geo.py` has never been able
to run here, and a typed-in coordinate is a fabricated address. Run it on a networked machine and
hand-check the pins before trusting the map.

### Seeing it without an Android device

[`preview/index.html`](preview/index.html) is a single self-contained page — open it in any browser,
no server needed. It renders the §7 palette, type roles, Fare Meter and the Places/Detail wireframes
against the real dataset, and its closed-on-a-given-day logic runs off each entry's own
`hours.closed_days`, so picking Mon 10 Aug really does strike out the four places that are shut.

It exists because ADR-009 means the Compose UI cannot be built or looked at in this container, so the
design would otherwise go unreviewed until someone with an Android machine ran it. **It is not the
app**: no Kotlin, nothing compiled, and it proves nothing about the Android build. Regenerate it with
`tools/build_preview.py` after any dataset change; `--check` fails if it is stale.

## Planned stack

Kotlin · Jetpack Compose (Material 3) · Room + SQLCipher · Hilt · MapLibre Native + PMTiles ·
WorkManager. Single Android target, `minSdk 29` / `targetSdk 36`. No backend, no accounts, no
analytics, no crash SDK.

## Licences and attribution

Map data © OpenStreetMap contributors, ODbL — attributed in-app on the map surface, not buried in
an About screen. Curated place coordinates derived from OSM are published under ODbL and kept in
fields separate from original editorial prose. Fonts (Archivo, IBM Plex) are OFL; Lucide icons are
ISC. Full list ships on the in-app Licences screen at M5.

## Privacy

Your data never leaves the phone unless you export it. There is no server to leave it on.
