# OmniArmor.ai

**Catch the fine before it catches you.**

A self-running compliance service for 50 regulated industries. Each industry
has ten checks covering the compliance failures that cost businesses in that
industry the most: common, expensive when missed, and cheap to prevent with a
deadline, a threshold or a checklist. That is 500 checks in all.

Companies sign up, pick their industries and enter each date or reading once.
From then on OmniArmor:

- **Tracks deadlines by itself:** it counts the days from each saved date, every day, in the company's timezone.
- **Sends reminders:** one email per team member when something is 30, 7 or 1 day from due, due today, or overdue (weekly). Missed days catch up, and failed emails are retried.
- **Restarts recurring duties:** pressing Done today starts the next cycle.
- **Keeps the record:** every change is in the audit trail with who and when. Printable reports and CSV exports are ready for inspectors.
- **Backs itself up:** daily database backups, with old copies pruned.

Every check answers **Cleared**, **Warning** or **Blocked** and names the rule
it applies. This is decision support, not legal advice: confirm each rule with
a compliance professional for your jurisdiction.

## Run it

```sh
pip install -r requirements.txt
flask --app wsgi run --port 8000          # development, at http://localhost:8000
python3 -m unittest discover -s tests     # 99 tests
```

Production: see [docs/OPERATIONS.md](docs/OPERATIONS.md) (Render one-click
blueprint or Docker, email setup, backups, monitoring). How the pieces fit:
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Layout

| Path | What it is |
|---|---|
| `omniarmor_app/` | The web app: accounts, workspaces, tracking, reminders, reports, daily jobs |
| `omni_armor_rules/` | The 500 rules (`group_1.py` … `group_10.py`) and the one `evaluate` every rule uses |
| `omni_armor_platform.py` | The original engine: 25 detailed checks and the console demo |
| `dashboard/` | A standalone demo page of all 500 checks, built from the catalog |
| `tests/` | Tests for the engine, the catalog, the web app and the dashboard |
| `Dockerfile`, `render.yaml`, `.github/workflows/ci.yml` | Packaging, hosting and automatic test runs |

## Turning this into a C corporation

That's a legal filing only the founders can make. The usual path for a
software startup:

1. **Incorporate in Delaware** as a C corporation, directly with the Delaware
   Division of Corporations or through a service such as Stripe Atlas or Clerky.
   You'll need a registered agent in Delaware.
2. **Get an EIN** from the IRS (free, online, at irs.gov).
3. **Register to do business** in the state where you operate (a "foreign
   qualification"), if that isn't Delaware.
4. **Issue founder stock** and file an **83(b) election** with the IRS within
   30 days of receiving it.
5. **Adopt bylaws**, open a business bank account, and assign the code and the
   OmniArmor name to the company.

A startup lawyer and an accountant should review each step. They're also the
people to write your Terms of Service and Privacy Policy.
