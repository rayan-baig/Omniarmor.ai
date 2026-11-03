# Load test: how much OmniArmor handles, and when to grow

Measured on 3 November 2026 with `tools/load_test.py`, on a shared 4-core
Linux machine with 16 GB of memory. The load generator ran on the same
machine as the server and took CPU from it, and other work was running there
too, so **treat every number as rough**: good for the shape of the curve and
for which part gives first, not as a promise. Run it again on the size of
server you deploy to.

## 1. 500 workspaces using the app at once

```sh
python3 tools/load_test.py http                    # 500 workspaces, 50 to 1,000 people at once
python3 tools/load_test.py http --workers 4        # the same with WEB_CONCURRENCY=4
python3 tools/load_test.py http --think 0 --stages 16,64   # people clicking nonstop
```

The tool seeds 500 workspaces into a throwaway database (two or three
industries each, readings, running clocks, a learner on an Academy trial, two
people each), then starts the app with **the Dockerfile's own gunicorn
command** (one process, 8 threads, the scheduler on, production settings).
Each simulated person signs in with their password and then clicks, about
every 3 seconds, through a mix of pages: HQ, an industry page, updating a
check, the bulk form, the Academy (home, map, a lesson and its quiz),
Settings (and saving reminder choices), the Vault and the report. Every
redirect is followed like a browser. After each stage it reads the server
log for locked databases, timeouts, tracebacks and memory errors; at the end
it counts every saved change in the audit trail.

### One process, 8 threads (the default)

| People at once | Requests/s | Failed | All pages p50 | All pages p95 | Server memory |
|---|---|---|---|---|---|
| 50 | 22 | 0 | 6 ms | 94 ms | 152 MB |
| 100 | 42 | 0 | 6 ms | 14 ms | 161 MB |
| 250 | 90 | 0 | 290 ms | 1.3 s | 203 MB |
| **500** | **98** | **0** | **2.6 s** | **3.8 s** | 309 MB |
| 1,000 | 71 | 0 | 8.5 s | 14.6 s | 336 MB |

Per page at 100 people (median / 95th percentile): industry page 6 / 16 ms,
update a check 5 / 12 ms, bulk form 5 / 13 ms, HQ 6 / 13 ms, Academy map
8 / 12 ms, Academy lesson 4 / 10 ms, quiz answer 7 / 16 ms, Settings 6 / 18 ms,
Vault 5 / 16 ms, report 6 / 17 ms. Signing in: 97 / 165 ms (the password
hash is slow on purpose). At 500 people every page takes about the same
2.6 s: the time is spent waiting for the one process, not in any page.

Nonstop clicking (no pause between clicks), 16 people: **93 requests a
second** at p50 142 ms. That is one process's ceiling here.

### Four processes (`WEB_CONCURRENCY=4`)

| People at once | Requests/s | Failed | p50 | p95 | Server memory |
|---|---|---|---|---|---|
| 250 | 108 | 0 | 6 ms | 12 ms | 478 MB |
| 500 | 173 | 0 | 10 ms | 3.4 s | 1,020 MB |
| 1,000 | 122 | 0 | 2.8 s | 14.2 s | 1,104 MB |

Nonstop clicking, 64 people: about 500 requests a second, with industry
pages at p95 170 ms and saves at p95 about 1 s (they wait their turn for
SQLite's single writer). At 500 people the p95 comes from the sign-in rush:
500 people signing in within 15 seconds, each password check taking about
0.1 s of CPU and 32 MB of memory.

### What broke first

**Response time, from one process running out of CPU.** With the default
settings, pages stay fast up to about 100 people clicking every few seconds,
and past about 90 requests a second requests queue: at 500 people at once
the 95th percentile is 3.8 s. Nothing fails while it slows down.

What did **not** break, at any stage:

- **No errors:** 0 failed requests and 0 server errors in every run.
- **No lost writes:** every change the app confirmed is in the audit trail
  (4,075 of 4,075 in the main run, 6,262 of 6,262 nonstop).
- **No "database is locked":** WAL mode and a 30-second busy timeout make
  writers wait their turn; under nonstop saving a save waits up to about a
  second, and none failed.
- **No worker timeouts or restarts.**

**Memory is next**, with more processes: each sign-in's password check
briefly takes 32 MB, so a process with 8 threads can spike by about 260 MB
during a sign-in rush. Four processes reached 1 GB, more than the smallest
servers have.

## 2. The scheduled sweeps under load

```sh
python3 tools/load_test.py sweep --sizes 100,500,2000
python3 tools/load_test.py sweep --sizes 100,500 --smtp-ms 100   # an email provider taking 0.1 s per email
```

Every seeded workspace has business-day, day, hour and minute clocks
running, all at a reminder point at once (the worst case: every company's
clocks crossing a line in the same minute), and two people. Email goes to a
local mail server the tool runs.

| Workspaces | Alerts sweep | Next minute's sweep | Daily run | Autopilot pass | Digests | Alerts |
|---|---|---|---|---|---|---|
| 100 | 1.9 s | 0.0 s | 1.0 s | 1.8 s | 200 | 404 |
| 500 | 8.5 s | 0.2 s | 4.6 s | 1.5 s | 1,000 | 1,982 |
| 2,000 | 34.8 s | 0.7 s | 20.1 s | 1.5 s | 4,000 | 7,924 |

With an email provider taking 0.1 s per email: 100 workspaces, alerts 43 s and
daily run 21 s; 500 workspaces, alerts 212 s and daily run 108 s. **The time
is the emails:** a sweep takes about (emails sent) x (the provider's time per
email). With nothing new to send, a sweep of 2,000 workspaces takes under a
second.

Checked every time: every workspace got its digest and its alerts, nobody got
any email twice (in the database and at the mail server), the next minute's
sweep and a forced daily run sent nothing again, and two server processes
sweeping the same database at the same moment still sent each email once.

**What was wrong, and fixed:**

- **Two sweeps could overlap.** The daily run claimed the day with a time
  stamp that went stale after an hour, and Autopilot claimed each 10-minute
  slot. With more than one server process (`WEB_CONCURRENCY` above 1, or two
  containers during a deploy), a daily run longer than an hour (2,000
  workspaces at 1 s per email is over an hour) could be claimed again by
  another process and send the same digests twice, and an Autopilot pass
  longer than 10 minutes (re-sending failed emails to a provider that times
  out after 20 s) let the next pass re-send the same emails beside it. Each
  sweep now holds a lock in the database while it runs (`job_locks`, schema
  version 14), renewed every 20 seconds by its holder and lost within 2
  minutes if the process dies. `tests/test_sweeps.py` holds a run open past
  its time and shows the second one skips (it sent a second digest before).
- **A long daily run held the alerts up.** One thread ran the alerts, the
  daily job and Autopilot in turn, so while the daily run sent thousands of
  digests no time-limit alert went out, even for a 15-minute clock. The
  alerts now have a thread of their own.

## 3. Backup and restore rehearsal

A seeded database, used through the running app (a reading saved, a lesson
played), backed up with the app's own `flask --app wsgi backup` while the
server ran, one more change made, then restored by docs/OPERATIONS.md,
section 4, exactly as it was written, and the app started on it: health
check ok, sign-in, the industry page, the learner's progress report and the
Vault all there, the change made after the backup gone (24 audit rows back
to 21), integrity check ok. The written steps worked on a plain server, but:

1. **No commands**, and on Docker they don't work as written: once the
   container is stopped, its `/data` volume can only be reached through
   another container.
2. **The current database was overwritten**, so a wrong backup choice had no
   way back.
3. **No check** of the copy before using it, and nothing to check after.
4. The `-wal` and `-shm` files must go **before** the app starts again, or
   SQLite replays the old database's last changes onto the restored copy; it
   didn't say why or when.
5. **Restoring the morning's backup re-sent that day's digests.** The daily
   job took its backup before sending reminders, so the copy held the day's
   claim but none of its reminders; an hour after a restore the claim went
   stale and everyone got the day's digest again. The backup is now taken
   last (and a copy no longer carries a sweep's lock).

The steps are now a 10-minute checklist in docs/OPERATIONS.md, section 4:
copy the backup to a fresh file, check it, point `DATABASE_PATH` at it and
restart, check the app; the old database stays for a week. It was rehearsed
the same way (healthz, sign-in, checks, Academy, Vault all there), and
`tests/test_operations.py` (`TestRestoreRehearsal`) does it on every push,
including that the daily job on the restored copy sends no second digest.

## 4. When to grow

People really click every 10 to 30 seconds, not every 3, so the stages above
are 3 to 10 times harsher than the same number of real people.

1. **Now (one process, 8 threads, the smallest server):** comfortable up to
   about 60 requests a second, which is roughly 600 people actively clicking
   at the same moment, or several thousand workspaces in a normal day.
2. **When pages slow down at busy times** (p95 over a second, or the app's
   CPU near 100%): set `WEB_CONCURRENCY` to the number of CPU cores. Allow
   about 400 MB per process (150 MB running, plus the sign-in spikes): two
   processes on a 1 GB server, four on 2 GB. Four processes reached about 500
   requests a second here. This is a setting, not a code change; the sweep
   locks keep the timer safe with any number of processes.
3. **A bigger plan** (more cores and memory) when four processes are not
   enough.
4. **Move to Postgres** when one server is no longer enough: at roughly
   **3,000 to 5,000 busy workspaces**, when saves run above about 100 a second
   for long stretches (SQLite has one writer at a time; here saves waited up
   to a second at about 80 a second), when you want a second server for
   uptime (SQLite lives on one server's disk), or when the database file
   passes about 10 GB. That is a code change: the app uses SQLite directly.
5. **Email:** sweep time is the number of emails times the provider's time
   per email. Keep the provider fast; past about 1,000 workspaces whose clocks
   can all fire at once, sending each sweep's emails over one connection
   instead of one per email is the next improvement.
