# The actual trip

Extracted from two IRCTC Electronic Reservation Slips. This file is the source of truth for trip
dates, and it replaces the "trip dates unknown" open question in `PHASE-0-ALIGNMENT.md`.

Claims below are labelled **FACT** (read off the ticket), **DERIVED** (arithmetic on facts), or
**VERIFY** (matters for planning, must be sourced before anything relies on it — never asserted).

---

## Facts from the tickets

| | Inbound | Outbound |
|---|---|---|
| Train | 11036 **Sharavati Express** | 11301 **Udyan Express** |
| From | Mysuru Jn (MYS) | Chhatrapati Shivaji Maharaj T (CSMT) |
| To | **Dadar (DR)** | KSR Bengaluru (SBC) |
| Departs | 06:15, Sun 09-Aug-2026 | 07:55, **Mon 17-Aug-2026** |
| Arrives | **05:45, Mon 10-Aug-2026** | 06:00, Tue 18-Aug-2026 |
| Class / status | Sleeper (SL), **RAC/18** | Sleeper (SL), **RAC/5** |
| PNR | 4762122976 | 8751562744 |
| Distance | 1,212 km | 1,153 km |
| Ticket fare | ₹580 | ₹565 |
| **Total paid** | **₹768.00** | **₹743.00** |

Fare breakdown, both legs: IRCTC convenience fee ₹17.70, agent service charge ₹19.99, travel
insurance ₹0.45, FCF Max charge ₹139 (inbound) / ₹149 (outbound). Booked via ConfirmTkt
(Le Travenues Technology). Passenger: one adult, 22 M, no food. GST: nil on both.

Both legs are RAC, not confirmed. RAC boards legally and the dates hold either way, so nothing in
the plan depends on confirmation — noted only so no one is surprised by a shared side-lower berth.

---

## Derived

- **7 usable days on the ground: Mon 10 Aug → Sun 16 Aug 2026.** The 17th is not a day — CSMT
  departure at 07:55 means leaving accommodation around 06:45, so Sun 16 Aug is the last real day
  and the 16th is the last night.
- Trip record for the app: `start_date = 2026-08-10`, `end_date = 2026-08-17`, `city = Mumbai`,
  `tz = Asia/Kolkata`.
- **Arrival is Dadar, departure is CSMT.** Different ends of the city, which is convenient: the
  first morning is a Dadar/Matunga morning whether you planned it or not, and the last morning is a
  Fort/CSMT morning.
- **Day 1 is decided by the ticket.** You are on the platform at Dadar at 05:45 with a bag. Dadar
  is the one place in Mumbai where 05:45 is the *right* time to arrive rather than a problem to
  solve — the flower market runs pre-dawn (VERIFY exact hours), and Matunga's South Indian
  breakfast belt one station south opens early (VERIFY per establishment).
- **Two real expenses exist before the app does:** ₹768 and ₹743, both
  `Travel ▸ Long distance ▸ Intercity train`, dated 09-Aug and 17-Aug. These seed the trip. Every
  screenshot in this project will use these numbers and the ones that follow them — there will be
  no fabricated demo data anywhere, per the briefs' prohibition.
- Weekdays: Mon 10, Tue 11, Wed 12, Thu 13, Fri 14, **Sat 15 (Independence Day)**, Sun 16.
  Two weekend days, and a public holiday on the Saturday.
- **Today is 30 Jul 2026. Boarding is in 10 days.** See §"What this does to the plan".

### A free validation of the time-zone decision

The inbound ticket's own print timestamp is `31-Jul-2026 01:44:28` IST, which is `2026-07-30
20:14 UTC` — a document that belongs to the 31st in Mumbai and the 30th in UTC. That is exactly the
bug class ADR/§9.3 guards against, appearing unprompted in the first real document the project
touched. Confirms the rule: store instants in UTC, let the **trip's** zone own the day boundary,
never the device's.

---

## The season changes the product

**August is peak south-west monsoon in Mumbai** (roughly Jun–Sep; August is typically among the
wettest months). This is not a footnote — it re-ranks the entire dataset, and it invalidates one of
my own examples from the Phase 0 wireframes:

- **The Sewri flamingos are not there.** They are winter migrants, roughly Nov–Mar. I used "Sewri
  jetty · flamingo tide window 07:00–10:00" as the sample row in the Phase 0 Home wireframe. For
  *this* trip that row is wrong, and it is a useful wrong: it is precisely why `season` is a
  first-class field with filtering behaviour rather than prose in a description. The app must hide
  or visibly de-rank out-of-season entries, not show them and let you find out at the jetty.
- **Monsoon ferry suspensions (VERIFY, but plan around them):** passenger ferries to **Elephanta**
  are suspended during the monsoon for sea conditions, and the Alibaug catamaran / RoRo services
  likewise. Treat the Elephanta and Alibaug day trips from the brief's cluster list as **out for
  this trip** until proven otherwise. Short creek crossings (Madh–Versova, Gorai) may run but are
  weather-dependent.
- **`monsoon_safe` becomes the primary filter, not a nice-to-have.** The dataset should be weighted
  toward what August rewards: covered markets, Irani cafés, the Matunga/Dadar/Ghatkopar food belts,
  indoor heritage and museums, and the specifically-monsoon-good outdoors — the green in Aarey and
  Sanjay Gandhi NP, Kanheri, high-tide sea walls at Marine Drive and Bandstand.
- **Waterlogging and train disruption are a routing input.** Heavy-rain blackspots are well
  documented (Hindmata/Dadar, Sion, Kurla, Andheri and Milan subways). "Build my day" should prefer
  plans that don't depend on crossing one, and the app should be honest that a suburban line can
  simply stop.
- **Tide times matter and I will not invent them.** The Haji Ali causeway submerges at high tide;
  Sewri's mudflats and several sea-facing walks are tide-dependent. Real tide predictions for
  10–17 Aug 2026 have to be sourced and bundled, or the field ships empty with a "check the tide"
  instruction. It will not be filled with plausible-looking numbers.

### Calendar items to verify before they wreck a day (VERIFY, all of them)

- **Sat 15 Aug is Independence Day** — expect security restrictions and possible closures around
  CSMT, Gateway, Marine Drive and government buildings. Needs checking, not guessing.
- **Both bookend days are Mondays**, and many museums close on Mondays. Which ones, specifically,
  is a research task — arriving at a locked gate on day one is exactly the failure the insider-rules
  field exists to prevent.
- Any Parsi New Year / Janmashtami dates falling in the window — relevant to Irani cafés and to
  crowding. I do not know the 2026 dates and will not state them until sourced.

---

## What this does to the plan

The Phase 0 plan was a ~12-week build with the places dataset arriving several phases in. **That
plan is dead.** There are 10 days until boarding and 8 usable working days (31 Jul – 7 Aug), which
means the deadline is not "v1" — it is "something real is on the phone before Sunday the 9th".

Two hard environment facts shape what "real" can mean, both verified in this session rather than
assumed:

1. **This container cannot compile an Android app.** There is a JDK 21 and Gradle, but no Android
   SDK, and the network policy denies `dl.google.com` at the proxy (`403` on `CONNECT`).
   `maven.google.com` merely 301-redirects there, so AGP, AndroidX, Compose, Room and Hilt are all
   unreachable, and there is no aapt2/d8 to run anyway. Maven Central, Gradle's own services and
   `plugins.gradle.org` *are* reachable.
2. **Therefore CI is the compiler.** GitHub Actions runners ship the Android SDK and can reach
   Google's Maven. Every Android build claim in this project comes from a CI run whose log I can
   read, and the installable APK is downloaded from a CI artifact. Nothing will be described as
   "builds" or "tested" on the strength of my having written it.
   - Happy consequence: the `:domain` module was already required to have **zero Android imports**.
     That makes it a plain JVM module, so the money maths, split settlement, category roll-ups,
     budget projection and day-ordering tests **do run here, locally, for real**.
3. **Sideload, don't ship to Play, before the trip.** Play review latency alone could consume the
   remaining 10 days. Pre-trip distribution is a release-signed APK you install directly — release-
   signed, not debug, because this app holds money and location data. The Play track, data-safety
   form and background-location declaration are post-trip work.

The re-cut schedule is in `PHASE-0-ALIGNMENT.md` §9.
