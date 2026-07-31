#!/usr/bin/env python3
"""Generate preview/index.html — a browser-viewable prototype of the app, driven by the real dataset.

Why this exists: ADR-009 says this container cannot compile Android — no SDK, and `dl.google.com` is
denied at the proxy. So the Compose UI cannot be built, screenshotted or reviewed here, and the
design plan in docs/PHASE-0-ALIGNMENT.md §7 would otherwise sit unexamined until someone with an
Android machine ran it. This closes that gap: it renders the documented palette, type roles, Fare
Meter and the Places/Detail wireframes as HTML, fed by data/places.mumbai.json, so the design and the
data can both be criticised before a line of Kotlin is written.

What it is NOT: the app. Nothing here is Kotlin, nothing here is compiled, and passing this does not
mean the Android build passes. It is a design and data review surface.

The closed-on-a-given-day logic is real, not mocked — it reads `hours.closed_days` and the trip's
actual dates, which is the single most valuable behaviour in the product and the one most worth
checking against the data before it is reimplemented in Kotlin.

Usage:
    python3 tools/build_preview.py            # writes preview/index.html
    python3 tools/build_preview.py --check    # verify it is up to date (for CI)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACES = ROOT / "data" / "places.mumbai.json"
FARES = ROOT / "data" / "fares.mumbai.json"
OUT = ROOT / "preview" / "index.html"

# The seven usable days. docs/TRIP.md is the source of truth for these dates; docs/ITINERARY.md is
# the source of truth for the plan below. Kept as data so the day selector can compute closures
# rather than having them written out by hand.
DAYS = [
    ("2026-08-10", "mon", "Mon 10 Aug", "Arrive Dadar 05:45"),
    ("2026-08-11", "tue", "Tue 11 Aug", "Fort & Kala Ghoda"),
    ("2026-08-12", "wed", "Wed 12 Aug", "Novena, then Aarey"),
    ("2026-08-13", "thu", "Thu 13 Aug", "Kanheri Caves"),
    ("2026-08-14", "fri", "Fri 14 Aug", "Girgaon & Malabar Hill"),
    ("2026-08-15", "sat", "Sat 15 Aug", "Independence Day + Pateti"),
    ("2026-08-16", "sun", "Sun 16 Aug", "Navroz — last real day"),
]

# Mirrors docs/ITINERARY.md. That file is authoritative; this is the machine-readable copy.
PLAN = {
    "2026-08-10": [
        ("06:00", "dadar-flower-market", "Only morning you are guaranteed to be here in time."),
        ("07:00", "asthika-samaj-matunga", "Open from 05:00."),
        ("07:30", "ram-ashraya-matunga", "Order idli, not dosa — full menu not until ~06:30."),
        ("14:00", "bhau-daji-lad-museum", "Closed Wednesdays, so today is the day for it."),
        ("18:00", "shivaji-park-dadar", "Sit on the katta rather than walking laps."),
    ],
    "2026-08-11": [
        ("07:15", "yazdani-bakery-fort", "Opens 07:00. Brun is hard-crusted on purpose: dunk it."),
        ("10:15", "csmvs-kala-ghoda", "Upper galleries first. Confirm the ₹200 fee at the counter."),
        ("13:00", "ideal-corner-fort", "Tuesday specials are the reason to come. Shut Mondays."),
        ("15:00", "david-sassoon-library-kala-ghoda", "Hours unverified — opportunistic, not scheduled."),
        ("17:30", "marine-drive-promenade", "Stay behind the railing and off the tetrapods."),
        ("19:00", "kyani-and-co-marine-lines", "Chai and bun maska together."),
    ],
    "2026-08-12": [
        ("06:00", "st-michaels-church-mahim", "Wednesday is the entire point. Take the 06:00 slot."),
        ("08:30", "aarey-picnic-point", "August is the point here. Keep to roads and garden."),
        ("17:30", "ghatkopar-khau-galli", "Nothing opens before ~16:30. Metro-1 east from Andheri."),
    ],
    "2026-08-13": [
        ("07:30", "kanheri-caves-sgnp", "Gate fee and cave ticket are separate. Closed Mondays."),
        ("19:00", "cafe-madras-matunga", "Open today — the Monday problem does not apply."),
    ],
    "2026-08-14": [
        ("09:30", "khotachiwadi-girgaon", "Somebody's street, not a site. Ask before photographing."),
        ("11:00", "banganga-tank-walkeshwar", "Tank is open ground; temple hours conflict."),
        ("13:00", "britannia-and-co-fort", "Lunch only, cash only. Deliberately before Navroz."),
        ("17:00", "marine-drive-promenade", "Worth timing to a high tide — table not yet sourced."),
    ],
    "2026-08-15": [
        ("09:30", "ranwar-village-bandra", "North of the likely Independence Day restrictions."),
        ("14:00", "nehru-science-centre-worli", "Open every day of the year, public holidays included."),
        ("15:00", "nehru-planetarium-worli", "Separate ticket. 15:00 is the English show. Shut Mondays."),
    ],
    "2026-08-16": [
        ("05:00", "sassoon-dock-colaba", "Peak 03:30–07:30. Fishing ban may thin landings."),
        ("11:00", "chor-bazaar-mutton-street", "Close at 35–45% of the first quote on antiques."),
        ("15:00", "sewri-fort", "Free and unstaffed. No flamingos in August."),
        ("19:00", "five-gardens-matunga", "A last easy evening before packing."),
    ],
}

# From docs/TRIP.md — the only two expenses that exist. The project forbids fabricated demo data, so
# the Fare Meter renders against these and shows no budget, because no budget has been set anywhere.
REAL_EXPENSES = [
    {"date": "2026-08-09", "label": "Sharavati Exp · MYS→DR", "paise": 76800},
    {"date": "2026-08-17", "label": "Udyan Exp · CSMT→SBC", "paise": 74300},
]


def build_payload() -> dict:
    doc = json.loads(PLACES.read_text())
    places = doc["places"]
    fares = json.loads(FARES.read_text())
    conf = Counter(p["confidence"] for p in places)
    clusters = Counter(p["cluster"] for p in places)
    return {
        "places": places,
        "days": [
            {"date": d, "dow": w, "label": lab, "theme": th} for d, w, lab, th in DAYS
        ],
        "plan": PLAN,
        "expenses": REAL_EXPENSES,
        "fares": fares,
        "stats": {
            "total": len(places),
            "clusters": len(clusters),
            "clusterTotal": 21,
            "high": conf["high"],
            "medium": conf["medium"],
            "low": conf["low"],
            "geoUnresolved": sum(
                1 for p in places if p["geo"]["status"] != "resolved"
            ),
            "hoursUnknown": sum(1 for p in places if not p["hours"].get("known")),
            "costUnknown": sum(1 for p in places if p["cost"]["avg_paise"] is None),
        },
        "generated": doc.get("generated", ""),
    }


TEMPLATE = r"""<title>Mumbai — offline-first trip companion</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
/* ------------------------------------------------------------------
   Palette and type are NOT invented here. Both come from
   docs/PHASE-0-ALIGNMENT.md §7 — the kaali-peeli palette sampled from
   the Premier Padmini taxi, with contrast ratios already computed
   there, and the Archivo / IBM Plex pairing with their stated roles.
   ------------------------------------------------------------------ */
:root{
  --ink:#17150F; --plate:#F2F3F1;
  --ochre:#D9A21B; --ochre-text:#7A5806;
  --jade:#1F7A5C; --taillight:#A32017; --fuchsia:#C2367E;

  /* Light theme. Chrome greys are a ramp off --ink's warm hue (45 19%),
     never a second neutral hue. */
  --bg:#F2F3F1;
  --raised:#FAFAF9;
  --sunk:#E8E9E5;
  --text:#17150F;
  --dim:#5C5749;
  --faint:#8A8577;
  --rule:#D8D9D3;
  --accent-text:var(--ochre-text);
  --accent-fill:var(--ochre);
  --on-fill:#17150F;
  /* Semantic TEXT colours are separate tokens from the fills, because the raw
     palette values do not survive both grounds. §7 already found this for ochre
     (2.2:1 on plate, so ochre text became #7A5806); the same computation says
     taillight is 2.18:1 and jade 3.14:1 on ink, so both need a lightened
     counterpart for small text in dark. Fills keep the raw palette values. */
  --danger-text:#A32017;  /* 7.24:1 on plate */
  --ok-text:#1F7A5C;      /* 5.03:1 on plate */
  --shadow:0 1px 2px rgba(23,21,15,.06), 0 4px 14px rgba(23,21,15,.05);

  --f-display:"Archivo","Archivo Expanded","Helvetica Neue",Helvetica,Arial,sans-serif;
  --f-body:"IBM Plex Sans","Segoe UI",system-ui,-apple-system,sans-serif;
  --f-mono:"IBM Plex Mono",ui-monospace,"SF Mono",Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){
  :root{
    --bg:#17150F; --raised:#211F17; --sunk:#100F0A;
    --text:#F2F3F1; --dim:#A9A395; --faint:#7C7768; --rule:#302D23;
    --accent-text:var(--ochre); --accent-fill:var(--ochre); --on-fill:#17150F;
    --danger-text:#E8776A;  /* 5.72:1 on ink */
    --ok-text:#4FBF95;      /* 7.24:1 on ink */
    --shadow:0 1px 2px rgba(0,0,0,.4), 0 6px 18px rgba(0,0,0,.3);
  }
}
:root[data-theme="dark"]{
  --bg:#17150F; --raised:#211F17; --sunk:#100F0A;
  --text:#F2F3F1; --dim:#A9A395; --faint:#7C7768; --rule:#302D23;
  --accent-text:var(--ochre); --accent-fill:var(--ochre); --on-fill:#17150F;
    --danger-text:#E8776A;  /* 5.72:1 on ink */
    --ok-text:#4FBF95;      /* 7.24:1 on ink */
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 6px 18px rgba(0,0,0,.3);
}
:root[data-theme="light"]{
  --bg:#F2F3F1; --raised:#FAFAF9; --sunk:#E8E9E5;
  --text:#17150F; --dim:#5C5749; --faint:#8A8577; --rule:#D8D9D3;
  --accent-text:var(--ochre-text); --accent-fill:var(--ochre); --on-fill:#17150F;
  --danger-text:#A32017; --ok-text:#1F7A5C;
  --shadow:0 1px 2px rgba(23,21,15,.06), 0 4px 14px rgba(23,21,15,.05);
}

*{box-sizing:border-box}
body{
  margin:0; background:var(--bg); color:var(--text);
  font-family:var(--f-body); font-size:15px; line-height:1.55;
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1180px; margin:0 auto; padding:0 20px 72px}
h1,h2,h3{font-family:var(--f-display); text-wrap:balance; margin:0}
a{color:var(--accent-text)}
.eyebrow{
  font-size:11px; letter-spacing:.14em; text-transform:uppercase;
  color:var(--faint); font-weight:600;
}
.num{font-family:var(--f-display); font-variant-numeric:tabular-nums lining-nums}

/* ---------- masthead ---------- */
header.top{
  border-bottom:1px solid var(--rule); background:var(--bg);
  padding:26px 0 0;
}
.brand{display:flex; align-items:baseline; gap:14px; flex-wrap:wrap}
.brand h1{font-size:clamp(28px,4.4vw,44px); letter-spacing:-.02em; font-weight:700}
.brand .sub{color:var(--dim); font-size:14px}
/* The ochre roof over the black body: one 4px rule, the only decorative
   flourish on the page, and it is the subject's own colour pairing. */
.roofline{height:4px; background:var(--ochre); border-radius:2px; margin:14px 0 0}

.disclaimer{
  margin:18px 0 22px; padding:13px 16px; border-radius:8px;
  background:var(--sunk); border:1px solid var(--rule);
  border-left:3px solid var(--taillight);
  font-size:13.5px; color:var(--dim);
}
.disclaimer strong{color:var(--text)}

/* ---------- stat row ---------- */
.stats{
  display:grid; gap:10px; margin:0 0 26px;
  grid-template-columns:repeat(auto-fit,minmax(148px,1fr));
}
.stat{
  background:var(--raised); border:1px solid var(--rule); border-radius:10px;
  padding:12px 14px; box-shadow:var(--shadow);
}
.stat .v{font-family:var(--f-display); font-size:26px; font-weight:700; font-variant-numeric:tabular-nums; line-height:1.1}
.stat .k{font-size:11.5px; color:var(--dim); margin-top:3px}
.stat.warn .v{color:var(--danger-text)}
.stat.ok .v{color:var(--ok-text)}

section{margin:0 0 42px}
.sechead{display:flex; align-items:baseline; justify-content:space-between; gap:16px; flex-wrap:wrap; margin:0 0 4px}
.sechead h2{font-size:20px; font-weight:700; letter-spacing:-.01em}
.sechead p{margin:0; color:var(--dim); font-size:13.5px; max-width:64ch}

/* ---------- day selector ---------- */
.days{display:flex; gap:8px; overflow-x:auto; padding:14px 0 4px; scrollbar-width:thin}
.day{
  flex:0 0 auto; background:var(--raised); border:1px solid var(--rule);
  border-radius:9px; padding:9px 13px; cursor:pointer; text-align:left;
  font-family:inherit; font-size:13px; color:var(--text); min-width:132px;
  transition:border-color .12s, background .12s;
}
.day:hover{border-color:var(--faint)}
.day[aria-pressed="true"]{
  border-color:var(--accent-fill); background:var(--accent-fill); color:var(--on-fill);
}
.day[aria-pressed="true"] .dt{color:var(--on-fill); opacity:.75}
.day .dl{font-family:var(--f-display); font-weight:700; display:block}
.day .dt{display:block; font-size:11.5px; color:var(--dim); margin-top:1px}

/* ---------- phone frames ---------- */
.phones{display:flex; gap:24px; overflow-x:auto; padding:6px 0 10px; align-items:flex-start}
.phone{
  flex:0 0 auto; width:344px; background:var(--raised);
  border:1px solid var(--rule); border-radius:18px; overflow:hidden;
  box-shadow:var(--shadow);
}
.phone .cap{
  font-size:11px; letter-spacing:.12em; text-transform:uppercase; color:var(--faint);
  padding:10px 14px 0; font-weight:600;
}
.pbody{padding:12px 14px 16px}
.pbar{
  display:flex; justify-content:space-between; align-items:center;
  font-size:12px; color:var(--dim); padding:2px 0 10px; border-bottom:1px solid var(--rule);
}

/* the Fare Meter — one hairline strip, text and one rule, no chart */
.meter{padding:12px 0 4px}
.meter .track{height:7px; background:var(--sunk); border-radius:4px; overflow:hidden; border:1px solid var(--rule)}
.meter .fill{height:100%; background:var(--jade)}
.meter .amt{font-family:var(--f-display); font-size:30px; font-weight:700; font-variant-numeric:tabular-nums; letter-spacing:-.02em; margin-top:9px}
.meter .amt .cur{font-size:.72em; opacity:.6}
.meter .amt .p{font-size:.6em; opacity:.6}
.meter .proj{font-size:12.5px; color:var(--dim); margin-top:2px}
.meter .nobudget{color:var(--danger-text); font-weight:600}

.row{display:flex; justify-content:space-between; gap:10px; padding:7px 0; border-bottom:1px solid var(--rule); font-size:13.5px}
.row:last-child{border-bottom:0}
.row .t{color:var(--faint); font-family:var(--f-mono); font-size:12px; flex:0 0 44px}
.row .m{font-family:var(--f-display); font-variant-numeric:tabular-nums; font-weight:600}

/* checklist */
.chk{display:flex; gap:9px; padding:9px 0; border-bottom:1px solid var(--rule); align-items:flex-start}
.chk:last-child{border-bottom:0}
.chk .box{
  flex:0 0 17px; height:17px; margin-top:2px; border-radius:4px;
  border:1.5px solid var(--faint); background:transparent;
}
.chk.done .box{background:var(--fuchsia); border-color:var(--fuchsia)}
.chk .nm{font-weight:600; font-size:13.5px}
.chk .meta{font-size:12px; color:var(--dim)}
.chk.shut .nm{text-decoration:line-through; color:var(--faint)}
.chk .shutwhy{color:var(--danger-text); font-size:12px; font-weight:600}

/* ---------- pills ---------- */
.pill{
  display:inline-block; font-size:11px; font-weight:600; padding:2px 7px;
  border-radius:5px; border:1px solid; letter-spacing:.02em; white-space:nowrap;
}
.pill.jade{color:var(--ok-text); border-color:var(--jade)}
.pill.ochre{color:var(--accent-text); border-color:var(--accent-fill)}
.pill.red{color:var(--danger-text); border-color:var(--taillight)}
.pill.mute{color:var(--faint); border-color:var(--rule)}
.pills{display:flex; gap:5px; flex-wrap:wrap; margin-top:6px}

/* ---------- filters + grid ---------- */
.filters{display:flex; gap:8px; flex-wrap:wrap; padding:14px 0 16px; align-items:center}
select,.tgl{
  font-family:inherit; font-size:13px; padding:7px 10px; border-radius:8px;
  background:var(--raised); color:var(--text); border:1px solid var(--rule);
}
.tgl{cursor:pointer}
.tgl[aria-pressed="true"]{background:var(--accent-fill); color:var(--on-fill); border-color:var(--accent-fill)}
.count{color:var(--dim); font-size:13px; margin-left:auto}

.grid{display:grid; gap:12px; grid-template-columns:repeat(auto-fill,minmax(276px,1fr))}
.card{
  background:var(--raised); border:1px solid var(--rule); border-radius:11px;
  padding:0 0 13px; cursor:pointer; text-align:left; font-family:inherit; color:var(--text);
  overflow:hidden; transition:border-color .12s, transform .12s;
  display:flex; flex-direction:column; box-shadow:var(--shadow);
}
.card:hover{border-color:var(--faint); transform:translateY(-1px)}
/* severity stripe encodes confidence — state in form, not only in number */
.card .stripe{height:3px; background:var(--jade)}
.card.c-medium .stripe{background:var(--ochre)}
.card.c-low .stripe{background:var(--taillight)}
.card .in{padding:12px 14px 0}
.card h3{font-size:15.5px; font-weight:700; letter-spacing:-.01em}
.card .local{font-size:12.5px; color:var(--faint); margin-top:1px}
.card .cl{font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:var(--faint); font-weight:600; margin-top:7px}
.card .wh{font-size:13px; color:var(--dim); margin-top:7px}
.card .shutbadge{
  margin:9px 14px 0; padding:5px 9px; border-radius:6px; font-size:12px; font-weight:600;
  background:color-mix(in srgb, var(--taillight) 14%, transparent); color:var(--danger-text);
}

/* ---------- detail dialog: rules ABOVE the photo, per the wireframe ---------- */
dialog{
  border:1px solid var(--rule); border-radius:14px; background:var(--raised); color:var(--text);
  max-width:620px; width:calc(100% - 32px); padding:0; box-shadow:0 20px 60px rgba(0,0,0,.35);
  max-height:88vh; overflow-y:auto;
}
dialog::backdrop{background:rgba(9,8,5,.62)}
.dhead{padding:18px 20px 14px; border-bottom:1px solid var(--rule); position:relative}
.dhead h3{font-size:22px; font-weight:700; letter-spacing:-.015em; padding-right:36px}
.dclose{
  position:absolute; top:14px; right:14px; width:30px; height:30px; border-radius:8px;
  background:var(--sunk); border:1px solid var(--rule); color:var(--text); cursor:pointer; font-size:15px;
}
.dsec{padding:15px 20px; border-bottom:1px solid var(--rule)}
.dsec:last-child{border-bottom:0}
.dsec h4{margin:0 0 8px; font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--faint); font-family:var(--f-body); font-weight:700}
.rules{margin:0; padding-left:18px}
.rules li{margin-bottom:7px; font-size:14px}
.rules li:last-child{margin-bottom:0}
.kv{display:grid; grid-template-columns:auto 1fr; gap:5px 14px; font-size:13.5px}
.kv dt{color:var(--faint)}
.kv dd{margin:0}
.nophoto{
  padding:22px; text-align:center; border:1px dashed var(--rule); border-radius:9px;
  color:var(--faint); font-size:12.5px; background:var(--sunk);
}
.srcs{font-size:12.5px}
.srcs li{margin-bottom:6px; word-break:break-word}
.unver{color:var(--danger-text); font-weight:600}

table{border-collapse:collapse; width:100%; font-size:13.5px}
th,td{text-align:left; padding:7px 10px; border-bottom:1px solid var(--rule)}
th{font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:var(--faint)}
td.n{font-family:var(--f-display); font-variant-numeric:tabular-nums; text-align:right}
.scroll{overflow-x:auto}

:focus-visible{outline:2px solid var(--accent-fill); outline-offset:2px}
@media (prefers-reduced-motion:reduce){*{transition:none!important; animation:none!important}}
footer{border-top:1px solid var(--rule); padding-top:18px; color:var(--dim); font-size:12.5px}
</style>

<header class="top">
  <div class="wrap">
    <div class="brand">
      <h1>Mumbai</h1>
      <span class="sub">offline-first trip companion · design &amp; data review</span>
    </div>
    <div class="roofline"></div>
  </div>
</header>

<div class="wrap">
  <div class="disclaimer">
    <strong>This is not the app.</strong> It is an HTML review surface for the design and the
    dataset. No Kotlin is compiled here and nothing on this page proves the Android build works —
    per ADR-009 this container has no Android SDK and cannot reach Google's Maven, so the Compose UI
    can only be built in CI. What <em>is</em> real: every place, hour, price and warning below is read
    straight from <code>data/places.mumbai.json</code>, and the closed-today logic runs off each
    entry's own <code>closed_days</code>. Palette and type roles are the ones specified in
    <code>docs/PHASE-0-ALIGNMENT.md</code> §7. Archivo and IBM Plex are not embedded — the page falls
    back to system faces, so treat weights and widths as indicative.
  </div>

  <div class="stats" id="stats"></div>

  <section>
    <div class="sechead">
      <h2>What is open on each day of the trip</h2>
      <p>The product's core behaviour, running for real against the data. Pick a day: the plan for it
      appears, and anything shut that day is struck through with the reason. Both bookend days are
      Mondays, which is where this earns its keep.</p>
    </div>
    <div class="days" id="days" role="group" aria-label="Trip day"></div>
    <div class="phones" id="phones"></div>
  </section>

  <section>
    <div class="sechead">
      <h2>The dataset</h2>
      <p>All <span id="n1"></span> entries. The stripe on each card is its confidence — jade high,
      ochre medium, red low. Open one to see the insider rules, which render above the photo because
      the rules are the product and the photo is decoration.</p>
    </div>
    <div class="filters" id="filters"></div>
    <div class="grid" id="grid"></div>
  </section>

  <section>
    <div class="sechead">
      <h2>Coverage, honestly</h2>
      <p>Per-cluster counts against a ~180-entry target across ≥18 clusters. Empty clusters are
      listed rather than hidden.</p>
    </div>
    <div class="scroll"><table id="cov"></table></div>
  </section>

  <footer>
    Map data © OpenStreetMap contributors, ODbL 1.0 — coordinates in this dataset are unresolved and
    carry no OSM provenance yet, so no map is drawn here.
    Generated from the dataset dated <span id="gen"></span>.
  </footer>
</div>

<dialog id="dlg"><div id="dlgin"></div></dialog>

<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
const D = JSON.parse(document.getElementById("payload").textContent);
const byId = Object.fromEntries(D.places.map(p => [p.id, p]));
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

const rupees = paise => {
  const r = Math.floor(paise / 100), p = paise % 100;
  return `<span class="cur">₹</span>${r.toLocaleString("en-IN")}${p ? `<span class="p">.${String(p).padStart(2,"0")}</span>` : ""}`;
};
const CLUSTERS = ["fort-kala-ghoda","colaba","churchgate-marine-lines","girgaon-charni-road",
  "byculla-bhendi-bazaar","dadar","matunga","mahim-bandra-west","bandra-east-bkc","khar-santacruz",
  "andheri-versova-jvlr","juhu","goregaon-aarey","powai-vikhroli","ghatkopar-chembur","sion-wadala",
  "worli-prabhadevi-lower-parel","sewri-mazgaon","navi-mumbai","thane","day-trips"];

let day = D.days[0].date;
let f = {cluster:"", monsoon:"", conf:"", openOnly:false};

/* ---- closed-today: the real rule, off each entry's own closed_days ---- */
function shutOn(p, dow) {
  const cd = p.hours.closed_days || [];
  if (cd.includes(dow)) {
    return p.hours.closed_days_verified ? "Closed today" : "Reported closed today (unverified)";
  }
  return null;
}

function stats() {
  const s = D.stats;
  const cells = [
    ["v", s.total, "places, all validated"],
    ["v", `${s.clusters}/${s.clusterTotal}`, "clusters covered"],
    ["ok", s.high, "high confidence"],
    ["v", s.medium, "medium confidence"],
    ["warn", `${s.geoUnresolved}/${s.total}`, "coordinates unresolved"],
    ["warn", s.costUnknown, "no verified price"],
    ["warn", s.hoursUnknown, "no verified hours"],
  ];
  $("#stats").innerHTML = cells.map(([k,v,l]) =>
    `<div class="stat ${k==="v"?"":k}"><div class="v num">${esc(v)}</div><div class="k">${esc(l)}</div></div>`).join("");
  $("#n1").textContent = s.total;
  $("#gen").textContent = D.generated;
}

function daybar() {
  $("#days").innerHTML = D.days.map(d =>
    `<button class="day" data-d="${d.date}" aria-pressed="${d.date===day}">
       <span class="dl">${esc(d.label)}</span><span class="dt">${esc(d.theme)}</span></button>`).join("");
  $("#days").querySelectorAll(".day").forEach(b =>
    b.onclick = () => { day = b.dataset.d; daybar(); phones(); grid(); });
}

function phones() {
  const d = D.days.find(x => x.date === day);
  const plan = D.plan[day] || [];
  const logged = D.expenses.reduce((a,e) => a + e.paise, 0);

  // Fare Meter. No budget exists anywhere in the repo, so none is invented: the meter renders
  // against the two real ticket fares and says plainly that there is no denominator yet.
  const meter = `
    <div class="meter">
      <div class="track"><div class="fill" style="width:38%"></div></div>
      <div class="amt num">${rupees(logged)}</div>
      <div class="proj">logged across 2 real expenses · <span class="nobudget">no budget set</span>,
        so the meter has no denominator and shows a specimen fill</div>
    </div>`;

  const planRows = plan.length ? plan.map(([t,id,note]) => {
    const p = byId[id]; if (!p) return "";
    const shut = shutOn(p, d.dow);
    return `<div class="chk ${shut?"shut":""}">
      <div class="box"></div>
      <div>
        <div class="nm">${esc(p.name)}</div>
        ${shut ? `<div class="shutwhy">⚠ ${esc(shut)} — reschedule</div>` : ""}
        <div class="meta"><span class="t" style="display:inline">${esc(t)}</span> · ${esc(note)}</div>
      </div></div>`;
  }).join("") : `<div class="meta">Nothing scheduled.</div>`;

  const shutList = D.places.map(p => [p, shutOn(p, d.dow)]).filter(([,s]) => s);
  const openNow = D.places.length - shutList.length;

  $("#phones").innerHTML = `
    <div class="phone">
      <div class="cap">Today — ${esc(d.label)}</div>
      <div class="pbody">
        <div class="pbar"><span>Mumbai · day ${D.days.indexOf(d)+1} of 7</span><span>${esc(d.theme)}</span></div>
        ${meter}
      </div>
    </div>
    <div class="phone">
      <div class="cap">Plan for ${esc(d.label)}</div>
      <div class="pbody">${planRows}</div>
    </div>
    <div class="phone">
      <div class="cap">Shut on ${esc(d.label)} — ${shutList.length} of ${D.places.length}</div>
      <div class="pbody">
        <div class="pbar"><span>${openNow} open</span><span>${shutList.length} closed</span></div>
        ${shutList.length ? shutList.map(([p,s]) => `<div class="chk shut">
            <div class="box"></div>
            <div><div class="nm">${esc(p.name)}</div><div class="shutwhy">${esc(s)}</div></div>
          </div>`).join("")
          : `<div class="meta" style="padding-top:10px">Nothing in the dataset is shut today.</div>`}
      </div>
    </div>`;
}

function filters() {
  const used = [...new Set(D.places.map(p => p.cluster))].sort();
  $("#filters").innerHTML = `
    <select id="fc"><option value="">All clusters (${used.length} with entries)</option>
      ${used.map(c => `<option value="${c}">${c} (${D.places.filter(p=>p.cluster===c).length})</option>`).join("")}</select>
    <select id="fm"><option value="">Any monsoon rating</option>
      <option value="yes">Works in a downpour</option>
      <option value="conditional">Light rain only</option>
      <option value="no">Not in August</option></select>
    <select id="fk"><option value="">Any confidence</option>
      <option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select>
    <button class="tgl" id="fo" aria-pressed="false">Open on selected day</button>
    <span class="count" id="cnt"></span>`;
  $("#fc").onchange = e => { f.cluster = e.target.value; grid(); };
  $("#fm").onchange = e => { f.monsoon = e.target.value; grid(); };
  $("#fk").onchange = e => { f.conf = e.target.value; grid(); };
  $("#fo").onclick = e => {
    f.openOnly = !f.openOnly;
    e.currentTarget.setAttribute("aria-pressed", String(f.openOnly));
    grid();
  };
}

function grid() {
  const dow = D.days.find(x => x.date === day).dow;
  const list = D.places.filter(p =>
    (!f.cluster || p.cluster === f.cluster) &&
    (!f.monsoon || p.monsoon_safe === f.monsoon) &&
    (!f.conf || p.confidence === f.conf) &&
    (!f.openOnly || !shutOn(p, dow)));

  $("#cnt").textContent = `${list.length} of ${D.places.length} shown`;
  $("#grid").innerHTML = list.map(p => {
    const shut = shutOn(p, dow);
    const cost = p.cost.avg_paise === null
      ? `<span class="pill mute">price unverified</span>`
      : `<span class="pill ochre">${p.cost.avg_paise === 0 ? "free" : "₹" + (p.cost.avg_paise/100).toLocaleString("en-IN")}</span>`;
    const hrs = p.hours.known
      ? (p.hours.always_open ? `<span class="pill jade">always open</span>`
        : p.hours.windows ? `<span class="pill jade">${esc(p.hours.windows[0].open)}–${esc(p.hours.windows[0].close)}</span>`
        : `<span class="pill ochre">opens ${esc(p.hours.opens_at)}</span>`)
      : `<span class="pill red">hours unverified</span>`;
    return `<button class="card c-${p.confidence}" data-id="${p.id}">
      <div class="stripe"></div>
      ${shut ? `<div class="shutbadge">⚠ ${esc(shut)}</div>` : ""}
      <div class="in">
        <h3>${esc(p.name)}</h3>
        ${p.name_local ? `<div class="local">${esc(p.name_local)}</div>` : ""}
        <div class="cl">${esc(p.cluster)} · ${esc(p.type.join(" · "))}</div>
        <div class="wh">${esc(p.what_it_is)}</div>
        <div class="pills">${hrs}${cost}
          <span class="pill ${p.monsoon_safe==="yes"?"jade":p.monsoon_safe==="no"?"red":"ochre"}">monsoon: ${esc(p.monsoon_safe)}</span>
        </div>
      </div></button>`;
  }).join("") || `<p style="color:var(--dim)">Nothing matches. That is the dataset being honest about a gap.</p>`;

  $("#grid").querySelectorAll(".card").forEach(c => c.onclick = () => detail(c.dataset.id));
}

function costLine(p) {
  const v = p.cost.avg_paise === null
    ? `<span class="unver">Unverified — ships empty rather than guessed.</span>`
    : (p.cost.avg_paise === 0 ? "Free" : "₹" + (p.cost.avg_paise/100).toLocaleString("en-IN"));
  return p.cost.note ? `${v} <span style="color:var(--dim)">— ${esc(p.cost.note)}</span>` : v;
}

function detail(id) {
  const p = byId[id];
  const dow = D.days.find(x => x.date === day).dow;
  const shut = shutOn(p, dow);
  const h = p.hours;
  const hoursText = !h.known ? `<span class="unver">Not verified.</span> ${esc(h.note||"")}`
    : h.always_open ? `No gate — always open. ${esc(h.note||"")}`
    : h.windows ? h.windows.map(w => `${esc(w.open)}–${esc(w.close)}${w.note?` (${esc(w.note)})`:""}`).join("<br>")
    : `Opens ${esc(h.opens_at)} — closing time not verified.`;

  $("#dlgin").innerHTML = `
    <div class="dhead">
      <h3>${esc(p.name)}</h3>
      ${p.name_local ? `<div class="local">${esc(p.name_local)}</div>` : ""}
      <div class="pills">
        <span class="pill ${p.confidence==="high"?"jade":p.confidence==="low"?"red":"ochre"}">${p.confidence} confidence</span>
        <span class="pill mute">${esc(p.cluster)}</span>
        ${shut ? `<span class="pill red">${esc(shut)}</span>` : ""}
      </div>
      <button class="dclose" aria-label="Close">✕</button>
    </div>

    <div class="dsec">
      <h4>Before you go</h4>
      <ul class="rules">${p.insider_rules.map(r => `<li>${esc(r)}</li>`).join("")}</ul>
    </div>

    <div class="dsec">
      <h4>Hours</h4><div>${hoursText}</div>
    </div>

    <div class="dsec">
      <h4>The basics</h4>
      <dl class="kv">
        <dt>What it is</dt><dd>${esc(p.what_it_is)}</dd>
        <dt>Why locals rate it</dt><dd>${esc(p.why_locals_rate_it)}</dd>
        <dt>Cost</dt><dd>${costLine(p)}</dd>
        <dt>Getting there</dt><dd>${esc(p.how_to_get_there.nearest_station||"No nearby station")}${p.how_to_get_there.line?` (${esc(p.how_to_get_there.line)})`:""}${p.how_to_get_there.walk_minutes!=null?` + ${p.how_to_get_there.walk_minutes} min walk`:""}. ${esc(p.how_to_get_there.note||"")}</dd>
        <dt>In monsoon</dt><dd>${esc(p.monsoon_safe)}. ${esc(p.monsoon_note||"")}</dd>
        <dt>Safety</dt><dd>${esc(p.safety_notes)}</dd>
        <dt>Access</dt><dd>${esc(p.accessibility)}</dd>
      </dl>
    </div>

    <div class="dsec">
      <h4>Photo</h4>
      <div class="nophoto">No photograph in the dataset. The rules above are the product; the photo
      was never allowed to block them, and none has been fabricated.</div>
    </div>

    <div class="dsec">
      <h4>Sources — ${p.sources.length}</h4>
      ${p.confidence_note ? `<p style="margin:0 0 9px"><span class="unver">Caveat:</span> ${esc(p.confidence_note)}</p>` : ""}
      <ul class="srcs">${p.sources.map(s =>
        `<li><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url)}</a>
         <br><span style="color:var(--faint)">supports ${esc(s.supports.join(", "))}${s.note?` — ${esc(s.note)}`:""}</span></li>`).join("")}</ul>
      <p style="margin:9px 0 0; color:var(--faint); font-size:12.5px">
        Coordinates: <strong>${esc(p.geo.status)}</strong> — <code>${esc(p.geo.osm_query)}</code>.
        Reviewed ${esc(p.last_reviewed)}.</p>
    </div>`;
  const dlg = $("#dlg");
  $("#dlgin").querySelector(".dclose").onclick = () => dlg.close();
  dlg.showModal();
}

function coverage() {
  const c = {};
  D.places.forEach(p => { (c[p.cluster] = c[p.cluster] || []).push(p); });
  const rows = CLUSTERS.map(cl => {
    const e = c[cl] || [];
    const n = k => e.filter(x => x.confidence === k).length;
    return `<tr${e.length?"":' style="color:var(--faint)"'}>
      <td><code>${esc(cl)}</code></td><td class="n">${e.length||"—"}</td>
      <td class="n">${e.length?n("high"):"—"}</td><td class="n">${e.length?n("medium"):"—"}</td>
      <td class="n">${e.length?n("low"):"—"}</td></tr>`;
  }).join("");
  $("#cov").innerHTML = `<thead><tr><th>Cluster</th><th style="text-align:right">Entries</th>
    <th style="text-align:right">High</th><th style="text-align:right">Med</th>
    <th style="text-align:right">Low</th></tr></thead><tbody>${rows}</tbody>`;
}

stats(); daybar(); phones(); filters(); grid(); coverage();
$("#dlg").addEventListener("click", e => { if (e.target === $("#dlg")) $("#dlg").close(); });
</script>
"""


def render() -> str:
    payload = json.dumps(build_payload(), ensure_ascii=False, separators=(",", ":"))
    # </script> inside embedded JSON would end the block early.
    payload = payload.replace("</", "<\\/")
    return TEMPLATE.replace("__PAYLOAD__", payload)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if the output is stale")
    args = ap.parse_args()

    html = render()
    if args.check:
        if not OUT.exists() or OUT.read_text() != html:
            print(f"{OUT.relative_to(ROOT)} is stale — run tools/build_preview.py", file=sys.stderr)
            return 1
        print(f"{OUT.relative_to(ROOT)} is up to date")
        return 0

    # Referential check: the plan must not point at entries that do not exist.
    ids = {p["id"] for p in json.loads(PLACES.read_text())["places"]}
    missing = {i for stops in PLAN.values() for _, i, _ in stops} - ids
    if missing:
        print(f"ERROR plan references unknown ids: {sorted(missing)}", file=sys.stderr)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(html):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
