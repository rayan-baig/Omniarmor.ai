# How fast OmniArmor is

Measured on 19 November 2026 (version 1.8.0) on the demo workspace
(`flask --app wsgi seed-demo`), in the app itself, on a shared Linux
machine. How much the server takes at once, and when to grow, is in
[LOAD-TEST.md](LOAD-TEST.md); this page is about one person's wait.

## 1. What was slow

The server was already quick: every page takes 1 to 11 ms to make (median),
with 0 to 16 database queries, and no page runs a query per row (no
"N+1"). The wait was **the bytes**: on a host without Caddy in front (Render,
say) every page and stylesheet went out uncompressed, and the Academy map
alone is 150 KB of HTML.

## 2. Page weight on the first visit

What the browser downloads from OmniArmor for one page: the HTML and our CSS
and JavaScript (Google Fonts not counted; they come from Google and are
cached across sites). "Slow phone" is Chrome's "Slow 3G" setting, 400 kbit/s:
the time just to download those bytes, before any round trips.

| Page | Before | After | Slow phone before | Slow phone after |
|---|---|---|---|---|
| Landing page | 59.9 KB | 14.8 KB | 1.2 s | 0.3 s |
| HQ (signed in) | 68.5 KB | 16.6 KB | 1.4 s | 0.3 s |
| Academy map | 226.6 KB | 35.9 KB | 4.5 s | 0.7 s |
| Academy lesson (the game) | 117.6 KB | 26.2 KB | 2.4 s | 0.5 s |

On a second visit only the HTML comes again: CSS, JavaScript and images are
kept by the browser for a year (each link carries the file's version, so a
deploy that changes one gets a new address).

| File | Before | After |
|---|---|---|
| `app.css` | 32.6 KB | 8.1 KB |
| `academy.css` | 43.8 KB | 10.0 KB |
| `academy.js` | 9.9 KB | 3.3 KB |
| `armo.js` | 8.5 KB | 2.8 KB |

**What changed:** the app gzips HTML, CSS, JavaScript and JSON itself
(`omniarmor_app/compress.py`) when the browser says it takes gzip: only
complete answers over 1 KB, never the streamed CSV exports, and each static
file is compressed once per version and kept in memory. Making a page costs
0.5 to 2 ms more for it. Behind Caddy, which compressed already, nothing
changes. The forms' hidden token is now different on every page, so a
compressed page gives away nothing about it.

## 3. Database queries that read whole tables

Every query the pages and the background jobs run was checked with SQLite's
query plan. Three read a whole table each time and get slower as the
service grows. Timed on a big database (2,000 workspaces, 4,000 people,
400,000 emails, about a year of reminders), median of 20 runs:

| Query | Runs | Before | After |
|---|---|---|---|
| Radar (a workspace's emails, and the emails to one person) | each Radar page | 35.5 ms | 0.2 ms |
| Autopilot: failed emails to send again, and stuck ones | every 10 minutes | 28 ms | 0.02 ms |
| A workspace's team (memberships by workspace) | HQ, Settings, every digest | 0.20 ms | 0.01 ms |

**What changed:** three indexes (schema version 24):
`notifications (user_id, created_at)`, `notifications (status, created_at)`
and `memberships (org_id, role)`. `tests/test_health_and_speed.py` checks
the plans use them.

The rest scan only small tables, or run once a day (the daily job's sweep
of every workspace), where a scan is the right plan.

## 4. Checking it again

The pages that do the most work are the Academy map (all the worlds and
levels) and an industry page with many checks; measure them first. With the
app running, `curl -s -o /dev/null -w '%{size_download}\n' -H
'Accept-Encoding: gzip' https://omniarmor.mtrxhorizyn.com/` gives the bytes
sent for one page.
