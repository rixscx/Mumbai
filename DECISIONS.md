# Decision record

Every entry: **what** was chosen, **why**, the **strongest rejected** alternative, and the
**cost** the choice imposes later. Newest last. Entries added in the phase that made them.

Status legend: `PROPOSED` (awaiting sign-off) · `ACCEPTED` · `SUPERSEDED by ADR-nnn`.

---

## ADR-001 — Kotlin + Jetpack Compose, not Expo/React Native · PROPOSED

**Chose:** a single-target native Android app: Kotlin, Compose, Room, Hilt.

**Why:** the brief's own justification for React Native was "so native map and background location
modules work and I get a real signed AAB", which argues for native. iOS is out of scope in v1,
which removes RN's decisive advantage. The quality gates the brief demands — Macrobenchmark,
Baseline Profiles, JankStats, Paparazzi/Roborazzi, exported Room schemas with migration tests, an
AAB-size CI check — are Android toolchain features that are either unavailable or meaningless when
measured across a JS bridge.

**Rejected:** Expo SDK + prebuild with op-sqlite/SQLCipher/Drizzle and
`@maplibre/maplibre-react-native`. It is a real stack that ships real apps, and it would have been
faster to sketch UI in. It loses on measurement fidelity for exactly the budgets that were made
acceptance criteria.

**Costs later:** no path to iOS without a rewrite; every design-system primitive is hand-built
once instead of installed; UI iteration is a Gradle build rather than a fast refresh.

---

## ADR-002 — No routing server, and no offline turn-by-turn in v1 · PROPOSED

**Chose:** a `RoutingProvider` interface with a straight-line estimator for "build my day", plus
one-tap handoff to any installed nav app via `geo:` / `google.navigation:` intents, plus
station/BEST-route directions carried in the curated dataset.

**Why:** OSRM and hosted Valhalla/ORS/GraphHopper are server-side — a monthly bill and a single
point of failure that is unreachable precisely when underground. On-device routing (Valhalla tiles
or GraphHopper's core) is feasible but needs an NDK build, a second 30–60 MB per-region graph
artifact distinct from the tile pack, and voice guidance. That is a milestone, not a bullet.

**Rejected:** self-hosting Valhalla on a small VM. Cheap in money, expensive in the one dimension
that matters here — it fails offline, which is the product's whole premise.

**Costs later:** travel-time estimates are labelled estimates and will be wrong on Mumbai traffic;
"build my day" ordering is geometric, not road-network-aware, until an on-device engine lands
behind the same interface at M2.

---

## ADR-003 — Tiles as bundled + downloadable PMTiles from an OSM extract · PROPOSED

**Chose:** MapLibre Native reading PMTiles generated with Tilemaker from a Geofabrik extract; a
~6 MB Colaba/Fort pack bundled in the APK, regional packs as resumable `WorkManager` downloads.

**Why:** zero running cost, no API key to expire mid-trip, and the bundled pack makes the
airplane-mode acceptance test pass on first launch with no network at all.

**Rejected:** a hosted vector-tile provider (MapTiler/Stadia free tier). Simpler to wire, but
introduces a key, a quota, and a per-request trace of where the user is looking.

**Costs later:** tile freshness becomes our job — packs need regeneration and a `tile_version` to
drive eviction; and generating them is a build step someone has to be able to re-run.

---

## ADR-004 — Arbitrary category depth, not a cap of 3 · PROPOSED

**Chose:** `categories.parent_id` self-FK with recursive-CTE roll-ups, indexed, tested to depth 6.
No hard depth cap. Deleting a node reparents its children to the node's parent and reassigns its
expenses to that parent; expenses are never orphaned and never cascade-deleted.

**Why:** one brief made arbitrary depth an acceptance criterion; the other capped nesting at 3. The
cap fails immediately — the seed taxonomy already uses 3 levels
(`Travel ▸ Local ▸ Suburban train`), so a single user-added level hits the wall. A recursive CTE
costs the same at depth 3 or depth 8 given the index.

**Rejected:** a hard cap of 3 with a closure table. The closure table makes roll-ups a single
indexed join and would be the right call at scale; at one traveller's trip volume it is write
amplification and a second thing to keep consistent.

**Costs later:** the category picker needs breadcrumbs and a deliberate discouragement past depth
4, and roll-up queries must be `EXPLAIN`-checked rather than assumed.

---

## ADR-005 — Splits deferred from the M0 slice to M4; schema ships in M0 · PROPOSED

**Chose:** `people` and `expense_splits` tables exist from the first migration; settle-up UI lands
at M4.

**Why:** splitting is the one feature that can be replaced by a single WhatsApp message, and the
only one requiring a second human to test. Shipping the tables now means no migration later.

**Rejected:** splits in v1 as the first brief specified. Reinstated at once if you're travelling
with companions on this trip — say so and it moves to M1.

**Costs later:** minimum-transaction settlement and the UPI intent are unexercised code paths
until M4, so the schema shape is an educated guess rather than a validated one.

---

## ADR-006 — No crash reporter, no analytics, no Play Integrity · PROPOSED

**Chose:** zero third-party SDKs. No Sentry, no attribution, no integrity attestation. A local-only
crash breadcrumb file in app-private storage, surfaced on a debug screen.

**Why:** the brief requires that "no tracking, no ads" survive transitive dependencies, and with no
backend there is nothing to verify a Play Integrity token — a client-side check is bypassable and
would be theatre. Degrading the app for rooted users was explicitly ruled out.

**Rejected:** self-hosted GlitchTip. Genuinely attractive and revisitable post-v1; it still means
a server and an egress path for data the privacy note promises never leaves the phone.

**Costs later:** the ≥99.5% crash-free-session budget is unmeasurable in the field. Logged as a
consciously accepted risk rather than quietly dropped.

---

## ADR-007 — minSdk 29, above both briefs' suggested 26 · PROPOSED

**Chose:** `minSdk 29` (Android 10), `targetSdk 36`.

**Why:** the stated device floor *is* Android 10, and 29 deletes every pre-scoped-storage code
branch from the photo, receipt and export paths — the exact code where a bug becomes a data leak.

**Rejected:** minSdk 26 as suggested, keeping legacy-storage fallbacks. Reversible on request.

**Costs later:** excludes Android 8–9 devices; if that matters the fallbacks come back and the
privacy surface widens with them.
