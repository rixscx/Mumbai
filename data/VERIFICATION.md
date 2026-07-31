# Places dataset — method and verification report

**Status: in progress. 29 entries, 13 of 21 clusters.** The target is ~180 across ≥18 clusters. This
file exists so the gap between those two numbers is always visible, and so nobody — including me —
can mistake a partial dataset for a finished one.

The bar agreed at Phase 0 sign-off was **the confidence distribution, not the raw count**. That
distribution is below, and it is currently weighted to `medium` for a specific and fixable reason:
this container cannot read a single first-party page.

---

## Method

The rule from the brief is that every factual claim about a real place must be traceable to a source
or visibly marked as unverified, because fabricated safety or timing advice about a real
neighbourhood is a liability rather than a feature. That is enforced four ways:

1. **`tools/validate_places.py` fails the build.** It rejects a coordinate with no OSM provenance, a
   claim field that no source lists in `supports`, an entry with fewer than two `underrated_basis`
   values, marketing adjectives in the prose, `hours.known: true` with no actual hours, a
   `cost.avg_paise` that is null while the band claims otherwise, and `pairs_with` pointing at ids
   that don't exist.
2. **Confidence has to be earned, not asserted.** `check_confidence_is_earned` rejects `high` on
   fewer than two distinct source hosts, and rejects `high` when *every* source is a listing
   aggregator — aggregators copy each other, so two of them agreeing is one source. Until this check
   existed, the "two independent sources" rule below was a promise in a document, which is the same
   shape of problem as trusting good intentions about opening hours. It is now executable.
3. **Coordinates are machine-resolved, never typed.** `lat`/`lng` stay null until
   `tools/resolve_geo.py` fills them from a named OSM object (`osm:node/123`). See the constraint
   below for why this is a separate step.
4. **Unverified fields ship empty.** Ten of twenty-nine entries have no price and three have no
   hours. That is the honest state, not an oversight — the validator would have accepted a guessed
   figure just as happily as a real one, so the discipline has to come first.

`tools/merge_entries.py` ingests a research pass. It refuses to merge on duplicate ids and reports
or prunes dangling `pairs_with` references, printing every removal — a quietly dropped reference is
what makes an itinerary feature look broken for no visible reason.

### The environment constraint that shaped this

The container this was built in cannot reach Nominatim, Overpass, Wikidata or Wikipedia — the
network policy denies them, and **`WebFetch` returns HTTP 403 on every URL**, re-confirmed this pass
against the Bhau Daji Lad museum's own site. What works is keyword web search. So:

- **Timings, closures, addresses and practical rules** are sourced from search results, with
  corroboration across independent write-ups where possible. Two independent sources agreeing raises
  confidence to `high`; a single listing aggregator caps it at `medium`.
- **Coordinates cannot be verified here at all.** They are therefore not written. Run
  `python3 tools/resolve_geo.py` on any machine with network access and every pin arrives with an
  OSM object id attached. Then hand-check each one: a geocoder returns the neighbourhood centroid
  for a query it half-understands, `precision: "area"` flags that, and the validator warns on it.
- **First-party pages could not be read.** Where a museum or restaurant has its own site it is
  cited but explicitly marked as not directly read — see `asthika-samaj-matunga`, whose own site is
  cited with that caveat in the source `note`. **This single constraint is why the distribution is
  medium-weighted.** Roughly a dozen entries would move to `high` on an afternoon with working
  first-party fetches, with no new research at all.

### Rejected on principle

Nothing has been added to reach a count. Two gaps the first pass recorded have now been closed
honestly — **Shivaji Park** and **Matunga's Asthika Samaj**, both previously dropped for having no
sourceable claim, are now in with three sources each. **Elephanta and Alibaug** remain out: monsoon
ferry suspensions make them unavailable for this trip, so researching them is wasted effort.

Still deliberately absent: **Matunga's Ayyappan temple** (real place, no verified timings, and temple
timings are exactly the field where being wrong wastes a morning) and the whole **Bandra eating**
category, which Day 6 of the itinerary visibly suffers for. Neither is invented to fill the hole.

Also still absent by choice: the **Nehru Planetarium's show durations**. Start times and languages are
sourced; how long a show runs is not, so the entry's `hours.windows` uses a one-hour assumption that
its own note flags as an assumption rather than a fact.

---

## Coverage

| Cluster | Entries | high | med | low |
|---|---|---|---|---|
| `matunga` | 6 | 1 | 4 | 1 |
| `fort-kala-ghoda` | 5 | 1 | 4 | 0 |
| `dadar` | 3 | 1 | 2 | 0 |
| `byculla-bhendi-bazaar` | 2 | 1 | 1 | 0 |
| `churchgate-marine-lines` | 2 | 0 | 2 | 0 |
| `girgaon-charni-road` | 2 | 1 | 1 | 0 |
| `colaba` | 1 | 0 | 1 | 0 |
| `day-trips` | 1 | 0 | 1 | 0 |
| `ghatkopar-chembur` | 1 | 0 | 1 | 0 |
| `goregaon-aarey` | 1 | 0 | 1 | 0 |
| `mahim-bandra-west` | 2 | 1 | 1 | 0 |
| `worli-prabhadevi-lower-parel` | 2 | 1 | 1 | 0 |
| `sewri-mazgaon` | 1 | 0 | 1 | 0 |
| **8 other clusters** | **0** | — | — | — |
| **Total** | **29** | **7** | **21** | **1** |

At zero: `bandra-east-bkc`, `khar-santacruz`, `andheri-versova-jvlr`, `juhu`, `powai-vikhroli`,
`sion-wadala`, `navi-mumbai`, `thane`.

Field completeness across the 29: **geo unresolved 29/29** (blocked on network, resolver written),
hours unknown 3/29, cost unknown 10/29.

Why these clusters first: the inbound train arrives at **Dadar at 05:45**, so Dadar and Matunga are
the only clusters day one can possibly use; Byculla is one stop further down the same Central line
with the strongest indoor option in the city for a wet afternoon; and Fort/Kala Ghoda is both the
last morning (CSMT) and the most rain-proof day available. Clusters were not picked for interest.
They were picked by the ticket and by the weather.

**The two most consequential gaps from the last pass are now closed.**
`worli-prabhadevi-lower-parel` has the Nehru Science Centre and Nehru Planetarium — the answer to a
washed-out afternoon — and `mahim-bandra-west` has St Michael's, whose Wednesday novena is the
strongest single entry in the dataset. The most consequential remaining gap is **Bandra eating**:
there is not one sourced place to eat in Bandra, Khar or Santacruz, which visibly thins Day 6.

---

## Findings that change the trip

Nine things have surfaced across these passes that a generic dataset would have missed, and each one
would have cost a day.

1. **Café Madras is closed on Mondays — and you arrive on Monday 10 August.** The single most
   commonly recommended South Indian breakfast in Matunga is shut on the one morning you are
   guaranteed to be in Matunga hungry at dawn. Sourced, `closed_days_verified: true`.
2. **Ram Ashraya opens at 05:00, and its menu opens in stages.** Idli, upma, tea and coffee from
   05:00; daily specials from about 06:00; full menu around 06:30. A 05:45 arrival at Dadar puts you
   there in the first window — so **order idli, not a dosa**. Open on Mondays as far as any source
   shows. This is the day-one breakfast.
3. **The Monday problem is bigger than one restaurant.** `ideal-corner-fort`,
   `kanheri-caves-sgnp` and `nehru-planetarium-worli` are *also* shut Mondays. Both trip bookend days
   are Mondays, so four of the best entries in the dataset are unavailable on two of the nine days.
   The one confirmed counterweight: **`nehru-science-centre-worli` opens every day of the year,
   public holidays included**, which makes it the reliable fallback for both Mondays *and* for
   Independence Day. The Monday-closure list is certainly still incomplete.
4. **Dr Bhau Daji Lad Museum is closed every Wednesday**, and Wednesday 12 August falls inside the
   trip. Re-verified this pass at **₹20 Indian adult, 10:00–17:30** — some aggregators claim ₹50 and
   an 18:00 close, and that is the noise, not the signal. It remains the best answer to a
   washed-out afternoon on the six days it is open.
5. **Elephanta is out, and so are the Sewri flamingos.** Ferries from the Gateway are suspended
   June–August for sea conditions; the Alibaug catamaran and RoRo are the same story. The flamingos
   are Nov–Mar migrants, so `sewri-fort` is in the dataset for the fort and the harbour view, with
   `season.note` saying plainly that the birds are absent in August.
6. **Marine Drive in monsoon is a hazard, not just a view.** High tide against a south-west wind
   sends waves over the sea wall; police restrict promenade access during red alerts; people are
   swept off the tetrapods and killed every monsoon. `marine-drive-promenade` carries that in
   `safety_notes`, and it is the most dangerous entry in the dataset.
7. **Aarey is the one entry August improves.** Green, high birdlife, and a genuine monsoon
   destination rather than a monsoon compromise — which is why Day 3 of the itinerary is built on it.
8. **Ganesh Chaturthi 2026 falls on 14 September — outside the trip.** This was the single largest
   risk to the whole plan: had it landed inside 10–16 August, Lalbaug, the immersion processions and
   city-wide transport would have dictated the entire week. Janmashtami (4 Sep) and Dahi Handi
   (5 Sep) are out too. Resolved, and the relief is worth stating plainly.
9. **Parsi New Year IS inside the trip, on the last two days — Pateti Sat 15 Aug, Navroz Sun 16 Aug.**
   Indian Parsis follow the Shahanshahi calendar, which ignores leap years and so runs about 200 days
   behind the global Nowruz. Six entries in this dataset are Parsi or Irani houses, and **no source
   states whether any of them opens on Navroz**. The itinerary therefore puts every Parsi meal on
   11–14 August, before the holiday, so that a closure costs nothing. This is the finding most likely
   to save the trip a wasted journey, and it is one phone call from being settled.

And one weekly event that lands inside the window: **Mahim's St Michael's novena runs every
Wednesday**, roughly 06:00–21:30 in five languages, at a reported 40,000–50,000 attendees a week.
Wednesday 12 August is in the trip — and it is also the day Bhau Daji Lad shuts, so the weakest day
in the plan now has its strongest anchor.

Also worth carrying forward: the kaali-peeli night surcharge (25%) ends at **05:00**, so the 05:45
Dadar arrival is just outside it. Base fares are in `data/fares.mumbai.json` with their own
confidence notes — auto ₹26 minimum, taxi ₹31 plus ₹20.66/km, both `medium` because the source's
revision year is ambiguous. Suburban train and BEST fares are deliberately `null`: the brief's own
"₹10 train ticket" example is not a figure I have verified for 2026, so the quick-add preset will
ask you once rather than ship with an invented number.

### Source conflicts recorded rather than hidden

Four entries carry an unresolved conflict in `confidence_note` instead of a silently-picked winner:

- **`chor-bazaar-mutton-street`** — the Friday position is contradictory: closed for Jumma with an
  afternoon reopening, or closed but for a dawn trade-only market. Marked closed as the conservative
  reading, and the itinerary simply avoids Friday.
- **`banganga-tank-walkeshwar`** — three different sets of temple hours across three sources. The
  *tank* is open ground, which resolves it for planning; no specific temple is promised.
- **`kanheri-caves-sgnp`** — sources disagree on whether Monday closes the caves or the whole park.
  Monday is out either way; which it is remains unknown, as does the park gate fee.
- **`ranwar-village-bandra`** — founding dated to 1716 by one source and "roughly 400 years" by
  another, so the prose asserts no date at all.

---

## Still to verify

Ordered by how much damage each would do if left unresolved.

- **Whether the six Parsi and Irani houses open on Navroz, Sun 16 August — now the highest-value
  open question in the project, and the cheapest to close.** Britannia, Ideal Corner, Kyani, Koolar,
  Mani's and Yazdani: no source states a Navroz policy for any of them. The available evidence points
  to *open but very busy* — one Navroz round-up advises reserving at Ideal Corner — but that is a
  recommendation, not an opening hour, and a Parsi family holiday is exactly the day a family-run
  Parsi restaurant shuts. **A phone call each settles it.** Until then the itinerary schedules no
  Parsi food on 15–16 August.
  - Resolved this pass, and no longer open: **Ganesh Chaturthi is 14 Sep 2026, Janmashtami 4 Sep,
    Dahi Handi 5 Sep — all outside the trip.** Pateti is Sat 15 Aug and Navroz Sun 16 Aug, inside it.
- **Tide times for 10–17 August 2026.** The Haji Ali causeway submerges at high tide, Marine Drive's
  overtopping is a high-tide phenomenon, and Sewri's mudflats are tide-dependent. Searching this pass
  surfaced the right services — tide-forecast.com, tides4fishing.com, tidetime.org,
  tidetimesglobal.com — but no actual August 2026 predictions, and this container cannot fetch a page
  to read a table. **No tide figures exist anywhere in this repository and none will be invented.**
- **Independence Day, Saturday 15 August.** Restrictions around CSMT, the Gateway, Marine Drive and
  government buildings are expected but unconfirmed. The itinerary routes around it rather than
  betting on it. Also unknown: whether museums close on national holidays, which would affect
  `csmvs-kala-ghoda`.
- **Monday closures beyond the four now known** (Café Madras, Ideal Corner, Kanheri, Nehru
  Planetarium). Both bookend days are Mondays and the list is certainly incomplete.
- **The monsoon fishing ban's effect on Sassoon Dock in mid-August.** `sassoon-dock-colaba` is built
  on accounts of a busy dock; if the west-coast ban thins landings, a 05:00 start could arrive to a
  near-empty quay. Unsourced, and flagged in the entry's own `season.note`.
- **Whether photography at Sassoon Dock is prohibited or merely restricted** — sources differ, and
  naval facilities adjoin the site.
- **Whether the Dadar flower market has moved**, and its exact operating hours. Markets relocate;
  the lane boundaries here are unverified, and this is the first stop on day one.
- **CSMVS's ₹200 Indian-adult fee**, which is aggregator-sourced and an order of magnitude above the
  neighbouring museum's ₹20. Confirm at the counter.
- **Yazdani Bakery's closing time and Sunday closure.** Widely described as Sunday-closed; not
  confirmed by anything I could read.
- **David Sassoon Library's opening hours** — entirely unverified, which is why the itinerary treats
  it as opportunistic rather than scheduled.
