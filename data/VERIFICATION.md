# Places dataset — method and verification report

**Status: in progress. 8 entries, 3 of 21 clusters.** The target is ~180 across ≥18 clusters. This
file exists so the gap between those two numbers is always visible, and so nobody — including me —
can mistake a partial dataset for a finished one.

---

## Method

The rule from the brief is that every factual claim about a real place must be traceable to a source
or visibly marked as unverified, because fabricated safety or timing advice about a real
neighbourhood is a liability rather than a feature. That is enforced three ways:

1. **`tools/validate_places.py` fails the build.** It rejects a coordinate with no OSM provenance, a
   claim field that no source lists in `supports`, an entry with fewer than two `underrated_basis`
   values, marketing adjectives in the prose, `hours.known: true` with no actual hours, a
   `cost.avg_paise` that is null while the band claims otherwise, and `pairs_with` pointing at ids
   that don't exist.
2. **Coordinates are machine-resolved, never typed.** `lat`/`lng` stay null until
   `tools/resolve_geo.py` fills them from a named OSM object (`osm:node/123`). See the constraint
   below for why this is a separate step.
3. **Unverified fields ship empty.** Three of eight entries currently have no price and two have no
   hours. That is the honest state, not an oversight — the validator would have accepted a guessed
   figure just as happily as a real one, so the discipline has to come first.

### The environment constraint that shaped this

The container this was built in cannot reach Nominatim, Overpass, Wikidata or Wikipedia — the
network policy denies them, and `WebFetch` returns 403 on every URL. What works is keyword web
search. So:

- **Timings, closures, addresses and practical rules** are sourced from search results, with
  corroboration across independent write-ups where possible. Two sources agreeing raises confidence
  to `high`; a single listing aggregator caps it at `medium`.
- **Coordinates cannot be verified here at all.** They are therefore not written. Run
  `python3 tools/resolve_geo.py` on any machine with network access and every pin arrives with an
  OSM object id attached. Then hand-check each one: a geocoder returns the neighbourhood centroid
  for a query it half-understands, `precision: "area"` flags that, and the validator warns on it.
- **First-party pages could not be read.** Where a museum or restaurant has its own site, it is
  cited but marked as not directly read. That distinction is in the `note` on each source.

### Rejected on principle

Nothing has been added to reach a count. Specifically dropped during this first pass:

- **Shivaji Park (Dadar)** — genuinely worth including and I could not source a single claim about
  it in this pass. Rather than write it from memory with `sources: []`, it waits. The validator
  requires at least one source, so the file could not have contained it anyway.
- **Matunga's temples** (Asthika Samaj and the Ayyappan temple) — same reason. Real places, no
  verified timings, and temple timings are exactly the field where being wrong wastes a morning.
- **Elephanta and Alibaug** — see the seasonal findings below. Out for this trip, so they are not
  worth researching yet.

---

## Coverage

| Cluster | Entries | high | med | low |
|---|---|---|---|---|
| `matunga` | 5 | 1 | 3 | 1 |
| `dadar` | 2 | 0 | 2 | 0 |
| `byculla-bhendi-bazaar` | 1 | 1 | 0 | 0 |
| **18 other clusters** | **0** | — | — | — |

Field completeness across the 8: geo unresolved 8/8 (blocked on network, resolver written), hours
unknown 2/8, cost unknown 3/8.

Why these clusters first: the inbound train arrives at **Dadar at 05:45**, so Dadar and Matunga are
the only clusters that day one can possibly use, and Byculla is one stop further down the same
Central line with the strongest indoor option in the city for a wet afternoon. Clusters were not
picked for interest; they were picked by the ticket.

---

## Findings that change the trip

Four things surfaced in this pass that a generic dataset would have missed, and each one would have
cost a day.

1. **Café Madras is closed on Mondays — and you arrive on Monday 10 August.** The single most
   commonly recommended South Indian breakfast in Matunga is shut on the one morning you are
   guaranteed to be in Matunga hungry at dawn. Sourced and marked `closed_days_verified: true`.
2. **Ram Ashraya opens at 05:00, and its menu opens in stages.** Idli, upma, tea and coffee from
   05:00; daily specials from about 06:00; full menu around 06:30. A 05:45 arrival at Dadar puts you
   there in the first window — so order idli, not a dosa. This is the day-one breakfast, and it is
   open on Mondays as far as any source shows.
3. **Dr Bhau Daji Lad Museum is closed every Wednesday.** Wednesday 12 August falls inside the trip.
   It closes at 17:30 and costs ₹20 for an Indian adult. It is also the best answer on the list to a
   washed-out afternoon — on the six days it is open.
4. **Elephanta is out.** Ferry services from the Gateway are suspended June to August for sea
   conditions, and July–August high tides are specifically cited as unsafe for the crossing. The
   Alibaug catamaran and RoRo are the same story. Both were on the brief's cluster list as day
   trips; both are removed for a 10–17 August trip. **The Sewri flamingos are also out** — winter
   migrants, roughly November to March. My own Phase 0 wireframe used them as its example row, which
   is a good demonstration of why `season.months` filters rather than merely describes.

Also worth carrying forward: the kaali-peeli night surcharge (25%) ends at **05:00**, so the 05:45
Dadar arrival is just outside it. Base fares are in `data/fares.mumbai.json` with their own
confidence notes — auto ₹26 minimum, taxi ₹31 plus ₹20.66/km, both `medium` because the source's
revision year is ambiguous. Suburban train and BEST fares are deliberately `null`: the brief's own
"₹10 train ticket" example is not a figure I have verified for 2026, so the quick-add preset will
ask you once rather than ship with an invented number.

---

## Still to verify

- **Tide times for 10–17 August 2026.** The Haji Ali causeway submerges at high tide and several
  sea-facing walks are tide-dependent. Real predictions have to be sourced; the field ships empty
  otherwise. No plausible-looking tide table will be written.
- **Independence Day, Saturday 15 August.** Expect restrictions around CSMT, the Gateway, Marine
  Drive and government buildings. Specifics unverified.
- **Monday closures beyond Café Madras**, since both bookend days are Mondays.
- **Any festival dates falling in the window** — Parsi New Year in particular, which would affect
  the Irani cafés. I do not know the 2026 dates and have not guessed them.
- **Whether the Dadar flower market has moved.** Markets relocate; the lane boundaries here are
  unverified.
