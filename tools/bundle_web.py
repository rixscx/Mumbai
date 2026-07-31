#!/usr/bin/env python3
"""Bundle web/ into one self-contained HTML file.

Why: the normal web app is several files that fetch the dataset over relative URLs. That is the
right shape for something served over http and installed to a home screen, and the wrong shape for
handing someone a page to try — from `file://` or inside a sandboxed frame, those fetches are
blocked and the app shows its "could not start" screen.

This inlines the CSS, the JS and both JSON payloads into a single page with no external requests at
all. It is a *try-it* build, not the shipping one:

  * no service worker, so no offline precache — the page still works without a network once loaded,
    because everything is already in it, but a cold start needs the page;
  * no web app manifest, so no install-to-home-screen;
  * the live-hours lookup cannot reach Google from a sandboxed frame, and will report the failure
    rather than pretending to be off.

Everything else is the real app, including the IndexedDB storage — so expenses entered here are
genuinely saved, in this page's origin.

Output is deliberately headless of <!doctype>/<html>/<head>/<body>: the publishing surface wraps it,
and duplicating those tags produces a malformed document.

Usage:
    python3 tools/bundle_web.py            # writes web/standalone.html
    python3 tools/bundle_web.py --check    # fail if stale (for CI)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
OUT = WEB / "standalone.html"

BANNER = """
<div class="tryout">
  <b>Try-it build.</b> The real app installs to a home screen and works offline; this single page is
  everything inlined so it runs anywhere. Expenses you enter <em>are</em> saved — in this page's
  storage, separate from a real install. Live hours from Google cannot be reached from here.
</div>
"""

BANNER_CSS = """
.tryout {
  margin: 0 auto; max-width: 820px; padding: 11px 16px;
  background: var(--sunk); border-bottom: 1px solid var(--rule);
  font-size: 12.5px; color: var(--dim); line-height: 1.45;
}
.tryout b { color: var(--text); }
"""


def esc_json(text: str) -> str:
    """`</script>` inside embedded JSON would end the block early."""
    return text.replace("</", "<\\/")


def build() -> str:
    html = (WEB / "index.html").read_text()
    css = (WEB / "app.css").read_text()
    js = (WEB / "app.js").read_text()
    places = (WEB / "places.json").read_text().strip()
    trip = (WEB / "trip.json").read_text().strip()

    # Take only what is inside <body>; the wrapper supplies the document shell.
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S)
    if not m:
        sys.exit("web/index.html has no <body> — cannot bundle")
    body = m.group(1)

    # Drop the external references we are replacing with inlined content.
    body = re.sub(r'\s*<script src="app\.js"></script>', "", body)
    body = body.strip()

    # The banner goes after the app bar so it does not push the sticky header around.
    body = body.replace("</header>", "</header>\n" + BANNER.strip(), 1)

    # Service-worker registration is pointless here and throws in a sandbox; the app already
    # catches it, but removing it keeps the console clean for anyone who opens dev tools.
    js = js.replace(
        '    navigator.serviceWorker.register("sw.js").catch(() => { /* http-only; fine without it */ });',
        "    /* stripped in the single-file build: no sw.js alongside this page */",
    )

    return f"""<title>Mumbai — trip companion</title>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<style>
{css}
{BANNER_CSS}
</style>

{body}

<script type="application/json" id="data-places">{esc_json(places)}</script>
<script type="application/json" id="data-trip">{esc_json(trip)}</script>
<script>
{js}
</script>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    out = build()
    if args.check:
        if not OUT.exists() or OUT.read_text() != out:
            print(f"{OUT.relative_to(ROOT)} is stale — run tools/bundle_web.py", file=sys.stderr)
            return 1
        print(f"{OUT.relative_to(ROOT)} is up to date")
        return 0

    OUT.write_text(out)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(out):,} bytes, no external requests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
