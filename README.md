# Mumbai — offline-first trip companion

An Android app that does two things without a network: logs every rupee in about five seconds, and
carries a checklist of the Mumbai that locals actually use.

## Status

**TB1 — the dataset, and a phone you can install onto.** 29 sourced places across 13 of 21
clusters, a 7-day itinerary, and two front-ends: an installable web app that works today and the
Kotlin/Compose app whose **APK is built by CI** (ADR-009 — CI is the compiler, because this container
has no Android SDK). `:domain` carries the shared logic in Kotlin with **53 passing unit tests**.

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

## Layout

| Path | What it is | Verified where |
|---|---|---|
| `data/` | The curated dataset and its schema. The source of truth. | `tools/validate_places.py`, locally and in CI |
| `domain/` | Kotlin, **JVM-only, zero Android imports**. Money, the hours engine, category roll-ups, budget projection. | **53 unit tests, run locally and in CI** |
| `android/` | The Kotlin + Compose app (`:android`). | CI only — no Android SDK here (ADR-009) |
| `web/` | An installable PWA. Same dataset, works offline, runs today. | Driven in headless Chromium: 38 checks |
| `preview/` | A one-page design/data review surface. | Rendered and screenshotted |
| `tools/` | Validators and generators. | CI runs all of them with `--check` |

**Two front-ends is a deliberate, temporary state, not indecision.** ADR-001 commits to Kotlin +
Compose and that has not changed. But ADR-009 means the Compose UI cannot be compiled, run or
screenshotted in the authoring container, and the trip boards on 09 August — so `web/` is what
actually reaches the phone this week while `android/` is built and verified by CI. `domain/` is
shared: the logic is written and tested once, in Kotlin, and both front-ends implement the same
rules. The web app is expected to be retired once the Compose app carries the same features.

### Working on it

```bash
python3 tools/validate_places.py                  # the anti-fabrication gate; fails the build
python3 tools/merge_entries.py NEW.json --dry-run # ingest a research pass, checking ids and refs
python3 tools/build_app_data.py                   # regenerate web/ + android/ assets and icons
python3 tools/build_preview.py                    # regenerate preview/index.html
python3 tools/resolve_geo.py                      # needs network: fills lat/lng from OSM objects

./gradlew :domain:test        # 53 tests. Runs anywhere, including with no Android SDK.
./gradlew :android:assembleDebug   # needs an Android SDK; otherwise CI does it
```

`settings.gradle.kts` only includes `:android` when an SDK is actually present, so a clone without
one still runs the domain tests rather than failing at configuration time.

Every coordinate in the dataset is currently `null` by design — `resolve_geo.py` has never been able
to run here, and a typed-in coordinate is a fabricated address. Run it on a networked machine and
hand-check the pins before trusting the map.

### Getting it onto a phone

**The APK comes from CI, not from here.** Open the latest green run of
[`.github/workflows/ci.yml`](.github/workflows/ci.yml) and download the `mumbai-debug-apk` artifact.
The release APK is built too but is left **unsigned on purpose**: ADR-008 wants release-signed for an
app holding money and location data, and signing with the debug key would be release-signed in name
only. Signing lands when a keystore secret exists.

**The web app installs today.** Serve `web/` over https (or `http://localhost`) and use Chrome's
*Add to Home Screen*; it gets its own icon, launches without browser chrome, and works with no
network. `python3 -m http.server -d web 8000` is enough to try it locally.

### Seeing the design without a device

[`preview/index.html`](preview/index.html) is a single self-contained page — open it in any browser,
no server needed. It renders the §7 palette, the Fare Meter and the Places/Detail wireframes against
the real dataset. **It is not the app**: nothing compiled, and it proves nothing about the Android
build. Regenerate with `tools/build_preview.py`; `--check` fails if it is stale.

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
