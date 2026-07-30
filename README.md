# Mumbai — offline-first trip companion

An Android app that does two things without a network: logs every rupee in about five seconds, and
carries a checklist of the Mumbai that locals actually use.

## Status

**Phase 0 — alignment. No application code exists yet.** That is deliberate: the two source briefs
specified mutually exclusive stacks, and the resolution needed sign-off before a line of Kotlin was
worth writing.

Read, in order:

1. [`docs/PHASE-0-ALIGNMENT.md`](docs/PHASE-0-ALIGNMENT.md) — the stack contradiction and its
   resolution, the eight other contradictions found between the briefs, every assumption in force,
   the three requirements that are not deliverable as written and why, the tile/routing decision
   with costs, the design plan, and the phase plan.
2. [`DECISIONS.md`](DECISIONS.md) — ADRs for the non-obvious choices, each stating what was chosen,
   why, what was rejected, and what it costs later.

`ARCHITECTURE.md` arrives with the D2 record. Build instructions arrive with M0, at which point
this file gets the one documented command that produces a signed AAB from a clean clone.

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
