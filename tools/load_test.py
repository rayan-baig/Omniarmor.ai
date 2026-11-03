#!/usr/bin/env python3
"""Load test: many workspaces using OmniArmor at once, and how long its sweeps take.

Everything runs on a throwaway database in a temporary folder, deleted at the end.

    python3 tools/load_test.py http  [--workspaces 500] [--stages 50,100,250,500,1000] [--seconds 45]
    python3 tools/load_test.py sweep [--sizes 100,500,2000] [--smtp-ms 0]

http   Seeds the workspaces (each with its people, industries, readings and a
       learner), then starts the app with gunicorn exactly as the Docker image
       does: the CMD line of the Dockerfile, with its worker and thread
       settings (change them with --workers and --threads). Stage by stage it
       raises the number of signed-in people clicking at once, each in their
       own workspace, through a mix of pages: the overview, an industry page,
       updating a check, the bulk form, the Academy (home, map, a lesson and
       its quiz), Settings, the audit trail and the report. For each stage it
       prints requests per second, the median and 95th-percentile time per
       page, the failures, the server's memory and anything the server
       logged, and names the first thing that broke. At the end it counts
       every saved change in the audit trail, so a lost write shows up.

sweep  Seeds workspaces whose business-day, hour and minute clocks are running
       and times one pass of each scheduled job: the time-limit alerts (every
       minute), the daily reminder run and an Autopilot pass. Email goes to a
       local SMTP sink (--smtp-ms adds a delay per message, like a real
       provider). It then checks that every workspace was reminded, nobody got
       the same email twice, and that two server processes sweeping together
       still send each email once.

Numbers depend on the computer: run it on the size of server you deploy to.
"""

import argparse
import http.client
import multiprocessing
import os
import random
import re
import shutil
import signal
import socket
import socketserver
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter, defaultdict
from datetime import timedelta
from urllib.parse import urlencode, urlsplit
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from werkzeug.security import generate_password_hash  # noqa: E402

from omniarmor_app.catalog import INDUSTRIES, counts_time, date_mode, date_unit, rules_for  # noqa: E402
from omniarmor_app.db import connect, iso, migrate, utcnow  # noqa: E402
from omniarmor_app.reminders import clock_stage, reminder_window  # noqa: E402
from omniarmor_app.tracking import compute_state, effective_rule  # noqa: E402

PASSWORD = "load-test-password"
TIMEZONES = ["America/New_York", "America/Chicago", "America/Los_Angeles", "Europe/London", "UTC", "Asia/Tokyo"]
# A stage "breaks" when more than this share of its requests fail, or its 95th
# percentile is slower than this.
FAIL_SHARE = 0.01
SLOW_P95_MS = 2000
# Lines in the server log that mean something went wrong.
LOG_PROBLEMS = {
    "database is locked": "SQLite: database is locked",
    "WORKER TIMEOUT": "gunicorn: a worker timed out and was killed",
    "MemoryError": "out of memory",
    "Traceback": "a server error (traceback in the log)",
    "Too many open files": "out of file handles",
}


# --- Seeding ------------------------------------------------------------------------------

def _email(workspace, person):
    return f"load{workspace}-{person}@example.com"


def _limit_days(rule, row):
    """Roughly how many days a date-tracked check runs before it is due."""
    eff = effective_rule(rule, row)
    per_unit = {"days": 1, "business days": 1.4, "months": 30.4, "calendar months": 30.4, "years": 365.25}
    return int((eff.limit or 0) * per_unit.get(date_unit(rule), 1))


def _clock_row(industry_id, rule, today, now, tz, rng, overdue):
    """A reading that puts this date-tracked check in a reminder window today
    (for the hour and minute clocks: at their warning point, or just overdue),
    or None if no nearby date does."""
    row = dict.fromkeys(("value_num", "value_bool", "value_date", "limit_override", "warn_override", "updated_at",
                         "updated_by", "updated_by_name"))
    if counts_time(rule):
        eff = effective_rule(rule, row)
        per = 60 if date_unit(rule) == "hours" else 1
        limit = int(eff.limit * per)
        warn = int(eff.warn * per) if eff.warn is not None else limit
        for elapsed in ([limit + 2, limit + 5] if overdue else [(warn + limit) // 2, warn, limit]):
            row["value_date"] = iso((now - timedelta(minutes=elapsed)).replace(second=0, microsecond=0))
            if clock_stage(compute_state(industry_id, rule, row, today, now, tz), now) is not None:
                return row
        return None
    target = rng.choice([20, 5, 1, 0, -3, -10])
    if date_mode(rule) == "until":
        candidates = [today + timedelta(days=target + d) for d in range(0, 4)]
    else:
        back = _limit_days(rule, row) - target
        candidates = [today - timedelta(days=back + d) for d in (0, 1, -1, 2, -2, 3, -3, 5, -5, 8, -8)]
    for day in candidates:
        if date_mode(rule) == "since" and day > today:
            continue
        row["value_date"] = day.isoformat()
        if reminder_window(compute_state(industry_id, rule, row, today, now, tz).days_left) is not None:
            return row
    return None


def seed(path, workspaces, people=2, clocks=True, rng_seed=7):
    """Creates `workspaces` workspaces with `people` people each. Every
    workspace has two or three industries, yes-or-no answers, a learner on an
    Academy trial and, with clocks=True, every date-tracked check in a
    reminder window: business-day and day clocks coming due or overdue, and
    hour and minute clocks at their warning point or just overdue. Returns one
    dict per workspace."""
    rng = random.Random(rng_seed)
    conn = connect(path)
    migrate(conn)
    password = generate_password_hash(PASSWORD)
    now = utcnow().replace(microsecond=0)
    stamp = iso(now)
    trial = iso(now + timedelta(days=14))
    timed = sorted({i for i in INDUSTRIES for r in rules_for(i) if counts_time(r)})
    business = sorted({i for i in INDUSTRIES for r in rules_for(i) if date_unit(r) == "business days"})
    others = sorted(INDUSTRIES)
    made = []
    for n in range(1, workspaces + 1):
        tz_name = TIMEZONES[n % len(TIMEZONES)]
        tz = ZoneInfo(tz_name)
        local_now = now.astimezone(tz)
        today = local_now.date()
        industries = [timed[n % len(timed)], business[n % len(business)], rng.choice(others)]
        industries = list(dict.fromkeys(industries))[: 2 + n % 2]
        org_id = conn.execute(
            "INSERT INTO orgs (name, timezone, created_at, academy_trial_ends) VALUES (?, ?, ?, ?)",
            (f"Load Test Company {n}", tz_name, stamp, trial)).lastrowid
        users = []
        for p in range(people):
            user_id = conn.execute(
                "INSERT INTO users (email, name, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (_email(n, p), f"Person {n}-{p}", password, stamp)).lastrowid
            conn.execute("INSERT INTO memberships (user_id, org_id, role, created_at) VALUES (?, ?, ?, ?)",
                         (user_id, org_id, "owner" if p == 0 else "member", stamp))
            users.append(user_id)
        conn.executemany("INSERT INTO org_industries (org_id, industry_id) VALUES (?, ?)",
                         [(org_id, i) for i in industries])
        conn.execute("INSERT INTO audit (org_id, user_id, user_name, at, action, summary) VALUES (?, ?, ?, ?, ?, ?)",
                     (org_id, users[0], f"Person {n}-0", stamp, "workspace",
                      f"Workspace created with {len(industries)} industries"))
        learner_id = conn.execute(
            "INSERT INTO learners (org_id, nickname, avatar, armo, track, track_chosen, created_by, created_at,"
            " device_epoch) VALUES (?, ?, 'rocket', 'sweet', 'launchpad', 1, ?, ?, ?)",
            (org_id, f"Kid {n}", users[0], stamp, rng.randrange(1, 2 ** 62))).lastrowid
        items = []
        for industry_id in industries:
            for rule in rules_for(industry_id):
                row = None
                if rule.kind in ("required", "forbidden") and rng.random() < 0.5:
                    row = {"value_bool": 1 if rule.kind == "required" else 0}
                elif clocks and date_mode(rule):
                    row = _clock_row(industry_id, rule, today, local_now, tz, rng, overdue=n % 2 == 1)
                if row:
                    items.append((org_id, industry_id, rule.key, row.get("value_bool"), row.get("value_date"),
                                  stamp, users[0], f"Person {n}-0"))
        conn.executemany(
            "INSERT INTO items (org_id, industry_id, rule_key, value_bool, value_date, updated_at, updated_by,"
            " updated_by_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", items)
        made.append({"org_id": org_id, "emails": [_email(n, p) for p in range(people)], "industries": industries,
                     "learner_id": learner_id})
    conn.commit()
    conn.close()
    return made


# --- The server, as the Docker image runs it ---------------------------------------------------

def dockerfile_command():
    """The gunicorn command from the Dockerfile's CMD line, so the test runs
    what production runs."""
    with open(os.path.join(ROOT, "Dockerfile"), encoding="utf-8") as f:
        text = f.read()
    cmd = re.search(r'^CMD \["sh", "-c", "(.*)"\]\s*$', text, re.M).group(1)
    env = dict(re.findall(r"\b(WEB_CONCURRENCY|WEB_THREADS)=(\d+)", text))
    return cmd.replace("0.0.0.0", "127.0.0.1"), int(env["WEB_CONCURRENCY"]), int(env["WEB_THREADS"])


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server(folder, db_path, workers, threads, scheduler=True):
    cmd, _, _ = dockerfile_command()
    port = free_port()
    env = dict(os.environ, OMNIARMOR_ENV="production", SECRET_KEY=os.urandom(32).hex(), DATABASE_PATH=db_path,
               BACKUP_DIR=os.path.join(folder, "backups"), PORT=str(port), WEB_CONCURRENCY=str(workers),
               WEB_THREADS=str(threads), BASE_URL=f"http://127.0.0.1:{port}", SESSION_COOKIE_SECURE="0",
               SCHEDULER_ENABLED="1" if scheduler else "0",
               PATH=os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", ""))
    log = open(os.path.join(folder, "server.log"), "wb")
    proc = subprocess.Popen(["sh", "-c", cmd], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                            start_new_session=True)
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
            conn.request("GET", "/healthz")
            if conn.getresponse().status == 200:
                return proc, port
        except OSError:
            time.sleep(0.3)
        if proc.poll() is not None:
            break
    stop_server(proc)
    raise RuntimeError("the server didn't start; see " + log.name)


def stop_server(proc):
    if proc.poll() is None:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(15)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()


def server_memory_mb(pid):
    """Resident memory of the server's process group (gunicorn and its workers)."""
    total = 0
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/stat") as f:
                fields = f.read().rsplit(")", 1)[1].split()
            if int(fields[2]) != pid:   # process group id
                continue
            with open(f"/proc/{entry}/status") as f:
                total += next(int(line.split()[1]) for line in f if line.startswith("VmRSS:"))
        except (OSError, StopIteration, IndexError, ValueError):
            continue
    return total / 1024


# --- A signed-in person clicking around --------------------------------------------------------

CSRF = re.compile(r'name="csrf_token" value="([^"]+)"')
ATTEMPT = re.compile(r'name="attempt" value="(\d+)"')
QUESTION = re.compile(r'name="q(\d+)"')
YES_NO = {i: [r.key for r in rules_for(i) if r.kind in ("required", "forbidden")] for i in INDUSTRIES}
DONE = {i: [r.key for r in rules_for(i) if date_mode(r) == "since" and not counts_time(r)] for i in INDUSTRIES}

# What people do, and how often (weights).
MIX = [("overview", 10), ("industry page", 22), ("update a check", 14), ("bulk form", 6), ("academy home", 5),
       ("academy map", 7), ("academy lesson", 7), ("academy quiz", 5), ("settings", 8), ("settings save", 3),
       ("audit trail", 7), ("report", 6)]
KEEP_ALIVE = 1.5    # gunicorn closes an idle connection after 2 s; don't reuse one older than this


class Person:
    def __init__(self, port, workspace, email, rng, record):
        self.port, self.ws, self.email, self.rng, self.record = port, workspace, email, rng, record
        self.cookies = {}
        self.csrf = None
        self.conn = None
        self.last_used = 0.0
        self.writes = 0

    def _send(self, method, path, form=None):
        body = urlencode(form, doseq=True) if form is not None else None
        headers = {"Cookie": "; ".join(f"{k}={v}" for k, v in self.cookies.items()), "User-Agent": "load-test"}
        if body is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if self.conn is None or time.monotonic() - self.last_used > KEEP_ALIVE:
            if self.conn is not None:
                self.conn.close()
            self.conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=90)
        try:
            self.conn.request(method, path, body=body, headers=headers)
            resp = self.conn.getresponse()
            data = resp.read()
        except Exception:
            self.conn.close()
            self.conn = None
            raise
        self.last_used = time.monotonic()
        for name, value in resp.getheaders():
            if name.lower() == "set-cookie":
                key, _, rest = value.partition("=")
                val = rest.split(";", 1)[0]
                if val and "Max-Age=0" not in value and "Expires=Thu, 01 Jan 1970" not in value:
                    self.cookies[key] = val
                else:
                    self.cookies.pop(key, None)
        return resp.status, resp.getheader("Location"), data.decode("utf-8", "replace")

    def hit(self, label, method, path, form=None, expect=(200,), follow=True):
        """One request, timed and recorded; a redirect is followed like a browser does."""
        if form is not None:
            form = dict(form, csrf_token=self.csrf)
        start = time.monotonic()
        try:
            status, location, text = self._send(method, path, form)
            error = None if status in expect else f"HTTP {status}"
        except Exception as exc:  # a refused, reset or timed-out connection
            status, location, text, error = 0, None, "", type(exc).__name__
        self.record(label, time.time(), (time.monotonic() - start) * 1000, error)
        if error is None and status in (301, 302, 303) and follow and location:
            return self.hit(_label(location), "GET", urlsplit(location).path or "/", follow=False)
        return error is None, text

    def sign_in(self):
        ok, page = self.hit("sign-in page", "GET", "/login")
        if not ok:
            return False
        self.csrf = CSRF.search(page).group(1)
        ok, page = self.hit("sign in", "POST", "/login", {"email": self.email, "password": PASSWORD},
                            expect=(302,), follow=False)
        if ok:
            ok, page = self.hit("overview", "GET", "/app")
            match = CSRF.search(page)
            self.csrf = match.group(1) if match else self.csrf
        return ok

    def one_click(self):
        label = self.rng.choices([m[0] for m in MIX], weights=[m[1] for m in MIX])[0]
        ws, rng = self.ws, self.rng
        industry = rng.choice(ws["industries"])
        learner = ws["learner_id"]
        if label == "overview":
            self.hit(label, "GET", "/app")
        elif label == "industry page":
            self.hit(label, "GET", f"/app/industry/{industry}")
        elif label == "update a check":
            if DONE[industry] and rng.random() < 0.4:
                form = {"action": "done_today"}
                key = rng.choice(DONE[industry])
            else:
                form = {"action": "save", "answer": rng.choice(["yes", "no"])}
                key = rng.choice(YES_NO[industry])
            ok, _ = self.hit(label, "POST", f"/app/industry/{industry}/rule/{key}", form, expect=(302,))
            self.writes += ok
        elif label == "bulk form":
            keys = rng.sample(YES_NO[industry], min(3, len(YES_NO[industry])))
            ok, _ = self.hit(label, "POST", f"/app/industry/{industry}/bulk",
                             {"keys": keys, "bulk_action": rng.choice(["yes", "no"])}, expect=(302,))
            self.writes += len(keys) if ok else 0
        elif label == "academy home":
            self.hit(label, "GET", "/app/academy")
        elif label == "academy map":
            self.hit(label, "GET", f"/app/academy/{learner}")
        elif label in ("academy lesson", "academy quiz"):
            path = f"/app/academy/{learner}/world/1/stage/1"
            ok, page = self.hit("academy lesson", "GET", path)
            attempt = ATTEMPT.search(page) if ok else None
            if label == "academy quiz" and attempt:
                answers = {f"q{i}": rng.randrange(2) for i in set(QUESTION.findall(page))}
                self.hit(label, "POST", path, dict(answers, attempt=attempt.group(1)))
        elif label == "settings":
            self.hit(label, "GET", "/app/settings")
        elif label == "settings save":
            form = {k: "on" for k in ("email_reminders", "email_alerts") if rng.random() < 0.8}
            self.hit(label, "POST", "/app/settings/reminders", form, expect=(302,))
        elif label == "audit trail":
            self.hit(label, "GET", "/app/audit")
        elif label == "report":
            self.hit(label, "GET", "/app/report")


def _label(location):
    path = urlsplit(location).path
    for pattern, label in ((r"^/app/industry/\d+$", "industry page"), (r"^/app/settings$", "settings"),
                           (r"^/app$", "overview"), (r"^/app/academy", "academy lesson")):
        if re.match(pattern, path):
            return label
    return "other"


def _client_process(port, people, start_at, ramp, stop_at, think, seed_value, out):
    """Runs a share of the people as threads, then sends back what each request did."""
    rows = []
    lock = threading.Lock()
    writes = Counter()

    def record(label, at, ms, error):
        with lock:
            rows.append((label, at, ms, error))

    def run(index, ws, email):
        rng = random.Random(seed_value * 100003 + index)
        person = Person(port, ws, email, rng, record)
        time.sleep(max(0.0, start_at - time.time()) + rng.uniform(0, ramp))
        if not person.sign_in():
            return
        while time.time() < stop_at:
            person.one_click()
            if think:
                time.sleep(rng.uniform(0.5 * think, 1.5 * think))
        with lock:
            writes[ws["org_id"]] += person.writes

    threads = [threading.Thread(target=run, args=(i, ws, email), daemon=True) for i, (ws, email) in enumerate(people)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(stop_at - time.time() + 120)
    out.put((rows, dict(writes)))


def run_stage(port, people, seconds, think, ramp, processes, seed_value):
    start_at = time.time() + 1
    stop_at = start_at + ramp + seconds
    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    shares = [people[i::processes] for i in range(processes)]
    procs = [ctx.Process(target=_client_process,
                                     args=(port, share, start_at, ramp, stop_at, think, seed_value + i, queue))
             for i, share in enumerate(shares) if share]
    for p in procs:
        p.start()
    rows, writes = [], Counter()
    for _ in procs:
        got_rows, got_writes = queue.get()
        rows += got_rows
        writes.update(got_writes)
    for p in procs:
        p.join()
    return rows, writes, start_at + ramp, stop_at


def percentile(values, share):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(share * len(ordered)))] if ordered else 0


def summarize(rows, steady_from, steady_to):
    """Per page: count, failures, median and p95 (ms), over the steady part of
    the stage (after everyone signed in). Sign-in is measured over the ramp."""
    pages = defaultdict(list)
    errors = defaultdict(Counter)
    for label, at, ms, error in rows:
        if label in ("sign in", "sign-in page") or steady_from <= at <= steady_to:
            pages[label].append(ms)
            if error:
                errors[label][error] += 1
    steady = [r for r in rows if steady_from <= r[1] <= steady_to and r[0] not in ("sign in", "sign-in page")]
    total = len(steady)
    failed = sum(1 for r in steady if r[3])
    return {
        "rps": total / max(1e-9, steady_to - steady_from),
        "requests": total,
        "failed": failed,
        "pages": {k: (len(v), sum(errors[k].values()), statistics.median(v), percentile(v, 0.95), dict(errors[k]))
                  for k, v in sorted(pages.items())},
        "all_p50": statistics.median([r[2] for r in steady]) if steady else 0,
        "all_p95": percentile([r[2] for r in steady], 0.95),
    }


def log_problems(path, since_offset):
    """What the server log says went wrong after `since_offset` bytes."""
    found = Counter()
    with open(path, "rb") as f:
        f.seek(since_offset)
        for line in f:
            text = line.decode("utf-8", "replace")
            for needle, meaning in LOG_PROBLEMS.items():
                if needle in text:
                    found[meaning] += 1
    return found


def http_test(args):
    folder = tempfile.mkdtemp(prefix="omniarmor-load-")
    db_path = os.path.join(folder, "omniarmor.db")
    _, docker_workers, docker_threads = dockerfile_command()
    workers = args.workers or docker_workers
    threads = args.threads or docker_threads
    stages = [int(s) for s in args.stages.split(",")]
    t0 = time.time()
    workspaces = seed(db_path, args.workspaces, people=max(1, -(-max(stages) // args.workspaces)))
    print(f"Seeded {args.workspaces} workspaces in {time.time() - t0:.1f} s ({folder})")
    people = [(ws, email) for p in range(max(len(w["emails"]) for w in workspaces))
              for ws in workspaces for email in ws["emails"][p:p + 1]]
    proc, port = start_server(folder, db_path, workers, threads, scheduler=not args.no_scheduler)
    print(f"Server: gunicorn --workers {workers} --threads {threads} (the Dockerfile's command), port {port}")
    print(f"Each person waits {args.think:g} s on average between clicks; ramp {args.ramp:g} s, then"
          f" {args.seconds:g} s measured per stage.\n")
    log_path = os.path.join(folder, "server.log")
    total_writes = Counter()
    first_break = None
    try:
        for n, users in enumerate(stages):
            offset = os.path.getsize(log_path)
            peak = [0.0]
            sampling = threading.Event()

            def sample():
                while not sampling.wait(0.5):
                    peak[0] = max(peak[0], server_memory_mb(proc.pid))
            sampler = threading.Thread(target=sample, daemon=True)
            sampler.start()
            rows, writes, steady_from, steady_to = run_stage(port, people[:users], args.seconds, args.think,
                                                             args.ramp, args.processes, n * 1000 + 1)
            sampling.set()
            sampler.join()
            total_writes.update(writes)
            s = summarize(rows, steady_from, steady_to)
            problems = log_problems(log_path, offset)
            print(f"== {users} people at once: {s['rps']:.1f} requests/s, {s['requests']} requests,"
                  f" {s['failed']} failed ({100 * s['failed'] / max(1, s['requests']):.2f}%),"
                  f" all pages p50 {s['all_p50']:.0f} ms p95 {s['all_p95']:.0f} ms, server memory {peak[0]:.0f} MB")
            print(f"   {'page':<16}{'count':>7}{'failed':>8}{'p50 ms':>9}{'p95 ms':>9}  errors")
            for label, (count, failed, p50, p95, errs) in s["pages"].items():
                print(f"   {label:<16}{count:>7}{failed:>8}{p50:>9.0f}{p95:>9.0f}  {errs or ''}")
            if problems:
                print("   server log: " + ", ".join(f"{k} ({v})" for k, v in problems.items()))
            broke = []
            if s["failed"] > FAIL_SHARE * max(1, s["requests"]):
                broke.append(f"{100 * s['failed'] / s['requests']:.1f}% of requests failed")
            if s["all_p95"] > SLOW_P95_MS:
                broke.append(f"p95 {s['all_p95']:.0f} ms is over {SLOW_P95_MS} ms")
            broke += list(problems)
            if broke and first_break is None:
                first_break = (users, broke)
            print()
    finally:
        stop_server(proc)
    # Every change that came back saved must be in the audit trail.
    conn = connect(db_path)
    audited = Counter(dict(conn.execute(
        "SELECT org_id, COUNT(*) FROM audit WHERE action IN ('reading', 'done') GROUP BY org_id").fetchall()))
    server_errors = conn.execute("SELECT error, COUNT(*) FROM app_errors GROUP BY error ORDER BY 2 DESC").fetchall()
    conn.close()
    lost = {org: (n, audited.get(org, 0)) for org, n in total_writes.items() if audited.get(org, 0) != n}
    print(f"Saved changes: {sum(total_writes.values())} confirmed to the people, {sum(audited.values())} in the"
          f" audit trail; {len(lost)} workspaces don't match" + (f": {list(lost.items())[:5]}" if lost else "."))
    print("Server errors recorded: " + (", ".join(f"{e} ({c})" for e, c in server_errors) if server_errors else "none"))
    if first_break:
        print(f"First thing that broke: at {first_break[0]} people at once: {'; '.join(first_break[1])}")
    else:
        print("Nothing broke at these stages.")
    if args.keep:
        print(f"Kept {folder}")
    else:
        shutil.rmtree(folder, ignore_errors=True)
    return 0 if not lost else 1


# --- The sweeps ---------------------------------------------------------------------------------

class _SmtpSink(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """Just enough SMTP to accept mail, with an optional delay per message
    like a real provider's. Counts what each address received."""
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, delay):
        self.delay = delay
        self.received = Counter()
        self.lock = threading.Lock()
        super().__init__(("127.0.0.1", 0), _SmtpHandler)


class _SmtpHandler(socketserver.StreamRequestHandler):
    def handle(self):
        server = self.server
        self.wfile.write(b"220 sink\r\n")
        rcpts, subject = [], ""
        while True:
            line = self.rfile.readline()
            if not line:
                return
            word = line[:4].upper()
            if word in (b"EHLO", b"HELO"):
                self.wfile.write(b"250 sink\r\n")
            elif word == b"MAIL":
                rcpts, subject = [], ""
                self.wfile.write(b"250 ok\r\n")
            elif word == b"RCPT":
                rcpts.append(line.split(b"<", 1)[1].split(b">", 1)[0].decode())
                self.wfile.write(b"250 ok\r\n")
            elif word == b"DATA":
                self.wfile.write(b"354 go\r\n")
                while True:
                    data = self.rfile.readline()
                    if data in (b".\r\n", b".\n", b""):
                        break
                    if data.lower().startswith(b"subject:") and not subject:
                        subject = data[8:].strip().decode("utf-8", "replace")
                time.sleep(server.delay)
                with server.lock:
                    for r in rcpts:
                        server.received[(r, subject)] += 1
                self.wfile.write(b"250 queued\r\n")
            elif word == b"QUIT":
                self.wfile.write(b"221 bye\r\n")
                return
            else:
                self.wfile.write(b"250 ok\r\n")


def _sweep_cfg(folder, db_path, smtp_port):
    from omniarmor_app.config import load_config
    return load_config(DATABASE=db_path, BACKUP_DIR=os.path.join(folder, "backups"), SMTP_HOST="127.0.0.1",
                       SMTP_PORT=smtp_port, SMTP_STARTTLS=False, DAILY_JOB_HOUR_UTC=0,
                       BASE_URL="https://omniarmor.example.com", OPERATOR_EMAIL="operator@example.com",
                       SECRET_KEY="load-test")


def _sweep_in_process(cfg, start, out):
    """One server process's scheduled work: the alerts, then the daily run."""
    from omniarmor_app import jobs
    time.sleep(max(0.0, start - time.time()))
    a = jobs.run_alerts(cfg)
    d = jobs.run_daily(cfg)
    out.put((a, d))


def _check_once(db_path, sink, workspaces):
    """Every workspace got its digest and alerts, and nobody got any email twice."""
    conn = connect(db_path)
    rows = conn.execute("SELECT org_id, user_id, recipient, subject, status FROM notifications"
                        " WHERE kind = 'reminder'").fetchall()
    conn.close()
    per_org = defaultdict(lambda: {"digest": 0, "alert": 0})
    sent = Counter()
    for r in rows:
        # An alert's subject ends with the company in brackets; a digest's with the company.
        kind = "alert" if r["subject"].endswith(")") else "digest"
        per_org[r["org_id"]][kind] += 1
        sent[(r["recipient"], r["subject"])] += 1
    twice_db = sum(1 for v in sent.values() if v > 1)
    twice_smtp = sum(1 for v in sink.received.values() if v > 1)
    no_digest = [w["org_id"] for w in workspaces if per_org[w["org_id"]]["digest"] == 0]
    no_alert = [w["org_id"] for w in workspaces if per_org[w["org_id"]]["alert"] == 0]
    failed = sum(1 for r in rows if r["status"] != "sent")
    return {"emails": len(rows), "digests": sum(v["digest"] for v in per_org.values()),
            "alerts": sum(v["alert"] for v in per_org.values()), "twice": twice_db + twice_smtp, "no_digest": no_digest, "no_alert": no_alert,
            "not_sent": failed}


def sweep_test(args):
    import logging
    from omniarmor_app import autopilot, jobs
    logging.getLogger("omniarmor").setLevel(logging.WARNING)
    sizes = [int(s) for s in args.sizes.split(",")]
    print(f"Email: local SMTP sink, {args.smtp_ms:g} ms per message. Two people per workspace.\n")
    print(f"{'workspaces':>10} {'alerts sweep':>13} {'next minute':>12} {'daily run':>10} {'autopilot':>10} {'digests':>8} {'alerts':>7}"
          f" {'next pass':>9} {'twice':>6} {'missed':>7} {'2 procs':>8}")
    ok = True
    for n in sizes:
        folder = tempfile.mkdtemp(prefix="omniarmor-sweep-")
        sink = _SmtpSink(args.smtp_ms / 1000)
        threading.Thread(target=sink.serve_forever, daemon=True).start()
        try:
            db_path = os.path.join(folder, "omniarmor.db")
            workspaces = seed(db_path, n)
            cfg = _sweep_cfg(folder, db_path, sink.server_address[1])
            t = time.perf_counter()
            jobs.run_alerts(cfg)
            t_alerts = time.perf_counter() - t
            t = time.perf_counter()
            daily = jobs.run_daily(cfg)
            t_daily = time.perf_counter() - t
            t = time.perf_counter()
            autopilot.run(cfg, force=True)
            t_auto = time.perf_counter() - t
            first = _check_once(db_path, sink, workspaces)
            # The next minute's sweep and a forced daily run find nothing new to send.
            t = time.perf_counter()
            jobs.run_alerts(cfg)
            t_idle = time.perf_counter() - t
            jobs.run_daily(cfg, force=True)
            again = _check_once(db_path, sink, workspaces)["emails"] - first["emails"]

            # Two server processes sweeping the same fresh database at the same moment.
            db2 = os.path.join(folder, "two.db")
            seed(db2, n)
            sink.received.clear()
            cfg2 = _sweep_cfg(folder, db2, sink.server_address[1])
            cfg2["BACKUP_DIR"] = os.path.join(folder, "backups2")
            ctx = multiprocessing.get_context("spawn")
            queue = ctx.Queue()
            start = time.time() + 3
            procs = [ctx.Process(target=_sweep_in_process, args=(cfg2, start, queue)) for _ in range(2)]
            for p in procs:
                p.start()
            for _ in procs:
                queue.get()
            for p in procs:
                p.join()
            two = _check_once(db2, sink, workspaces)
            two_ok = two["twice"] == 0 and not two["no_digest"] and not two["no_alert"]
            missed = len(set(first["no_digest"]) | set(first["no_alert"]))
            print(f"{n:>10} {t_alerts:>12.1f}s {t_idle:>11.1f}s {t_daily:>9.1f}s {t_auto:>9.1f}s {first['digests']:>8} {first['alerts']:>7}"
                  f" {again:>9}"
                  f" {first['twice']:>6} {missed:>7} {'ok' if two_ok else 'WRONG':>8}")
            # "next pass": what the next minute's sweep and a forced daily run
            # sent. Only clocks that reached a new stage meanwhile belong there
            # (with a slow email provider, minutes pass); a repeat is "twice".
            if "failed" in (daily or "") or first["twice"] or missed or not two_ok or first["not_sent"]:
                ok = False
                print(f"   problem: daily={daily!r} first={ {k: v if not isinstance(v, list) else v[:5] for k, v in first.items()} }"
                      f" two={ {k: v if not isinstance(v, list) else v[:5] for k, v in two.items()} }")
        finally:
            sink.shutdown()
            sink.server_close()
            shutil.rmtree(folder, ignore_errors=True)
    return 0 if ok else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    h = sub.add_parser("http", help="many signed-in people using the app at once")
    h.add_argument("--workspaces", type=int, default=500)
    h.add_argument("--stages", default="50,100,250,500,1000", help="people at once, stage by stage")
    h.add_argument("--seconds", type=float, default=45, help="measured time per stage")
    h.add_argument("--ramp", type=float, default=15, help="seconds over which a stage's people sign in")
    h.add_argument("--think", type=float, default=3.0, help="average seconds between one person's clicks (0: none)")
    h.add_argument("--workers", type=int, help="gunicorn workers (default: the Dockerfile's WEB_CONCURRENCY)")
    h.add_argument("--threads", type=int, help="threads per worker (default: the Dockerfile's WEB_THREADS)")
    h.add_argument("--processes", type=int, default=4, help="client processes driving the people")
    h.add_argument("--no-scheduler", action="store_true", help="don't run the built-in timer in the server")
    h.add_argument("--keep", action="store_true", help="keep the temporary folder (database and server log)")
    s = sub.add_parser("sweep", help="time the scheduled jobs over many workspaces with running clocks")
    s.add_argument("--sizes", default="100,500,2000")
    s.add_argument("--smtp-ms", type=float, default=0, help="delay per email at the SMTP sink, in ms")
    args = parser.parse_args(argv)
    return http_test(args) if args.command == "http" else sweep_test(args)


if __name__ == "__main__":
    sys.exit(main())
