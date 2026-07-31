/* ============================================================================
   Mumbai — offline-first trip companion.

   Three layers of truth about a place, never collapsed into one:

     1. CURATED   places.json — sourced, validated by tools/validate_places.py.
                  Read-only at runtime. Never overwritten by anything below.
     2. YOURS     your edits, kept on this device. Shown as "your edit" so a
                  correction you typed is never mistaken for a sourced fact.
     3. LIVE      optional, when online and you have supplied a Google Places
                  key. Shown ALONGSIDE the curated value, and when the two
                  disagree the disagreement is surfaced rather than resolved —
                  Google is a third party, not an authority over sourced data.

   Money is integer paise everywhere. There is no float arithmetic on money in
   this file; that is the one rule most likely to be quietly broken later.

   Everything you enter lives in IndexedDB on this device. There is no server.
   ============================================================================ */
"use strict";

const TZ = "Asia/Kolkata";
const DOW = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
const LIVE_TTL_MS = 6 * 60 * 60 * 1000;

/* ------------------------------------------------------------------ utils */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/** Money → display. Paise are punctuation, not the number (§7). */
function money(paise, opts = {}) {
  const neg = paise < 0, v = Math.abs(paise | 0);
  const r = Math.floor(v / 100), p = v % 100;
  const body = r.toLocaleString("en-IN");
  const cur = opts.plain ? "₹" : '<span class="cur">₹</span>';
  const dec = p ? (opts.plain ? `.${String(p).padStart(2, "0")}`
    : `<span class="p">.${String(p).padStart(2, "0")}</span>`) : "";
  return `${neg ? "−" : ""}${cur}${body}${dec}`;
}
const rupeesPlain = paise => money(paise, { plain: true });

/** Parse a user-typed rupee amount into integer paise without float drift. */
function toPaise(str) {
  const m = String(str).trim().match(/^(\d*)(?:[.,](\d{0,2}))?$/);
  if (!m || (!m[1] && !m[2])) return null;
  const rupees = m[1] ? parseInt(m[1], 10) : 0;
  const paise = m[2] ? parseInt(m[2].padEnd(2, "0"), 10) : 0;
  return rupees * 100 + paise;
}

/** "Now" in the trip's zone. The device zone must never own the day boundary. */
function istParts(d = new Date()) {
  const f = new Intl.DateTimeFormat("en-GB", {
    timeZone: TZ, weekday: "short", year: "numeric", month: "2-digit",
    day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
  });
  const o = {};
  for (const { type, value } of f.formatToParts(d)) o[type] = value;
  const hour = o.hour === "24" ? "00" : o.hour;
  return {
    date: `${o.year}-${o.month}-${o.day}`,
    hhmm: `${hour}:${o.minute}`,
    dow: o.weekday.toLowerCase().slice(0, 3),
    mins: parseInt(hour, 10) * 60 + parseInt(o.minute, 10),
  };
}
const dowOf = iso => DOW[new Date(iso + "T12:00:00Z").getUTCDay()];
const prettyDate = iso => new Date(iso + "T12:00:00Z").toLocaleDateString("en-GB",
  { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });
const toMin = hhmm => { const [h, m] = hhmm.split(":").map(Number); return h * 60 + m; };
function ago(ts) {
  const s = Math.max(0, (Date.now() - ts) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

/* ------------------------------------------------------------------ store */
/* A thin IndexedDB wrapper. IndexedDB rather than localStorage because this
   holds financial records: no 5 MB cliff, no whole-blob rewrite per keystroke,
   and real transactions. */
const DB = {
  db: null,
  async open() {
    this.db = await new Promise((res, rej) => {
      const r = indexedDB.open("mumbai", 1);
      r.onupgradeneeded = e => {
        const db = e.target.result;
        const ex = db.createObjectStore("expenses", { keyPath: "id" });
        ex.createIndex("date", "date");
        db.createObjectStore("settings");
        db.createObjectStore("categories", { keyPath: "id" });
        db.createObjectStore("visits");          // placeId -> ISO timestamp
        db.createObjectStore("overrides", { keyPath: "id" }); // your edits to a place
        db.createObjectStore("live");            // placeId -> live hours snapshot
      };
      r.onsuccess = () => res(r.result);
      r.onerror = () => rej(r.error);
    });
  },
  tx(store, mode = "readonly") { return this.db.transaction(store, mode).objectStore(store); },
  req(r) { return new Promise((res, rej) => { r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); }); },
  all(store) { return this.req(this.tx(store).getAll()); },
  get(store, k) { return this.req(this.tx(store).get(k)); },
  put(store, v, k) { return this.req(this.tx(store, "readwrite").put(v, k)); },
  del(store, k) { return this.req(this.tx(store, "readwrite").delete(k)); },
  async clear(store) { return this.req(this.tx(store, "readwrite").clear()); },
  async keyval(store) {
    const s = this.tx(store);
    const keys = await this.req(s.getAllKeys());
    const vals = await this.req(this.tx(store).getAll());
    return Object.fromEntries(keys.map((k, i) => [k, vals[i]]));
  },
};

/* ------------------------------------------------------------------ state */
const S = {
  places: [], byId: {}, trip: null,
  expenses: [], categories: [], catById: {},
  visits: {}, overrides: {}, live: {},
  settings: {
    budgetPaise: null, liveProvider: "none", googleKey: "", proxyUrl: "",
    seeded: false, autoLive: true,
  },
};

async function loadAll() {
  const [places, trip] = await Promise.all([
    fetch("places.json").then(r => r.json()),
    fetch("trip.json").then(r => r.json()),
  ]);
  S.places = places.places;
  S.licence = places.licence;
  S.generated = places.generated;
  S.byId = Object.fromEntries(S.places.map(p => [p.id, p]));
  S.trip = trip;

  await DB.open();
  const saved = await DB.get("settings", "app");
  if (saved) Object.assign(S.settings, saved);

  let cats = await DB.all("categories");
  if (!cats.length) {                       // first run: plant the seed taxonomy
    for (const c of trip.categories) await DB.put("categories", c);
    cats = await DB.all("categories");
  }
  S.categories = cats;
  S.catById = Object.fromEntries(cats.map(c => [c.id, c]));

  S.expenses = (await DB.all("expenses")).sort((a, b) =>
    b.date.localeCompare(a.date) || b.id.localeCompare(a.id));
  S.visits = await DB.keyval("visits");
  S.live = await DB.keyval("live");
  S.overrides = Object.fromEntries((await DB.all("overrides")).map(o => [o.id, o]));
}
const saveSettings = () => DB.put("settings", { ...S.settings }, "app");

/* --------------------------------------------------------- category helpers */
function catPath(id) {
  const out = [];
  let c = S.catById[id], guard = 0;
  while (c && guard++ < 12) { out.unshift(c.name); c = c.parentId ? S.catById[c.parentId] : null; }
  return out;
}
const catLabel = id => catPath(id).join(" ▸ ") || "Uncategorised";
function catDepth(id) {
  let d = 0, c = S.catById[id], guard = 0;
  while (c && c.parentId && guard++ < 12) { d++; c = S.catById[c.parentId]; }
  return d;
}
function descendants(id) {
  const out = [id];
  for (let i = 0; i < out.length; i++)
    for (const c of S.categories) if (c.parentId === out[i]) out.push(c.id);
  return out;
}
/** Roll-up: a parent's total includes every descendant. ADR-004's recursive CTE, in JS. */
const rollup = id => {
  const set = new Set(descendants(id));
  return S.expenses.reduce((a, e) => a + (set.has(e.categoryId) ? e.paise : 0), 0);
};

/* ------------------------------------------------------- the hours engine */
/* This is the part worth getting right: "is it open, at this actual time of
   day, in Mumbai". It runs entirely offline off the curated hours, so it works
   in a tunnel. The optional live layer never replaces it. */
function effectiveHours(p) {
  const o = S.overrides[p.id];
  return o && o.hours ? { ...o.hours, _mine: true } : p.hours;
}

function openState(p, when = new Date()) {
  const h = effectiveHours(p);
  const t = istParts(when);
  const mine = !!h._mine;

  if (!h.known) return { state: "unknown", label: "Hours not verified", mine };
  if (h.always_open) return { state: "open", label: "Always open — no gate", mine };

  const closed = h.closed_days || [];
  if (closed.includes(t.dow)) {
    return {
      state: "closed", mine,
      label: h.closed_days_verified ? "Closed today" : "Reported closed today",
      sub: h.closed_days_verified ? null : "closure unverified",
    };
  }

  if (h.windows && h.windows.length) {
    for (const w of h.windows) {
      const a = toMin(w.open), b = toMin(w.close);
      if (t.mins >= a && t.mins < b) {
        const left = b - t.mins;
        return {
          state: "open", mine,
          label: left <= 60 ? `Closing in ${left}m` : `Open until ${w.close}`,
          sub: w.note || null,
        };
      }
    }
    const next = h.windows.map(w => toMin(w.open)).filter(m => m > t.mins).sort((x, y) => x - y)[0];
    return {
      state: "closed", mine,
      label: next != null
        ? `Opens ${String(Math.floor(next / 60)).padStart(2, "0")}:${String(next % 60).padStart(2, "0")}`
        : "Closed for today",
    };
  }

  if (h.opens_at) {
    const a = toMin(h.opens_at);
    return t.mins >= a
      ? { state: "likely-open", label: `Open since ${h.opens_at}`, sub: "closing time unverified", mine }
      : { state: "closed", label: `Opens ${h.opens_at}`, mine };
  }
  return { state: "unknown", label: "Hours not verified", mine };
}

/** Shut for the whole of that weekday — the closure that actually wrecks a plan.
    Distinct from openState(), which answers "right now" and will call a dawn fish market
    closed at noon, correctly but uselessly for day-level planning. */
function closedAllDay(p, dow) {
  const h = effectiveHours(p);
  if (!h.known || h.always_open) return null;
  if (!(h.closed_days || []).includes(dow)) return null;
  return {
    label: h.closed_days_verified ? "Closed all day" : "Reported closed all day",
    verified: !!h.closed_days_verified,
  };
}

const STATE_PILL = {
  open: "ok", "likely-open": "warn", closed: "bad", unknown: "mute",
};

/* --------------------------------------------------------- live hours (opt-in) */
/* Google Places API (New). The key is stored on this device and sent only to
   Google (or to a proxy you nominate). Two honest caveats, both surfaced in
   Settings rather than buried:
     - browser calls need CORS; if your project blocks them, set a proxy URL.
     - this path could NOT be tested in the container this app was built in,
       where all outbound HTTP is denied. It is written, not verified. */
const Live = {
  configured() { return S.settings.liveProvider === "google" && !!S.settings.googleKey; },
  stale(id) {
    const l = S.live[id];
    return !l || (Date.now() - l.fetchedAt) > LIVE_TTL_MS;
  },
  async fetchOne(p) {
    if (!this.configured() || !navigator.onLine) return null;
    const body = JSON.stringify({
      textQuery: p.geo.osm_query, maxResultCount: 1, languageCode: "en",
    });
    const fields = [
      "places.id", "places.displayName", "places.formattedAddress",
      "places.currentOpeningHours.openNow",
      "places.currentOpeningHours.weekdayDescriptions",
      "places.regularOpeningHours.weekdayDescriptions",
    ].join(",");
    const base = S.settings.proxyUrl?.trim() || "https://places.googleapis.com/v1/places:searchText";
    try {
      const r = await fetch(base, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Goog-Api-Key": S.settings.googleKey,
          "X-Goog-FieldMask": fields,
        },
        body,
      });
      if (!r.ok) throw new Error(`Google returned ${r.status}`);
      const j = await r.json();
      const g = j.places && j.places[0];
      if (!g) throw new Error("no match for this place");
      const snap = {
        fetchedAt: Date.now(),
        name: g.displayName?.text || null,
        addr: g.formattedAddress || null,
        openNow: g.currentOpeningHours?.openNow ?? null,
        week: g.currentOpeningHours?.weekdayDescriptions
          || g.regularOpeningHours?.weekdayDescriptions || null,
        error: null,
      };
      S.live[p.id] = snap;
      await DB.put("live", snap, p.id);
      return snap;
    } catch (e) {
      const snap = { fetchedAt: Date.now(), error: e.message || String(e) };
      S.live[p.id] = snap;
      await DB.put("live", snap, p.id);
      return snap;
    }
  },
  /** Refresh a batch, oldest first, politely — never the whole dataset at once. */
  async refresh(ids, limit = 6) {
    if (!this.configured() || !navigator.onLine) return 0;
    const todo = ids.filter(id => this.stale(id)).slice(0, limit);
    let n = 0;
    for (const id of todo) { if (await this.fetchOne(S.byId[id])) n++; }
    return n;
  },
  /** Does Google disagree with our computed state? Worth saying out loud. */
  conflict(p) {
    const l = S.live[p.id];
    if (!l || l.error || l.openNow == null) return null;
    const st = openState(p).state;
    if (st === "unknown") return null;
    const oursOpen = st === "open" || st === "likely-open";
    return oursOpen === l.openNow ? null : (l.openNow ? "google-open" : "google-closed");
  },
};

/* ------------------------------------------------------------------ chrome */
function toast(msg, ms = 2200) {
  const t = $("#toast");
  t.textContent = msg; t.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { t.hidden = true; }, ms);
}
function setHead(title, sub = "") {
  $("#pageTitle").textContent = title;
  $("#pageSub").textContent = sub;
  document.title = title === "Today" ? "Mumbai" : `${title} · Mumbai`;
}
function syncNet() {
  const d = $("#offlineDot");
  const off = !navigator.onLine;
  d.dataset.off = off ? "1" : "0";
  d.title = off ? "Offline — everything here still works" : "Online";
}

/* ------------------------------------------------------------------ router */
const ROUTES = [
  [/^\/$/, () => pageToday()],
  [/^\/expenses$/, () => pageExpenses()],
  [/^\/places$/, () => pagePlaces()],
  [/^\/place\/([a-z0-9-]+)$/, m => pagePlace(m[1])],
  [/^\/itinerary$/, () => pageItinerary()],
  [/^\/trip$/, () => pageTrip()],
  [/^\/settings$/, () => pageSettings()],
];

function route() {
  const path = (location.hash.replace(/^#/, "") || "/");
  for (const [re, fn] of ROUTES) {
    const m = path.match(re);
    if (m) {
      const tabRoot = "/" + (path.split("/")[1] || "");
      $$(".tabs a").forEach(a =>
        a.toggleAttribute("aria-current",
          a.dataset.tab === path || (path.startsWith("/place/") && a.dataset.tab === "/places")));
      $$(".tabs a").forEach(a => {
        if (a.hasAttribute("aria-current")) a.setAttribute("aria-current", "page");
      });
      $("#main").scrollTop = 0;
      window.scrollTo(0, 0);
      fn(m);
      return;
    }
  }
  location.hash = "#/";
}

/* =========================================================== PAGE: today */
function budgetLine() {
  const b = S.settings.budgetPaise;
  const today = istParts().date;
  const spentToday = S.expenses.filter(e => e.date === today).reduce((a, e) => a + e.paise, 0);
  const total = S.expenses.reduce((a, e) => a + e.paise, 0);

  if (!b) {
    return `<div class="meter">
      <div class="meter-amt num">${money(total)}</div>
      <p class="meter-proj">logged in total across ${S.expenses.length} ${S.expenses.length === 1 ? "expense" : "expenses"}.
        <span class="meter-warn">No budget set</span>, so there is nothing to measure against —
        <a href="#/trip">set one</a> and this becomes a meter.</p>
    </div>`;
  }

  // Days remaining counts today as usable. Projection is arithmetic on real
  // numbers only; if nothing is spent yet there is nothing to project.
  const days = S.trip.days.map(d => d.date);
  const idx = days.indexOf(today);
  const left = b - total;
  const remainingDays = idx === -1 ? 0 : days.length - idx;
  const perDay = remainingDays > 0 ? Math.floor(left / remainingDays) : null;
  const pct = Math.max(0, Math.min(100, Math.round((total / b) * 100)));
  const over = left < 0;

  let proj;
  if (over) {
    proj = `<span class="meter-warn">Over budget by ${rupeesPlain(-left)}.</span>`;
  } else if (remainingDays > 0 && total > 0 && idx >= 0) {
    const rate = Math.floor(total / (idx + 1));
    const runsOutIn = rate > 0 ? Math.floor(left / rate) : null;
    proj = `<b>${rupeesPlain(perDay)}/day</b> for the ${remainingDays} ${remainingDays === 1 ? "day" : "days"} left`;
    if (runsOutIn != null && runsOutIn < remainingDays) {
      const d = days[Math.min(days.length - 1, idx + runsOutIn)];
      proj += ` · <span class="meter-warn">at this rate you run out ${prettyDate(d)}</span>`;
    }
  } else {
    proj = remainingDays > 0
      ? `<b>${rupeesPlain(perDay)}/day</b> across ${remainingDays} days · nothing spent yet, so no projection`
      : `Outside the trip dates.`;
  }

  return `<div class="meter">
    <div class="meter-track"><div class="meter-fill" style="width:${pct}%" data-over="${over ? 1 : 0}"></div></div>
    <div class="meter-amt num">${money(left)}</div>
    <p class="meter-proj">left of ${rupeesPlain(b)} · ${rupeesPlain(spentToday)} today · ${proj}</p>
  </div>`;
}

function expenseRow(e) {
  const p = e.placeId ? S.byId[e.placeId] : null;
  return `<button class="item" data-edit="${e.id}">
    <div class="item-main">
      <div class="item-t">${esc(e.note || catPath(e.categoryId).slice(-1)[0] || "Expense")}</div>
      <div class="item-s">${esc(catLabel(e.categoryId))}${p ? ` · ${esc(p.name)}` : ""} · ${esc(e.method)}</div>
    </div>
    <div class="item-amt num">${money(e.paise)}</div>
  </button>`;
}

function pageToday() {
  const t = istParts();
  const day = S.trip.days.find(d => d.date === t.date);
  setHead("Today", day ? `${day.label} · ${day.theme}` : `${prettyDate(t.date)} · outside the trip dates`);

  const mine = S.expenses.filter(e => e.date === t.date);
  const plan = (S.trip.plan[t.date] || []);

  // "Open right now" — the offline hours engine, at the actual current IST time.
  const openNow = S.places
    .map(p => ({ p, st: openState(p) }))
    .filter(x => x.st.state === "open" || x.st.state === "likely-open");

  $("#main").innerHTML = `<div class="stack">
    <section class="card">${budgetLine()}</section>

    <section class="card">
      <div class="daybar"><span>Today's spending</span>
        <span class="n">${mine.length} · ${rupeesPlain(mine.reduce((a, e) => a + e.paise, 0))}</span></div>
      ${mine.length ? `<div class="list">${mine.map(expenseRow).join("")}</div>`
        : `<p class="center-note tiny">Nothing logged today. Tap <b>+</b> to add the first one —
           four taps for a ₹140 auto.</p>`}
    </section>

    ${plan.length ? `<section class="card">
      <div class="daybar"><span>Plan for ${esc(day.label)}</span><span class="n">${plan.length} stops</span></div>
      <div class="list">${plan.map(([time, id, note]) => {
        const p = S.byId[id]; if (!p) return "";
        const st = openState(p);
        return `<a class="item" href="#/place/${p.id}">
          <span class="item-time">${esc(time)}</span>
          <span class="item-main">
            <span class="item-t">${esc(p.name)}</span>
            <span class="item-s">${esc(note)}</span>
          </span>
          <span class="pill ${STATE_PILL[st.state]}">${esc(st.label)}</span>
        </a>`;
      }).join("")}</div>
    </section>` : ""}

    <section class="card">
      <div class="daybar"><span>Open right now</span><span class="n">${openNow.length} of ${S.places.length}</span></div>
      ${openNow.length ? `<div class="list">${openNow.slice(0, 8).map(({ p, st }) =>
        `<a class="item" href="#/place/${p.id}">
           <span class="item-main">
             <span class="item-t">${esc(p.name)}</span>
             <span class="item-s">${esc(p.cluster)} · ${esc(st.label)}</span>
           </span>
           <span class="pill ${STATE_PILL[st.state]}">${st.state === "open" ? "open" : "likely"}</span>
         </a>`).join("")}</div>
        ${openNow.length > 8 ? `<p class="tiny muted" style="padding:12px 16px 14px">
           and ${openNow.length - 8} more — <a href="#/places">see all places</a></p>` : ""}`
        : `<p class="center-note tiny">Nothing in the dataset is open at ${esc(t.hhmm)} IST.</p>`}
    </section>
  </div>`;
}

/* ======================================================== PAGE: expenses */
let expFilter = { cat: "", from: "", to: "" };

function pageExpenses() {
  const total = S.expenses.reduce((a, e) => a + e.paise, 0);
  setHead("Money", `${S.expenses.length} ${S.expenses.length === 1 ? "expense" : "expenses"} · ${rupeesPlain(total)}`);

  let list = S.expenses;
  if (expFilter.cat) {
    const set = new Set(descendants(expFilter.cat));
    list = list.filter(e => set.has(e.categoryId));
  }
  if (expFilter.from) list = list.filter(e => e.date >= expFilter.from);
  if (expFilter.to) list = list.filter(e => e.date <= expFilter.to);

  const byDate = {};
  for (const e of list) (byDate[e.date] = byDate[e.date] || []).push(e);
  const dates = Object.keys(byDate).sort((a, b) => b.localeCompare(a));
  const roots = S.categories.filter(c => !c.parentId);

  $("#main").innerHTML = `<div class="stack">
    <div class="chips">
      <button class="chip" data-cf="" aria-pressed="${!expFilter.cat}">All</button>
      ${roots.map(c => `<button class="chip" data-cf="${c.id}"
        aria-pressed="${expFilter.cat === c.id}">${esc(c.name)}</button>`).join("")}
    </div>

    <div class="grid2">
      <div class="field"><label for="xFrom">From</label>
        <input id="xFrom" type="date" value="${esc(expFilter.from)}"></div>
      <div class="field"><label for="xTo">To</label>
        <input id="xTo" type="date" value="${esc(expFilter.to)}"></div>
    </div>

    ${list.length !== S.expenses.length
      ? `<p class="tiny muted">Showing ${list.length} of ${S.expenses.length} ·
         ${rupeesPlain(list.reduce((a, e) => a + e.paise, 0))}
         · <a href="#" data-clearf>clear filters</a></p>` : ""}

    ${dates.length ? dates.map(d => `<section class="card">
      <div class="daybar"><span>${esc(prettyDate(d))}</span>
        <span class="n">${rupeesPlain(byDate[d].reduce((a, e) => a + e.paise, 0))}</span></div>
      <div class="list">${byDate[d].map(expenseRow).join("")}</div>
    </section>`).join("")
      : `<section class="card"><p class="center-note">
          ${S.expenses.length ? "Nothing matches these filters." : `No expenses yet — nothing here is
          pre-filled. Tap <b>+</b> to add your own, or import the two real train fares from
          <a href="#/settings">Settings</a>.`}</p></section>`}
  </div>`;

  $$("[data-cf]").forEach(b => b.onclick = () => { expFilter.cat = b.dataset.cf; pageExpenses(); });
  $("#xFrom").onchange = e => { expFilter.from = e.target.value; pageExpenses(); };
  $("#xTo").onchange = e => { expFilter.to = e.target.value; pageExpenses(); };
  const cf = $("[data-clearf]");
  if (cf) cf.onclick = ev => { ev.preventDefault(); expFilter = { cat: "", from: "", to: "" }; pageExpenses(); };
}

/* ========================================================== PAGE: places */
let plFilter = { cluster: "", monsoon: "", openOnly: false, unvisited: false, q: "" };

function pagePlaces() {
  const visited = Object.keys(S.visits).length;
  setHead("Places", `${visited} of ${S.places.length} checked off`);

  let list = S.places.filter(p =>
    (!plFilter.cluster || p.cluster === plFilter.cluster) &&
    (!plFilter.monsoon || p.monsoon_safe === plFilter.monsoon) &&
    (!plFilter.unvisited || !S.visits[p.id]) &&
    (!plFilter.q || (p.name + " " + p.what_it_is + " " + p.cluster)
      .toLowerCase().includes(plFilter.q.toLowerCase())));

  if (plFilter.openOnly) {
    list = list.filter(p => ["open", "likely-open"].includes(openState(p).state));
  }

  const clusters = [...new Set(S.places.map(p => p.cluster))].sort();
  const groups = {};
  for (const p of list) (groups[p.cluster] = groups[p.cluster] || []).push(p);

  $("#main").innerHTML = `<div class="stack">
    <div class="field">
      <input id="plq" type="search" placeholder="Search places" value="${esc(plFilter.q)}"
        aria-label="Search places">
    </div>
    <div class="chips">
      <button class="chip" data-pf="openOnly" aria-pressed="${plFilter.openOnly}">Open now</button>
      <button class="chip" data-pf="unvisited" aria-pressed="${plFilter.unvisited}">Unvisited</button>
      <button class="chip" data-mf="yes" aria-pressed="${plFilter.monsoon === "yes"}">Rain-proof</button>
      <button class="chip" data-mf="conditional" aria-pressed="${plFilter.monsoon === "conditional"}">Light rain</button>
    </div>
    <div class="field">
      <select id="plc" aria-label="Cluster">
        <option value="">All ${clusters.length} areas with entries</option>
        ${clusters.map(c => `<option value="${c}" ${plFilter.cluster === c ? "selected" : ""}>
          ${esc(c)} (${S.places.filter(p => p.cluster === c).length})</option>`).join("")}
      </select>
    </div>

    <p class="tiny muted">${list.length} shown${Live.configured()
      ? ` · live hours on` : ` · live hours off (<a href="#/settings">enable</a>)`}</p>

    ${Object.keys(groups).length ? Object.keys(groups).sort().map(cl => {
      const g = groups[cl];
      const done = g.filter(p => S.visits[p.id]).length;
      return `<section class="card">
        <div class="daybar"><span>${esc(cl)}</span><span class="n">${done}/${g.length} ✓</span></div>
        <div class="list">${g.map(p => {
          const st = openState(p);
          const conflict = Live.conflict(p);
          return `<div class="item" role="group">
            <button class="tick-btn" data-visit="${p.id}" aria-label="Mark ${esc(p.name)} visited"
              aria-pressed="${!!S.visits[p.id]}" style="all:unset;cursor:pointer">
              <span class="tick">
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 13l4 4L19 7"/></svg>
              </span>
            </button>
            <a class="item-main" href="#/place/${p.id}">
              <span class="item-t">${esc(p.name)}</span>
              <span class="item-s">${esc(st.label)}${st.mine ? " · your edit" : ""}${
                p.cost.avg_paise == null ? " · price unverified"
                  : p.cost.avg_paise === 0 ? " · free" : ` · ${rupeesPlain(p.cost.avg_paise)}`}</span>
            </a>
            <span class="pills">
              ${conflict ? `<span class="pill live">Google differs</span>` : ""}
              <span class="pill ${STATE_PILL[st.state]}">${st.state === "likely-open" ? "likely" : st.state}</span>
            </span>
          </div>`;
        }).join("")}</div>
      </section>`;
    }).join("") : `<section class="card"><p class="center-note">Nothing matches. That is the dataset
      being honest about a gap rather than inventing a result.</p></section>`}
  </div>`;

  const q = $("#plq");
  q.oninput = () => { plFilter.q = q.value; clearTimeout(q._t); q._t = setTimeout(pagePlaces, 220); };
  $("#plc").onchange = e => { plFilter.cluster = e.target.value; pagePlaces(); };
  $$("[data-pf]").forEach(b => b.onclick = () => { plFilter[b.dataset.pf] = !plFilter[b.dataset.pf]; pagePlaces(); });
  $$("[data-mf]").forEach(b => b.onclick = () => {
    plFilter.monsoon = plFilter.monsoon === b.dataset.mf ? "" : b.dataset.mf; pagePlaces();
  });
  $$("[data-visit]").forEach(b => b.onclick = async () => {
    const id = b.dataset.visit;
    if (S.visits[id]) { delete S.visits[id]; await DB.del("visits", id); }
    else { S.visits[id] = new Date().toISOString(); await DB.put("visits", S.visits[id], id); }
    pagePlaces();
  });

  if (S.settings.autoLive && Live.configured() && navigator.onLine) {
    Live.refresh(list.slice(0, 6).map(p => p.id)).then(n => { if (n) pagePlaces(); });
  }
}

/* ==================================================== PAGE: place detail */
function pagePlace(id) {
  const p = S.byId[id];
  if (!p) { location.hash = "#/places"; return; }
  setHead(p.name, `${p.cluster} · ${p.type.join(" · ")}`);

  const st = openState(p);
  const h = effectiveHours(p);
  const l = S.live[p.id];
  const conflict = Live.conflict(p);
  const spentHere = S.expenses.filter(e => e.placeId === p.id);

  const hoursBody = !h.known
    ? `<span class="unver">Not verified.</span> ${esc(h.note || "")}`
    : h.always_open ? `No gate — always open. ${esc(h.note || "")}`
      : h.windows ? h.windows.map(w =>
        `${esc(w.open)}–${esc(w.close)}${w.note ? ` <span class="muted">(${esc(w.note)})</span>` : ""}`).join("<br>")
        : `Opens ${esc(h.opens_at)} — <span class="unver">closing time not verified</span>.`;

  $("#main").innerHTML = `<div class="stack">
    <section class="card">
      <div class="hero">
        <h2>${esc(p.name)}</h2>
        ${p.name_local ? `<div class="local">${esc(p.name_local)}</div>` : ""}
        <div class="pills" style="margin-top:10px">
          <span class="pill ${STATE_PILL[st.state]}">${esc(st.label)}</span>
          <span class="pill ${p.confidence === "high" ? "ok" : p.confidence === "low" ? "bad" : "warn"}">${p.confidence} confidence</span>
          ${st.mine ? `<span class="pill live">your edit</span>` : ""}
        </div>
      </div>

      <div class="sec">
        <h3>Before you go</h3>
        <ul class="rules">${p.insider_rules.map(r => `<li>${esc(r)}</li>`).join("")}</ul>
      </div>

      <div class="sec">
        <h3>Hours ${st.mine ? "— your edit" : "— curated"}</h3>
        <div>${hoursBody}</div>
        ${h.closed_days?.length ? `<p class="tiny muted" style="margin:8px 0 0">
          Closed: ${h.closed_days.join(", ")}${h.closed_days_verified ? "" : " (unverified)"}</p>` : ""}
        <div class="btnrow" style="margin-top:12px">
          <button class="btn ghost" data-edith>${st.mine ? "Edit again" : "Correct these hours"}</button>
          ${st.mine ? `<button class="btn ghost danger" data-resetch>Reset to curated</button>` : ""}
        </div>
      </div>

      <div class="sec">
        <h3>Live from Google</h3>
        ${!Live.configured()
          ? `<p class="tiny muted" style="margin:0">Off. Turn it on in
             <a href="#/settings">Settings</a> with your own Places API key and this shows what
             Google says right now, next to the curated hours — never instead of them.</p>`
          : !l ? `<p class="tiny muted" style="margin:0">Not fetched yet.</p>`
          : l.error ? `<div class="callout bad">Google lookup failed: ${esc(l.error)}
              <span class="muted">· checked ${esc(ago(l.fetchedAt))}</span></div>`
          : `<dl class="kv">
              <dt>Open now</dt><dd>${l.openNow == null ? "not reported"
                : l.openNow ? `<b style="color:var(--ok-text)">Yes</b>` : `<b style="color:var(--danger-text)">No</b>`}</dd>
              ${l.name ? `<dt>Matched</dt><dd>${esc(l.name)}${l.addr ? `<br><span class="muted tiny">${esc(l.addr)}</span>` : ""}</dd>` : ""}
              <dt>Checked</dt><dd>${esc(ago(l.fetchedAt))}</dd>
            </dl>
            ${l.week ? `<p class="tiny muted" style="margin:8px 0 0">${l.week.map(esc).join("<br>")}</p>` : ""}`}
        ${conflict ? `<div class="callout bad" style="margin-top:10px">
          <b>Google disagrees with the curated hours.</b> We compute
          <b>${esc(st.label.toLowerCase())}</b>; Google says
          <b>${conflict === "google-open" ? "open" : "closed"}</b>.
          Neither is automatically right — Google's data is crowd-edited, ours is sourced and dated.
          Ring ahead if it matters.</div>` : ""}
        ${Live.configured() ? `<div class="btnrow" style="margin-top:12px">
          <button class="btn ghost" data-live>${navigator.onLine ? "Check Google now" : "Offline — cannot check"}</button>
        </div>` : ""}
      </div>

      <div class="sec">
        <h3>The basics</h3>
        <dl class="kv">
          <dt>What it is</dt><dd>${esc(p.what_it_is)}</dd>
          <dt>Why locals rate it</dt><dd>${esc(p.why_locals_rate_it)}</dd>
          <dt>Cost</dt><dd>${p.cost.avg_paise == null
            ? `<span class="unver">Unverified</span> — ships empty rather than guessed.`
            : p.cost.avg_paise === 0 ? "Free" : rupeesPlain(p.cost.avg_paise)}
            ${p.cost.note ? `<br><span class="muted tiny">${esc(p.cost.note)}</span>` : ""}</dd>
          <dt>Getting there</dt><dd>${esc(p.how_to_get_there.nearest_station || "No nearby station")}${
            p.how_to_get_there.line ? ` (${esc(p.how_to_get_there.line)})` : ""}${
            p.how_to_get_there.walk_minutes != null ? ` + ${p.how_to_get_there.walk_minutes} min walk` : ""}
            ${p.how_to_get_there.note ? `<br><span class="muted tiny">${esc(p.how_to_get_there.note)}</span>` : ""}</dd>
          <dt>In monsoon</dt><dd>${esc(p.monsoon_safe)}${p.monsoon_note ? ` — ${esc(p.monsoon_note)}` : ""}</dd>
          <dt>Safety</dt><dd>${esc(p.safety_notes)}</dd>
          <dt>Access</dt><dd>${esc(p.accessibility)}</dd>
        </dl>
      </div>

      <div class="sec">
        <h3>Spent here</h3>
        ${spentHere.length
          ? `<div class="list">${spentHere.map(expenseRow).join("")}</div>`
          : `<p class="tiny muted" style="margin:0">Nothing logged against this place yet.</p>`}
        <div class="btnrow" style="margin-top:12px">
          <button class="btn primary" data-logat>Log what you spent here</button>
          <button class="btn ghost" data-nav>Open in maps</button>
        </div>
      </div>

      <div class="sec">
        <h3>Sources — ${p.sources.length}</h3>
        ${p.confidence_note ? `<p class="tiny" style="margin:0 0 8px">
          <span class="unver">Caveat:</span> ${esc(p.confidence_note)}</p>` : ""}
        <ul class="srclist">${p.sources.map(s =>
          `<li><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(new URL(s.url).hostname)}</a>
           <span class="muted">— supports ${esc(s.supports.join(", "))}</span></li>`).join("")}</ul>
        <p class="tiny muted" style="margin:8px 0 0">Coordinates <b>${esc(p.geo.status)}</b> —
          no OSM provenance yet, so no pin is drawn. Reviewed ${esc(p.last_reviewed)}.</p>
      </div>
    </section>
  </div>`;

  $("[data-logat]").onclick = () => openSheet(null, { placeId: p.id, categoryId: guessCat(p) });
  $("[data-nav]").onclick = () => {
    // No coordinates exist, so hand the query string to whatever maps app is installed.
    window.open(`geo:0,0?q=${encodeURIComponent(p.geo.osm_query)}`, "_blank");
  };
  $("[data-edith]").onclick = () => editHours(p);
  const rc = $("[data-resetch]");
  if (rc) rc.onclick = async () => {
    delete S.overrides[p.id]; await DB.del("overrides", p.id);
    toast("Reset to the curated hours"); pagePlace(id);
  };
  const lv = $("[data-live]");
  if (lv) lv.onclick = async () => {
    if (!navigator.onLine) return toast("Still offline");
    lv.disabled = true; lv.textContent = "Checking…";
    await Live.fetchOne(p); pagePlace(id);
  };
}

/** Best-guess category for a place, so "log what you spent here" pre-selects. */
function guessCat(p) {
  if (p.type.includes("eat")) return "food-restaurant";
  if (p.type.includes("market") || p.type.includes("shop")) return "shopping";
  if (p.cost.avg_paise) return "entry";
  return "other";
}

/** Correcting hours writes to YOUR layer, never over the curated dataset. */
async function editHours(p) {
  const cur = effectiveHours(p);
  const openv = cur.windows?.[0]?.open || cur.opens_at || "";
  const closev = cur.windows?.[0]?.close || "";
  const a = prompt(
    `Opening time for ${p.name} (HH:MM, blank to clear).\n\n` +
    `This is saved as YOUR correction on this device. The curated, sourced value is kept and you ` +
    `can reset to it at any time.`, openv);
  if (a === null) return;
  const b = prompt(`Closing time (HH:MM). Leave blank if you only know when it opens.`, closev);
  if (b === null) return;

  const ok = s => /^([01]\d|2[0-3]):[0-5]\d$/.test(s);
  const cd = prompt(`Days it is closed, comma separated (mon,tue,wed,thu,fri,sat,sun). Blank for none.`,
    (cur.closed_days || []).join(","));
  if (cd === null) return;
  const closed = cd.split(",").map(s => s.trim().toLowerCase()).filter(s => DOW.includes(s));

  let hours;
  if (ok(a) && ok(b) && toMin(a) < toMin(b)) {
    hours = { known: true, windows: [{ open: a, close: b }], closed_days: closed, closed_days_verified: true };
  } else if (ok(a)) {
    hours = { known: true, opens_at: a, closed_days: closed, closed_days_verified: true };
  } else if (!a && !b) {
    hours = { known: false, note: "Cleared by you on this device.", closed_days: closed };
  } else {
    return toast("Times must be HH:MM, and opening before closing");
  }

  const rec = { id: p.id, hours, editedAt: new Date().toISOString() };
  S.overrides[p.id] = rec;
  await DB.put("overrides", rec);
  toast("Saved as your correction");
  pagePlace(p.id);
}

/* ======================================================= PAGE: itinerary */
let itDay = null;

function pageItinerary() {
  const t = istParts();
  if (!itDay) itDay = S.trip.days.some(d => d.date === t.date) ? t.date : S.trip.days[0].date;
  const d = S.trip.days.find(x => x.date === itDay);
  setHead("Days", `${d.label} · ${d.theme}`);

  const dow = dowOf(itDay);
  const at = new Date(`${itDay}T12:00:00+05:30`);       // midday, for a day-level view
  const plan = S.trip.plan[itDay] || [];
  const shut = S.places.map(p => ({ p, cl: closedAllDay(p, dow) })).filter(x => x.cl);

  $("#main").innerHTML = `<div class="stack">
    <div class="seg">${S.trip.days.map(x => `<button data-day="${x.date}"
      aria-pressed="${x.date === itDay}">
      <span class="l">${esc(x.label)}</span><span class="s">${esc(x.theme)}</span></button>`).join("")}</div>

    <section class="card">
      <div class="daybar"><span>Plan · ${esc(d.label)}</span><span class="n">${plan.length} stops</span></div>
      ${plan.length ? `<div class="list">${plan.map(([time, id, note]) => {
        const p = S.byId[id]; if (!p) return "";
        const cl = closedAllDay(p, dow);
        const bad = !!cl;
        const st = cl || openState(p, at);
        return `<a class="item" href="#/place/${p.id}">
          <span class="item-time">${esc(time)}</span>
          <span class="item-main">
            <span class="item-t" ${bad ? 'style="text-decoration:line-through;color:var(--faint)"' : ""}>${esc(p.name)}</span>
            <span class="item-s">${bad ? `<b style="color:var(--danger-text)">${esc(st.label)} — reschedule</b>` : esc(note)}</span>
          </span>
          ${S.visits[p.id] ? `<span class="pill ok">done</span>` : ""}
        </a>`;
      }).join("")}</div>` : `<p class="center-note tiny">Nothing planned.</p>`}
    </section>

    <section class="card">
      <div class="daybar"><span>Shut on ${esc(d.label)}</span>
        <span class="n">${shut.length} of ${S.places.length}</span></div>
      ${shut.length ? `<div class="list">${shut.map(({ p, cl }) => `<a class="item" href="#/place/${p.id}">
        <span class="item-main">
          <span class="item-t" style="text-decoration:line-through;color:var(--faint)">${esc(p.name)}</span>
          <span class="item-s" style="color:var(--danger-text)">${esc(cl.label)}${cl.verified ? "" : " (unverified)"}</span>
        </span></a>`).join("")}</div>`
        : `<p class="center-note tiny">Nothing in the dataset is shut on this day.</p>`}
    </section>

    <section class="card card-pad">
      <p class="tiny muted" style="margin:0">This lists places shut for the <b>whole</b> of that
      weekday, computed offline from each entry's own <code>closed_days</code>. It deliberately does
      not list places that are merely outside their hours right now — a dawn fish market is not
      "shut on Sunday" just because you checked at noon. For that, see <b>Open right now</b> on
      Today.</p>
    </section>
  </div>`;

  $$("[data-day]").forEach(b => b.onclick = () => { itDay = b.dataset.day; pageItinerary(); });
}

/* ============================================================ PAGE: trip */
function pageTrip() {
  const total = S.expenses.reduce((a, e) => a + e.paise, 0);
  const b = S.settings.budgetPaise;
  setHead("Trip", `${rupeesPlain(total)} logged${b ? ` of ${rupeesPlain(b)}` : ""}`);

  const roots = S.categories.filter(c => !c.parentId);
  const max = Math.max(1, ...roots.map(c => rollup(c.id)));
  const visited = Object.keys(S.visits).length;

  const byDay = {};
  for (const e of S.expenses) byDay[e.date] = (byDay[e.date] || 0) + e.paise;
  const dayMax = Math.max(1, ...Object.values(byDay));

  $("#main").innerHTML = `<div class="stack">
    <section class="card card-pad stack">
      <div class="field">
        <label for="bud">Trip budget (₹) <span class="opt">yours to set — nothing is assumed</span></label>
        <input id="bud" type="number" inputmode="numeric" min="0" step="1"
          value="${b ? Math.floor(b / 100) : ""}" placeholder="e.g. 30000">
      </div>
      <div class="btnrow">
        <button class="btn primary" id="budSave">Save budget</button>
        ${b ? `<button class="btn ghost" id="budClear">Clear</button>` : ""}
      </div>
    </section>

    <section class="card">
      <div class="daybar"><span>Where it went</span><span class="n">${rupeesPlain(total)}</span></div>
      <div class="card-pad">
        ${total ? `<div class="bars">${roots.map(c => {
          const v = rollup(c.id);
          if (!v) return "";
          return `<div class="bar-row">
            <span class="nm">${esc(c.name)}</span><span class="v num">${rupeesPlain(v)}</span>
            <span class="bar-track"><i style="width:${Math.round(v / max * 100)}%"></i></span>
          </div>` + S.categories.filter(k => k.parentId === c.id).map(k => {
            const kv = rollup(k.id);
            if (!kv) return "";
            return `<div class="bar-row depth1">
              <span class="nm tiny">${esc(k.name)}</span><span class="v num tiny">${rupeesPlain(kv)}</span>
            </div>`;
          }).join("");
        }).join("")}</div>`
          : `<p class="tiny muted" style="margin:0">Nothing logged yet, so there is nothing to break down.</p>`}
      </div>
    </section>

    ${Object.keys(byDay).length ? `<section class="card">
      <div class="daybar"><span>By day</span><span class="n">${Object.keys(byDay).length} days</span></div>
      <div class="card-pad"><div class="bars">
        ${Object.keys(byDay).sort().map(d => `<div class="bar-row">
          <span class="nm tiny">${esc(prettyDate(d))}</span>
          <span class="v num tiny">${rupeesPlain(byDay[d])}</span>
          <span class="bar-track"><i style="width:${Math.round(byDay[d] / dayMax * 100)}%"></i></span>
        </div>`).join("")}
      </div></div>
    </section>` : ""}

    <section class="card">
      <div class="daybar"><span>Places</span><span class="n">${visited}/${S.places.length} ✓</span></div>
      <div class="card-pad">
        <span class="bar-track" style="display:block"><i style="width:${Math.round(visited / S.places.length * 100)}%"></i></span>
        <p class="tiny muted" style="margin:10px 0 0">${S.places.length} sourced places across
          ${new Set(S.places.map(p => p.cluster)).size} areas. Dataset dated ${esc(S.generated)}.</p>
      </div>
    </section>

    <section class="card">
      <div class="daybar"><span>Categories</span><span class="n">${S.categories.length}</span></div>
      <div class="list">${S.categories.map(c => `<div class="item">
        <span class="item-main depth${Math.min(2, catDepth(c.id))}">
          <span class="item-t">${esc(c.name)}</span>
          <span class="item-s">${rupeesPlain(rollup(c.id))}${c.parentId ? ` · in ${esc(S.catById[c.parentId]?.name || "?")}` : ""}</span>
        </span>
        <button class="btn ghost danger" data-delcat="${c.id}"
          style="min-height:34px;padding:0 12px;font-size:12px">Delete</button>
      </div>`).join("")}</div>
      <div class="card-pad">
        <button class="btn ghost block" id="addCat">Add a category</button>
        <p class="tiny muted" style="margin:10px 0 0">Deleting a category moves its children up to
        its parent and reassigns its expenses there too. Expenses are never orphaned and never
        deleted with a category.</p>
      </div>
    </section>
  </div>`;

  $("#budSave").onclick = async () => {
    const v = $("#bud").value.trim();
    if (!v) { toast("Enter an amount, or Clear"); return; }
    const n = parseInt(v, 10);
    if (!Number.isFinite(n) || n < 0) return toast("That is not an amount");
    S.settings.budgetPaise = n * 100;
    await saveSettings(); toast("Budget saved"); pageTrip();
  };
  const bc = $("#budClear");
  if (bc) bc.onclick = async () => {
    S.settings.budgetPaise = null; await saveSettings(); toast("Budget cleared"); pageTrip();
  };

  $("#addCat").onclick = async () => {
    const name = prompt("Name of the new category");
    if (!name || !name.trim()) return;
    const opts = S.categories.map(c => `${c.id} — ${catLabel(c.id)}`).join("\n");
    const parent = prompt(`Parent category id, or blank for a top-level one.\n\n${opts}`, "");
    if (parent === null) return;
    const pid = parent.trim() || null;
    if (pid && !S.catById[pid]) return toast("No category with that id");
    const id = "u-" + name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")
      + "-" + Math.random().toString(36).slice(2, 6);
    const rec = { id, parentId: pid, name: name.trim() };
    await DB.put("categories", rec);
    S.categories.push(rec); S.catById[id] = rec;
    toast("Category added"); pageTrip();
  };

  $$("[data-delcat]").forEach(btn => btn.onclick = async () => {
    const id = btn.dataset.delcat, c = S.catById[id];
    const parent = c.parentId;
    const kids = S.categories.filter(k => k.parentId === id);
    const hit = S.expenses.filter(e => e.categoryId === id);
    if (!parent && (kids.length || hit.length)) {
      return toast("Top-level category with contents — move them first");
    }
    if (!confirm(`Delete "${c.name}"?\n\n${kids.length} child categor${kids.length === 1 ? "y" : "ies"} `
      + `move up to ${S.catById[parent]?.name || "top level"}, and ${hit.length} expense(s) move there too. `
      + `No expense is deleted.`)) return;

    for (const k of kids) { k.parentId = parent; await DB.put("categories", k); }
    for (const e of hit) { e.categoryId = parent; await DB.put("expenses", e); }
    await DB.del("categories", id);
    S.categories = S.categories.filter(x => x.id !== id);
    S.catById = Object.fromEntries(S.categories.map(x => [x.id, x]));
    toast("Category deleted, nothing lost"); pageTrip();
  });
}

/* ======================================================== PAGE: settings */
function pageSettings() {
  setHead("Settings", "Your data, this device");
  const s = S.settings;

  $("#main").innerHTML = `<div class="stack">
    <section class="card">
      <div class="daybar"><span>Live opening hours</span>
        <span class="n">${Live.configured() ? "on" : "off"}</span></div>
      <div class="card-pad stack">
        <p class="tiny muted" style="margin:0">Opening hours already work offline — they are computed
        from the curated dataset at Mumbai time. This adds an optional second opinion from Google
        when you are online. It is shown <b>next to</b> the curated hours and never replaces them:
        Google's data is crowd-edited, the curated data is sourced and dated.</p>

        <div class="field">
          <label for="lp">Provider</label>
          <select id="lp">
            <option value="none" ${s.liveProvider === "none" ? "selected" : ""}>Off</option>
            <option value="google" ${s.liveProvider === "google" ? "selected" : ""}>Google Places API (New)</option>
          </select>
        </div>
        <div class="field">
          <label for="gk">Your Places API key</label>
          <input id="gk" type="password" autocomplete="off" value="${esc(s.googleKey)}"
            placeholder="AIza…">
        </div>
        <div class="field">
          <label for="px">Proxy URL <span class="opt">only if direct calls are blocked</span></label>
          <input id="px" type="url" value="${esc(s.proxyUrl)}" placeholder="https://your-proxy/searchText">
        </div>
        <label class="tiny" style="display:flex;gap:8px;align-items:center">
          <input type="checkbox" id="al" ${s.autoLive ? "checked" : ""} style="width:auto;min-height:0">
          Refresh a few visible places automatically when online
        </label>
        <div class="btnrow">
          <button class="btn primary" id="liveSave">Save</button>
          <button class="btn ghost" id="liveTest">Test on one place</button>
        </div>

        <div class="callout">
          <b>Read this before you paste a key.</b> The key is stored only in this app's storage on
          this device and is sent only to Google, or to a proxy you type in yourself. It is not
          bundled into the app and nobody else receives it.
          <br><br>
          Two honest limits. <b>One:</b> a key used from a browser is visible to anyone using this
          device's developer tools, so restrict it to the Places API and set an HTTP-referrer
          restriction in Google Cloud, and expect to pay Google for calls beyond their free tier.
          <b>Two:</b> browser calls need CORS. Places API (New) generally allows them; if yours
          refuses, run a one-line proxy and put its URL above.
        </div>
        <div class="callout bad">
          <b>This path is written but unverified.</b> All outbound network access was denied in the
          container this app was built in, so the Google call has never actually run. It will
          either work on your phone or show you the error it got — it will not fail silently.
        </div>
      </div>
    </section>

    <section class="card">
      <div class="daybar"><span>Your data</span>
        <span class="n">${S.expenses.length} expenses</span></div>
      <div class="card-pad stack">
        <div class="btnrow">
          <button class="btn ghost" id="exp">Export everything (JSON)</button>
          <button class="btn ghost" id="imp">Import a backup</button>
        </div>
        <p class="tiny muted" style="margin:0">Export writes a file containing your expenses,
        categories, budget, tick-offs and hour corrections. There is no server and no account, so
        this file is the only backup that exists — take one before you clear anything.</p>

        <div class="btnrow">
          <button class="btn ghost" id="seed" ${s.seeded ? "disabled" : ""}>
            ${s.seeded ? "Train fares already imported" : "Import the two real train fares"}</button>
        </div>
        <p class="tiny muted" style="margin:0">₹768 on 09 Aug and ₹743 on 17 Aug, off the IRCTC
        slips. Optional on purpose — nothing is pre-filled for you, and you can edit or delete them
        like any other expense.</p>

        <div class="btnrow">
          <button class="btn ghost danger" id="wipe">Delete all my data</button>
        </div>
      </div>
    </section>

    <section class="card">
      <div class="daybar"><span>Appearance</span><span class="n"></span></div>
      <div class="card-pad">
        <div class="chips">
          ${["system", "light", "dark"].map(m => `<button class="chip" data-theme="${m}"
            aria-pressed="${(localStorage.getItem("theme") || "system") === m}">${m}</button>`).join("")}
        </div>
      </div>
    </section>

    <section class="card card-pad">
      <p class="tiny muted" style="margin:0">
        Dataset ${esc(S.generated)} · ${S.places.length} places.
        ${esc(S.licence?.attribution_required || "")}<br>
        Coordinates are unresolved by design — a typed-in coordinate is a fabricated address, so no
        map is drawn until a real OSM lookup fills them in.<br>
        Your data never leaves this phone unless you export it. There is no server to leave it on.
      </p>
    </section>
  </div>`;

  $("#liveSave").onclick = async () => {
    S.settings.liveProvider = $("#lp").value;
    S.settings.googleKey = $("#gk").value.trim();
    S.settings.proxyUrl = $("#px").value.trim();
    S.settings.autoLive = $("#al").checked;
    await saveSettings();
    toast(Live.configured() ? "Live hours on" : "Live hours off");
    pageSettings();
  };
  $("#liveTest").onclick = async () => {
    S.settings.liveProvider = $("#lp").value;
    S.settings.googleKey = $("#gk").value.trim();
    S.settings.proxyUrl = $("#px").value.trim();
    await saveSettings();
    if (!Live.configured()) return toast("Pick Google and paste a key first");
    if (!navigator.onLine) return toast("You are offline");
    const p = S.places.find(x => x.confidence === "high") || S.places[0];
    toast(`Asking Google about ${p.name}…`, 4000);
    const r = await Live.fetchOne(p);
    toast(r?.error ? `Failed: ${r.error}` : `Worked — Google matched "${r.name || p.name}"`, 5000);
  };

  $("#exp").onclick = async () => {
    const dump = {
      kind: "mumbai-trip-companion-backup", version: 1,
      exportedAt: new Date().toISOString(),
      settings: S.settings, expenses: S.expenses, categories: S.categories,
      visits: S.visits, overrides: S.overrides,
    };
    const blob = new Blob([JSON.stringify(dump, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `mumbai-backup-${istParts().date}.json`;
    a.click(); URL.revokeObjectURL(a.href);
    toast("Exported");
  };

  $("#imp").onclick = () => {
    const inp = document.createElement("input");
    inp.type = "file"; inp.accept = "application/json,.json";
    inp.onchange = async () => {
      const f = inp.files[0]; if (!f) return;
      try {
        const d = JSON.parse(await f.text());
        if (d.kind !== "mumbai-trip-companion-backup") throw new Error("not a backup from this app");
        if (!confirm("Replace everything on this device with the contents of this backup?")) return;
        for (const st of ["expenses", "categories", "visits", "overrides"]) await DB.clear(st);
        for (const e of d.expenses || []) await DB.put("expenses", e);
        for (const c of d.categories || []) await DB.put("categories", c);
        for (const [k, v] of Object.entries(d.visits || {})) await DB.put("visits", v, k);
        for (const o of Object.values(d.overrides || {})) await DB.put("overrides", o);
        if (d.settings) { Object.assign(S.settings, d.settings); await saveSettings(); }
        await loadAll(); toast("Imported"); route();
      } catch (e) { toast(`Could not import: ${e.message}`, 4000); }
    };
    inp.click();
  };

  $("#seed").onclick = async () => {
    for (const e of S.trip.seedExpenses) {
      const rec = { id: crypto.randomUUID(), ...e, placeId: null, createdAt: new Date().toISOString() };
      await DB.put("expenses", rec);
    }
    S.settings.seeded = true; await saveSettings();
    await loadAll(); toast("Added the two train fares"); pageSettings();
  };

  $("#wipe").onclick = async () => {
    if (!confirm("Delete every expense, category change, tick-off and correction on this device? "
      + "This cannot be undone and there is no server copy.")) return;
    if (!confirm("Really delete everything? Export first if you might want it back.")) return;
    for (const st of ["expenses", "categories", "visits", "overrides", "live"]) await DB.clear(st);
    await DB.del("settings", "app");
    S.settings = { budgetPaise: null, liveProvider: "none", googleKey: "", proxyUrl: "", seeded: false, autoLive: true };
    await loadAll(); toast("Everything deleted"); location.hash = "#/";
  };

  $$("[data-theme]").forEach(b => b.onclick = () => {
    const m = b.dataset.theme;
    if (m === "system") { localStorage.removeItem("theme"); document.documentElement.removeAttribute("data-theme"); }
    else { localStorage.setItem("theme", m); document.documentElement.dataset.theme = m; }
    pageSettings();
  });
}

/* ================================================== expense editor sheet */
let sheet = { id: null, digits: "", ctx: {} };

function renderAmt() {
  const paise = sheet.digits ? parseInt(sheet.digits, 10) * 100 : 0;
  $("#amtOut").innerHTML = money(paise);
  const b = S.settings.budgetPaise;
  if (b) {
    const spent = S.expenses.filter(e => e.id !== sheet.id).reduce((a, e) => a + e.paise, 0);
    const after = b - spent - paise;
    $("#amtCtx").innerHTML = after < 0
      ? `<span class="meter-warn">${rupeesPlain(-after)} over budget after this</span>`
      : `${rupeesPlain(after)} left after this`;
  } else {
    $("#amtCtx").textContent = paise ? "No budget set — nothing to measure against" : "";
  }
}

function buildPad() {
  const keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "00", "0", "del"];
  $("#pad").innerHTML =
    `<button data-k="save" type="button">SAVE</button>` +
    keys.map(k => `<button data-k="${k}" type="button">${k === "del" ? "⌫" : k}</button>`).join("");
  // The save key is first in DOM so it can span all four rows, but visually last.
  $("#pad").style.gridTemplateAreas = "";
  $$("#pad button").forEach(b => b.onclick = () => {
    const k = b.dataset.k;
    if (k === "save") return saveExpense();
    if (k === "del") sheet.digits = sheet.digits.slice(0, -1);
    else if (sheet.digits.length < 7) sheet.digits += k;
    renderAmt();
  });
}

function fillCatSelect(sel, current) {
  sel.innerHTML = S.categories
    .slice().sort((a, b) => catLabel(a.id).localeCompare(catLabel(b.id)))
    .map(c => `<option value="${c.id}" ${c.id === current ? "selected" : ""}>${esc(catLabel(c.id))}</option>`)
    .join("");
}

function openSheet(id = null, ctx = {}) {
  const e = id ? S.expenses.find(x => x.id === id) : null;
  sheet = { id, digits: e ? String(Math.floor(e.paise / 100)) : "", ctx };

  $("#sheetTitle").textContent = e ? "Edit expense" : "Log an expense";
  $("#delBtn").hidden = !e;
  $("#fDate").value = e?.date || ctx.date || istParts().date;
  $("#fMethod").value = e?.method || "cash";
  $("#fNote").value = e?.note || "";

  fillCatSelect($("#fCat"), e?.categoryId || ctx.categoryId || "food-chai");

  $("#fPlace").innerHTML = `<option value="">None</option>` + S.places
    .map(p => `<option value="${p.id}" ${(e?.placeId || ctx.placeId) === p.id ? "selected" : ""}>${esc(p.name)}</option>`)
    .join("");

  // Quick chips: the categories you actually use, most-used first.
  const freq = {};
  for (const x of S.expenses) freq[x.categoryId] = (freq[x.categoryId] || 0) + 1;
  const top = Object.keys(freq).sort((a, b) => freq[b] - freq[a]).slice(0, 5);
  const chips = top.length ? top : ["food-chai", "travel-local-auto", "travel-local-train", "food-street"];
  $("#quickCats").innerHTML = chips.filter(c => S.catById[c]).map(c =>
    `<button class="chip" data-qc="${c}">${esc(S.catById[c].name)}</button>`).join("");
  $$("[data-qc]").forEach(b => b.onclick = () => { $("#fCat").value = b.dataset.qc; toast(catLabel(b.dataset.qc)); });

  buildPad(); renderAmt();
  $("#sheetWrap").hidden = false;
  document.body.style.overflow = "hidden";
}

function closeSheet() {
  $("#sheetWrap").hidden = true;
  document.body.style.overflow = "";
}

async function saveExpense() {
  const paise = sheet.digits ? parseInt(sheet.digits, 10) * 100 : 0;
  if (!paise) return toast("Enter an amount first");
  const rec = {
    id: sheet.id || crypto.randomUUID(),
    date: $("#fDate").value || istParts().date,
    paise,
    categoryId: $("#fCat").value,
    method: $("#fMethod").value,
    placeId: $("#fPlace").value || null,
    note: $("#fNote").value.trim(),
    createdAt: sheet.id ? undefined : new Date().toISOString(),
  };
  if (rec.createdAt === undefined) delete rec.createdAt;
  await DB.put("expenses", rec);
  await loadAll();
  closeSheet();
  toast(sheet.id ? "Updated" : `Logged ${rupeesPlain(paise)}`);
  route();
}

async function delExpense() {
  if (!sheet.id) return;
  if (!confirm("Delete this expense?")) return;
  await DB.del("expenses", sheet.id);
  await loadAll(); closeSheet(); toast("Deleted"); route();
}

/* ------------------------------------------------------------------ boot */
async function boot() {
  const th = localStorage.getItem("theme");
  if (th) document.documentElement.dataset.theme = th;

  try {
    await loadAll();
  } catch (e) {
    $("#main").innerHTML = `<section class="card card-pad">
      <h2>Could not start</h2>
      <p class="muted">${esc(e.message)}</p>
      <p class="tiny muted">If you opened this file directly from disk, the browser blocks reading
      the dataset next to it. Serve the folder over http instead — any static server will do.</p>
    </section>`;
    return;
  }

  $("#fab").onclick = () => openSheet();
  $("#saveBtn").onclick = saveExpense;
  $("#delBtn").onclick = delExpense;
  $$("[data-close]").forEach(el => el.onclick = closeSheet);
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && !$("#sheetWrap").hidden) closeSheet();
  });
  document.addEventListener("click", e => {
    const b = e.target.closest("[data-edit]");
    if (b) openSheet(b.dataset.edit);
  });

  addEventListener("hashchange", route);
  addEventListener("online", () => { syncNet(); toast("Back online"); });
  addEventListener("offline", () => { syncNet(); toast("Offline — everything still works"); });
  syncNet();
  route();

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch(() => { /* http-only; fine without it */ });
  }
}

boot();
