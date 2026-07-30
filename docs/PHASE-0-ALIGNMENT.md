# Phase 0 — Alignment

**Status: PROPOSED, awaiting sign-off. No implementation code exists yet, by design.**

Two briefs were supplied. They agree on the product and disagree on the stack. This document
resolves the disagreements, states every assumption I am running on, names the three things in
the briefs that are not deliverable as written, and sets the phase plan.

---

## 1. The contradiction, resolved

Brief A ("Bandra") specifies **Expo + React Native**, and justifies it as *"so native map +
background location modules work and I get a real signed `.aab`"*. Brief B specifies **Kotlin +
Compose + Room + Hilt**, identifies the web-stack items as the contradiction, and recommends
native-only.

Brief A's stated justification is an argument *for* native, not for React Native. Both briefs
rule out iOS in v1, which removes React Native's only decisive advantage. Brief B's performance
and quality gates — Macrobenchmark, Baseline Profiles, JankStats, Paparazzi/Roborazzi, exported
Room schemas with migration tests, R8 shrink verification, an AAB-size CI check — are Android
toolchain features. In an Expo project they are either unavailable or measured through a bridge
that makes the numbers meaningless.

**Decision: Kotlin + Jetpack Compose, single Android target. Brief B is authoritative on stack,
architecture and process. Brief A is authoritative on product, domain vocabulary, the Mumbai
places dataset and the design bar.**

### Mapping table (Brief B §3, option A)

| Brief says | Native equivalent | What's lost / gained |
|---|---|---|
| shadcn/ui, react-native-reusables | Material 3 (`androidx.compose.material3`) + a thin in-house component layer in `:core:designsystem` | **Lost:** a copy-paste component library; every primitive is hand-built once. **Gained:** no bridge, no `View` flattening cost, real M3 dynamic colour and TalkBack semantics for free. |
| Tailwind / NativeWind tokens | `MaterialTheme` extension + a `KaaliTokens` object exposing semantic names only | **Lost:** utility-class speed while sketching. **Gained:** tokens are Kotlin, so a PR that writes a raw hex at a call site fails detekt. |
| Motion.dev / anime.js / Reanimated | `animate*AsState`, `AnimatedContent`, `updateTransition`, `SharedTransitionLayout`, spring specs | **Lost:** nothing real. **Gained:** animation runs on the same thread as composition; no JS-thread jank class of bug exists. |
| Lucide icons | Lucide static SVG → vector drawables, de-duplicated against `material-icons-extended` (Lucide is ISC; attribution recorded on the Licences screen) | **Lost:** the whole 1400-icon set on tap. **Gained:** only the ~40 icons used ship, so APK cost is bounded. |
| Haikei SVG backgrounds | One static vector, one screen (trip summary), hard cap 24 KB, ≤8% opacity | **Lost:** generative variety. **Gained:** the fastest tell of an AI-built app is a decorative gradient blob; rationing it to one screen is the point. |
| Lottie | `lottie-compose`, ≤3 files, each named and justified (§7 below) | Kept as specified. |
| Fontjoy pairing | Same pairing method, self-hosted as bundled `.ttf`, subset with `pyftsubset` | Kept, and now offline by construction. |
| op-sqlite + Drizzle + SQLCipher | Room + `android-database-sqlcipher` (`net.zetetic:sqlcipher-android`) | **Lost:** Drizzle's TS-native migration ergonomics. **Gained:** Room exports a JSON schema per version and `MigrationTestHelper` makes migration tests trivial — which is what actually protects day-1 trip data. |
| @maplibre/maplibre-react-native | `org.maplibre.gl:android-sdk` (MapLibre Native) | **Gained:** the RN package wraps this; going direct removes a wrapper from the offline-pack code path, which is the least forgiving part of the app. |
| TanStack Query + Zustand + MMKV | Room `Flow` + `StateFlow` per screen + Jetpack DataStore (Preferences) | **Lost:** query caching machinery. **Gained:** there is no network to cache. Room is the single source of truth, so a client cache layer would be a second source of truth pretending to be one. |
| victory-native / Skia charts | Charts drawn in `Canvas` in Compose, no chart library | **Lost:** free chart types. **Gained:** two chart forms (bar, timeline) are all §6 mandates; a library for two forms is 300 KB of policy I don't control. |
| Maestro E2E | Espresso + Compose UI test for critical paths only | **Lost:** Maestro's YAML terseness. **Gained:** runs in the same Gradle invocation as CI. Maestro can be added later against the built APK if you want it. |
| Sentry (opt-in) | **Dropped from v1.** No crash SDK. | Brief B requires that "no tracking, no ads" survive transitive dependencies. Crash-free-rate ≥99.5% is then unmeasurable in the field — stated as an accepted risk in the risk register, not quietly dropped. Revisit with self-hosted GlitchTip post-v1. |

**Substitution I am making against both briefs, with reasoning:** `minSdk 29`, not 26. The stated
device floor is Android 10. minSdk 29 deletes every pre-scoped-storage branch from the photo and
export code, which is exactly the code where a privacy bug becomes a data leak. Cost: excludes
Android 8–9 devices (~4% of Indian Android traffic and falling). Say the word and I'll take it
to 26 and eat the branches.

---

## 2. Other contradictions found

| # | Conflict | Resolution |
|---|---|---|
| 1 | A §6 puts **splits + settle-up in v1**; B backlogs splitting explicitly. | Splits are **not in M0**. `expense_splits` and `people` ship in the M0 *schema* (so no migration later), UI lands in M1. Reason: settle-up is the single feature you can replace with one WhatsApp message, and it is the only one that needs a second human to test. |
| 2 | A: **arbitrary category depth** (acceptance criterion). B: **cap nesting at 3**. | Arbitrary depth in schema and roll-ups (`parent_id` self-FK + recursive CTE, indexed), tested to depth 6. No hard cap. B's cap of 3 fails on contact with A's own seed taxonomy plus one user-added level. Picker shows breadcrumbs and discourages depth >4; it does not forbid it. |
| 3 | A: cold start **<2.0 s**. B: **p90 <1.5 s on the device floor**, and notes SQLCipher's KDF cost. | Take B's number as the budget. It is at risk and I will not assert it — Home renders from a DataStore-cached summary while the DB opens off the critical path, and M0 ships the Macrobenchmark that produces the real figure. If it lands at 1.7 s you will see 1.7 s. |
| 4 | A: Mumbai, one trip, INR. B: multi-currency, en+hi, 20 currencies. | Schema is multi-trip and multi-currency from row one (`fx_rate`, `fx_source`, `currency`, per-currency exponent table). UI is Mumbai/INR-only through M0–M1. Currency picker at M1. Hindi/Marathi strings extracted from M0, translated at M1. |
| 5 | A: home screen unspecified. B: "opens onto today, on this trip". | B. Home is Today. No metrics dashboard. |
| 6 | A wants **3 type families** (display/body/mono). B caps at **2**. | 2 families. IBM Plex Sans carries the mono need via Plex Mono *within the same superfamily*, so tabular receipt/export views stay in-family. |
| 7 | A: routing via self-hostable Valhalla/ORS/GraphHopper. B: correctly notes hosted routers are not on-device. | See §4. No routing server in v1. |
| 8 | A: **8 phases each ending in a runnable app**. B: **8 documents, one per response, code last**. | Merged — see §8. Three lean decision records, then M0 code, then feature phases. Eight prose documents before any running code would burn the budget on paper. |

---

## 3. Constraints and assumptions

Values marked **[A]** are my assumption because the brief left the placeholder empty; correct any
of them in one word and I'll re-cut.

| Constraint | Value |
|---|---|
| Team / time | Solo, ~12 weeks, nights and weekends **[A]** |
| Device floor | 4 GB RAM, Android 10, Snapdragon 6-series class. All budgets measured here, on hardware, not an emulator **[A]** |
| minSdk / targetSdk | 29 / 36 (Android 16) — see §1 for the minSdk deviation |
| Backend | **None.** Not "TBD" — none. This makes Play Integrity theatre (§5) and makes TLS pinning apply only to tile/font downloads |
| Offline storage budget | ≤400 MB per city region, ≤3 GB total, per-region delete **[A]** |
| Locales / currencies | en at launch; hi + mr strings extracted, translated M1. INR base, multi-currency in schema, 20-currency UI at M1 **[A]** |
| Monetisation | None in v1. No ads, no analytics, no attribution SDK, no IAP dependency **[A]** |
| Distribution | Play Store (internal testing track first) **and** a sideloadable release APK for your own phone **[A]** |
| Trip dates | **Unknown — tell me.** If departure is inside 8 weeks I re-order the phases so the places dataset and the offline Colaba pack land before you fly, and the summary/charts polish slips behind it |

---

## 4. Tiles and routing — decision with real costs

**Tiles: MapLibre Native + PMTiles generated from a Geofabrik `india-latest` OSM extract, clipped
to Greater Mumbai.** Built with Tilemaker into a single `.pmtiles` archive, read locally via a
`file://` protocol handler — no tile server, no per-request cost, no API key that expires
mid-trip. Estimated 40–90 MB for Greater Mumbai at z0–14 plus z15–16 over the covered clusters;
the real number goes in the M0 changelog because I'll have generated it. A ~6 MB Colaba/Fort pack
ships **inside the APK** so the map works on first launch with no download, which is what makes
the airplane-mode acceptance test pass on day one.

**Running cost: ₹0/month.** Downloadable regional packs are static files — GitHub Releases, or
any object store you already pay for. Downloads are resumable, `WorkManager`-managed, and refuse
to start on a metered connection without an explicit tap.

**Routing: no routing server, and no offline turn-by-turn in v1.** This is the "stop and ask"
item from Brief A §13, and the answer is that the requirement as written is not deliverable
honestly at v1 scope:

- OSRM and hosted Valhalla/ORS/GraphHopper are **server-side**. Self-hosting one means a VM, a
  monthly bill, and a single point of failure that is unreachable exactly when you're underground
  — which is when you need it.
- Genuinely on-device options exist (Valhalla's tiled routing compiles for Android; GraphHopper
  has an Android-capable core) but each adds an NDK build, a second large per-region data
  artifact (a routing graph is *not* the tile pack — budget another 30–60 MB for Greater Mumbai),
  and a voice-guidance layer. That is a milestone of its own, not a bullet.

**So v1 does three real things instead of one fake one:** (a) a `RoutingProvider` interface with a
`StraightLineProvider` implementation used for "build my day" travel-time estimates, honestly
labelled *"~12 min estimate, not a route"*; (b) one-tap handoff to any installed nav app via
`geo:` and `google.navigation:` intents, with a graceful message if none is installed; (c) walking
distance and the nearest suburban station / metro / BEST route from the curated dataset, which is
how people actually navigate Mumbai. Offline turn-by-turn goes to M2 behind the same interface.
The UI will never show a "route" affordance it can't honour.

**Licensing, stated because it constrains the dataset:** OSM is ODbL. Rendered tiles are a
*Produced Work* — attribution required, share-alike not triggered. But a places table that
**derives coordinates from OSM** is a Derivative Database and *is* share-alike. Mitigation:
`data/places.mumbai.json` splits into `geo` fields (OSM-derived, published under ODbL) and
editorial fields (original prose, our licence). Wikivoyage/Wikidata are CC BY-SA — so no
Wikivoyage prose gets pasted into `what_it_is`; it is cited as a source, and the description is
written fresh. Attribution is a persistent, tappable element on the map surface, not an About-screen
footnote.

---

## 5. Where the briefs ask for something I can't deliver as written

Three, said plainly now rather than discovered in week six.

1. **"≥180 verified places, zero fabricated addresses or timings."** The *verification* is the
   hard part, not the writing. I can produce 180 plausible entries in an hour; that is precisely
   the failure mode both briefs prohibit. What I can do honestly: build the dataset per-cluster
   with a per-field provenance record and a `confidence` value, where `high` means the
   coordinate was cross-checked against OSM/Wikidata and the timing has a citable source;
   `medium` means the place is well-attested but a specific field is stale-risk; `low` means "go
   look before you rely on this". Anything I cannot source **is not written**, and opening hours
   and prices are the fields most likely to come back empty rather than guessed. The realistic
   outcome is 180+ entries where a meaningful fraction carry `low`/`medium` confidence on
   timings and near-100% carry verified coordinates. Which of those two — the count, or the
   confidence distribution — is the acceptance bar is your call (Question 3).
2. **Play Integrity / root detection.** With no backend there is nobody to verify the attestation
   token, so a client-side check is bypassable by anyone who cared enough to root the device.
   Shipping it would be security theatre and it would insult the power users who are most likely
   to be your users. **Not shipping it.** The real control is that the DB is unreadable when
   pulled off the device, which SQLCipher + Keystore delivers and which is testable.
3. **Crash-free sessions ≥99.5%** with no crash reporter is unmeasurable in the field. Accepted
   risk, logged in the register, with a local-only crash breadcrumb written to app-private storage
   and surfaced on the debug screen as the compromise.

---

## 6. Product definition (terse; the full brief is deliverable 1)

**Positioning:** the offline notebook for a trip to Mumbai — every rupee in five seconds, and a
checklist of the city locals actually use, both working in a tunnel.

**Primary job:** *when I've just paid for something, log it in seconds without breaking stride.*
Secondary: *when I have three free hours in a neighbourhood, tell me what's worth doing near me
right now.* Secondary: *when I get home, know where the money went.*

**Non-goals:** no accounts or cloud; no social/feed/badges; no live transit arrivals; no chatbot
or AI surface; no iOS; no widgets/Wear/tablet layouts; no receipt OCR; no in-app payments beyond
firing a UPI intent.

**Metrics, all measurable on-device and privately:** median cold-open→expense-committed under 6 s;
share of expense entries completed in ≤5 taps; share of sessions with no network (expected high —
if it's low, the offline-first premise is wrong); day-3 retention of ≥5 expenses logged; share of
checklist places visited per cluster.

**What this does that Google Maps saved lists + Splitwise + a notes app do not:** those three
break in the same place — they need signal, and none of them connects the two halves. Here,
checking off Sewri jetty offers to log the ₹40 auto and the ₹120 breakfast against
*Travel ▸ Local ▸ Auto* and *Food ▸ Street food* with the cost pre-filled from the dataset, with
no network, and the budget line updates before you've put the phone away. The seam is the product.
If that seam doesn't feel inevitable in M1, the product isn't defined and I'll say so.

---

## 7. Design plan

### Palette source: the kaali-peeli fleet, sampled honestly

Not "Mumbai vibes" — the Premier Padmini taxi as a material object: a bituminous body black that
goes warm grey-brown in afternoon sun, an ochre roof that is mustard and not acid, hand-painted
enamel number plates, the printed rexine seat covers in jade and fuchsia, and the chrome of the
meter housing. Six semantic tokens, no more:

| Token | Hex | HSL | Role |
|---|---|---|---|
| `surface.ink` | `#17150F` | `45 19% 8%` | dark-theme base; the body black, warm not neutral |
| `surface.plate` | `#F2F3F1` | `100 6% 95%` | light-theme base; enamel plate white, cooled so it is **not** cream paper |
| `accent.ochre` | `#D9A21B` | `42 79% 48%` | money numerals, the one primary action per screen |
| `state.jade` | `#1F7A5C` | `163 60% 30%` | under budget, visited, confirmed |
| `state.taillight` | `#A32017` | `4 75% 36%` | over budget, destructive |
| `moment.fuchsia` | `#C2367E` | `328 57% 48%` | the check-off moment only; never a surface |

Chrome greys are a ramp derived from `surface.ink` at fixed L steps, not a second hue.

**Contrast, computed not asserted:** `accent.ochre` on `surface.ink` = **8.0:1** ✓. `surface.ink`
on `surface.plate` = **16:1** ✓. `state.jade` on `surface.ink` = **3.6:1** — so jade is a *fill*
with ink text on top, or large text only; never body copy. And `accent.ochre` on `surface.plate`
= **2.0:1**, a fail — light theme therefore uses `accent.ochre.text` `#7A5806` (**5.3:1** ✓) for
ochre *text*, with the bright ochre reserved for fills. Both themes are first-class and both get
verified in a Roborazzi contrast test, including dynamic-colour mode.

### Type: two families

- **Archivo / Archivo Expanded** (OFL, Omnibus-Type) — screen titles and *all* money numerals.
  Chosen for lining tabular figures with unambiguous 1/7 and 0/O, and a variable width axis so
  large amounts compress without a second face. It reads like transit signage, which is the right
  register for a city whose typography is destination boards.
- **IBM Plex Sans** (OFL) — all body and UI. Tall x-height and open apertures hold up at 13 sp on
  a bright street. The decisive reason over Inter: **Plex Sans Devanagari** exists in the same
  superfamily, so Marathi place names set alongside English don't switch skeleton mid-line, and
  **Plex Mono** covers receipt/export tabular views without a third family.

Money is set in Archivo, large, tabular, with `₹` at 0.72 em and 60% opacity and paise at 0.6 em —
the rupees are the number, the rest is punctuation. 4 dp base unit / 8 dp rhythm, ≥48 dp targets,
three elevation levels with stated meanings (0 = page, 1 = raised card, 2 = sheet/dialog only),
one radius family, one border colour.

### Signature element: **the Fare Meter**

A single hairline strip, always present at the top of Home and re-appearing in the header of the
expense sheet: today's remaining budget as a filling meter styled after a taxi meter's readout,
with one sentence of honest projection beneath it — *"₹1,240 left today · at this rate you run out
Tue 11 Aug."* It is load-bearing: it answers "can I afford this auto?" before you've decided to
open the app, and it is the same component in both places so committing an expense visibly moves
the thing you were just looking at. It is text and one rule, no chart, no gradient.

### Wireframes

```
HOME — "Today"                              ADD EXPENSE (sheet, thumb zone)
┌────────────────────────────┐              ┌────────────────────────────┐
│ Mumbai · Day 4 of 12   ⚙  │              │ ═══ (drag)              ✕ │
│▓▓▓▓▓▓▓▓▓░░░░░░ ₹1,240 left │←Fare Meter   │▓▓▓▓▓░░░ ₹1,240 left today │←same meter
│ at this rate: out Tue 11   │              │                            │
├────────────────────────────┤              │        ₹  1 4 0            │←Archivo, huge
│ TODAY                      │              │        Auto · UPI          │←smart default
│ 09:12  Irani chai      ₹40 │              ├────────────────────────────┤
│ 09:40  Auto Fort→Sewri ₹80 │              │ [Auto] [Chai] [Train ₹10]  │←recents chips
│ 13:05  Thali          ₹210 │              │ [Lunch] [＋ all categories]│
│        ── 3 entries, ₹330  │              ├────────────────────────────┤
├────────────────────────────┤              │  1   2   3      ⌫         │
│ NEARBY, UNVISITED          │              │  4   5   6                 │
│ ○ Sewri jetty · flamingo   │              │  7   8   9      ┌────────┐ │
│   tide window 07:00–10:00  │              │  ·   0   00     │  SAVE  │ │←ochre, 56dp
│   ~₹40 auto · 90 min       │              │                 └────────┘ │
│ ○ Bhau Daji Lad museum     │              │ ▸ note · photo · yesterday │←collapsed
├────────────────────────────┤              └────────────────────────────┘
│ Today  Trip  Places  Map   │              4 taps for ₹140 auto: 1,4,0,SAVE
└────────────────────────────┘                 (category pre-selected by geofence)

PLACES — checklist                          PLACE DETAIL — rules above photo
┌────────────────────────────┐              ┌────────────────────────────┐
│ Places        14/186 ✓     │              │ ←  Sewri Jetty        ♡ ⤴ │
│ [open now][walkable][<₹200]│              │ शिवडी बंदर                 │
│ [monsoon-safe][veg][unseen]│              │ viewpoint · nature · free  │
├────────────────────────────┤              ├────────────────────────────┤
│ MATUNGA            6/11 ✓  │              │ BEFORE YOU GO              │←first, always
│ ☑ Café Madras              │              │ · Tide table decides this,  │
│   ₹150 · 30m · high conf   │              │   not the clock. Low tide   │
│ ☐ Ram Ashraya              │              │   Nov–Mar, 07:00–10:00.     │
│   06:00–10:30 · ₹120       │              │ · Ask at the gate; access   │
│ ☐ Mysore Concerns          │              │   is not guaranteed.        │
│   ⚠ low confidence: hours  │              │ · No toilet. No shade.      │
├────────────────────────────┤              │ · Solo: fine by day, leave  │
│ FORT / KALA GHODA  3/13 ✓  │              │   before dusk.              │
│ ...                        │              ├────────────────────────────┤
├────────────────────────────┤              │ GETTING THERE              │
│ [ Build my day → ]         │              │ Sewri stn (Harbour) + 12m   │
└────────────────────────────┘              │ walk · auto from Fort ~₹80  │
                                            ├────────────────────────────┤
MAP — spend + places                        │ [photo, lazy, never blocks] │
┌────────────────────────────┐              │ conf: medium · rev 2026-07  │
│ [places|spend]      ⛶  ⊕  │              ├────────────────────────────┤
│                            │              │ [✓ Mark visited] [Log ₹]   │
│     ◉12    ◉4              │←clustered    │ [Open in nav app]          │
│         ◉31     ○          │              └────────────────────────────┘
│   ○         ◉7             │
│                            │              TRIP SUMMARY
│ ┌────────────────────────┐ │              ┌────────────────────────────┐
│ │ ═══                    │ │←bottom sheet │  ₹18,420                   │←Archivo, hero
│ │ Fort · ₹2,140 · 9 stops│ │              │  of ₹30,000 · 12 days      │
│ └────────────────────────┘ │              │ ▓▓▓▓▓▓▓▓▓░░░░  61%         │
│ © OpenStreetMap (ODbL)     │←persistent   │ ──────────────────────────  │
└────────────────────────────┘               │ Food & Drink    ₹6,210 ▸  │
                                            │ Travel ▸ Local  ₹2,890 ▸  │←tree drill
                                            │ Stay            ₹7,100    │
                                            │ ──────────────────────────  │
                                            │ [bar chart, days, Canvas]  │
                                            │ 41 places visited of 186   │
                                            │ [Export CSV / JSON / .db]  │
                                            └────────────────────────────┘
```

### Motion budget

Three Lottie moments, named: (1) checklist check-off, (2) budget threshold crossed — the meter
tipping from jade to taillight, (3) trip-summary reveal. Everything else is ≤150 ms opacity or
translate. The FAB→sheet transition uses `SharedTransitionLayout`, not Lottie. Reduced-motion and
`ANIMATOR_DURATION_SCALE == 0` both fully honoured — under either, all three become instant state
changes and nothing becomes unintelligible, because no animation carries information on its own.

### Self-critique of this plan

- **Killed:** my first palette pass was tide-greys plus a flamingo-pink accent. That is
  "neutral surface plus one accent", which is the shape of every finance app shipped since 2019,
  and the specificity was decorative — nothing about the greys changed a single decision. The
  taxi palette earns its place because `moment.fuchsia` is quarantined to one interaction and the
  ochre is the money colour, so the palette encodes hierarchy rather than mood.
- **Still generic, flagged honestly:** the bottom-tab-plus-FAB shell is exactly what any expense
  app does. I'm keeping it, because the alternative is novelty that costs you taps, and Brief A's
  own acceptance criterion is a tap count. The differentiation has to come from the Fare Meter,
  the numerals, and the places seam — not from inventing navigation.
- **At risk:** "Archivo reads like transit signage" is one sentence away from being a vibe. It
  survives only if the tabular figures are actually verified at 200% font scale in the M0
  screenshot tests. If they clip, the face changes.
- Brief A asks for a Haikei-style background on the summary screen. I've budgeted it (one vector,
  ≤24 KB, ≤8% opacity) but I think it makes that screen worse, and I will show you the screen
  both ways in the phase that builds it rather than arguing now.

---

## 8. Phase plan and what "done" means

Merged from A §13 and B §13. Three lean decision records, then running code every phase.

| Phase | Deliverable | Done means |
|---|---|---|
| **0** | This document | You've answered the four questions and signed off the design plan |
| **D1** | Product + UX record: personas labelled as assumptions, teardown of 4 real apps, RICE backlog, IA tree, nav graph with back-stack and deep-link behaviour, 6 key flows as annotated wireframes | ≤1,800 words. Every screen names the user's next action |
| **D2** | Architecture + security record: module graph, Room schema as real DDL with indices and the query each serves, sync-deferral design, threat model with top 8 threats and consciously accepted risks, 6 ADRs | A new engineer can find any feature in <60 s from the module graph alone |
| **M0** | Vertical slice, compiling and tested: create trip → log expense (amount, category, currency, payment method) in <6 s → expenses grouped by day → one offline map screen rendering the bundled Colaba pack. SQLCipher + Keystore, CI green, Baseline Profile, Macrobenchmark | `./gradlew assembleRelease` from a clean clone. Cold-start number **reported, not asserted**. Migration test passes. Zero `TODO()` |
| **M1a** | Expenses complete: keypad entry, quick-add presets, category tree with arbitrary-depth roll-ups, day timeline, budgets + Fare Meter, undo everywhere, receipts | Adding ₹30 auto is ≤5 taps, measured. Roll-ups correct at every level, property-tested |
| **M1b** | Data portability: CSV + JSON + encrypted DB export via SAF, lossless import | Export → wipe → import equality test green. Deliberately **before** the fun features |
| **M2a** | Places dataset: `data/places.mumbai.json` + a verification report per cluster with per-field provenance and confidence distribution | Every entry has insider rules, transit, cost, confidence, `last_reviewed`. Nothing unsourced was written |
| **M2b** | Places UI: checklist, filters, detail, "build my day", the log-what-you-spent seam | Airplane mode: browse all clusters, check off, log linked expense |
| **M3** | Maps: offline pack manager, spend map, nav handoff, foreground-service tracking + geofence suggestions with just-in-time rationale | Permission-denied path is fully usable. Battery draw measured and reported |
| **M4** | Trip summary, charts, the three motion moments, splits + settle-up, hi/mr locales | Design self-critique against §7 re-run and reported, including failures |
| **M5** | Hardening + release: MASVS-L1 self-audit table, licences screen, R8 keep rules, perf pass against budgets, signed AAB, Play data-safety answers, background-location declaration text, README/ARCHITECTURE/DECISIONS | Every budget has a measured number next to it. Store checklist complete |

Splits moved from M0 to M4 (contradiction #1). Export moved early to M1b, per Brief A's insistence
that portability isn't a nice-to-have — it's also the only real recovery story once the DB is
encrypted with a Keystore-bound key that dies with the device.
