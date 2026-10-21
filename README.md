# FreeBees Sales CRM

A mobile-friendly Sales CRM where salespeople record their daily activities (calls, visits, demos, follow-ups) for restaurants, managers track their team's progress, and admins manage people and monitor everything.

**Live demo:** _add your Render URL here_  
*(Free hosting: the first load after inactivity can take about a minute while the server wakes up.)*

| Manager dashboard | Phone |
|---|---|
| ![Manager dashboard](docs/screenshots/dashboard-manager.png) | ![Phone](docs/screenshots/mobile-dashboard.png) |

## Demo accounts

On a demo deployment (`SEED_DEMO=true`) the login screen lists these, with a "Fill in" button. Password for **every** demo account: `Demo@12345`

| Role | Email | What they see |
|---|---|---|
| Admin | `admin@freebees-demo.com` | Everyone, plus the Employees screen |
| Manager | `priya.nair@freebees-demo.com` | Their own and their team's activities and progress |
| Salesperson | `ananya.rao@freebees-demo.com` | Only their own activities |

> Demo passwords are public on purpose. Never use `SEED_DEMO` with real data. For a real deployment use `ADMIN_EMAIL` / `ADMIN_PASSWORD` instead (see Deployment).

## Features

- **Login with three roles:** admin, manager, salesperson. Every query is limited by role on the server.
- **Role-based dashboards:** personal for salespeople; team with a per-employee progress table for managers; company-wide with team summaries and top performers for admins.
- **Activities:** add and edit (customer, type, product, start date that can be backdated, contact, location, notes, follow-up date and details), search, filters, pagination.
- **Status workflow:** new activities start *Pending*. Only an admin (any activity) or a manager (their team's) can move them forward: Pending → In progress → Completed. Completed is final. Every change is recorded in an audit history.
- **Time to complete:** start date to end date, shown as average / fastest / slowest, per person, team and company.
- **Follow-ups:** follow-up date and notes, with overdue and due-today counts on the dashboard.
- **Reports:** filter by date range, person, status and type; preview on screen; download as **CSV** or **PDF**.
- **Employees (admin):** create accounts, assign managers, deactivate, reset passwords, unlock locked accounts.
- **Security:** Argon2 passwords, HttpOnly session cookie, login lockout and rate limiting, UUID ids, duplicate prevention. See below.
- **Mobile-first UI** with light and dark themes.

## Roles and permissions

| | Salesperson | Manager | Admin |
|---|---|---|---|
| Log in | ✅ | ✅ | ✅ |
| See activities | own | own + direct reports | everyone |
| Create activities | own (starts Pending) | own | for anyone |
| Edit activity details | own, until completed | own, until completed | any |
| Change status | ❌ (403) | their team's only | any |
| Set an end date after completion | ❌ | ❌ | ✅ |
| Dashboard | personal | team | company |
| Team page | ❌ | ✅ | ✅ |
| Reports and exports | own data | team data | all data |
| Manage employees | ❌ | ❌ | ✅ |

A manager approves their team's work, not their own: their own activities are approved by an admin.

## Quick start (local)

Requires Python 3.11+.

```bash
python -m venv venv
venv\Scripts\activate              # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements-dev.txt

# Run with demo data and the demo accounts on the login screen:
set SEED_DEMO=true                 # Windows cmd   (PowerShell: $env:SEED_DEMO="true"; Mac/Linux: export SEED_DEMO=true)
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 (API docs: http://127.0.0.1:8000/docs).

The database (`crm.db`, SQLite) and its tables are created automatically on first start through Alembic migrations. If you have an `crm.db` from the old version 1, delete it first.

Other commands:

```bash
python seed.py --reset             # wipe and re-create the demo data (local only)
pytest                             # run the tests
python scripts/make_er_diagram.py  # regenerate the database diagrams
```

## Tests

`pytest` runs ~79 tests covering login, lockout and rate limiting, session security, roles and permissions, scoping, duplicates, status rules, end dates, UUIDs, dashboards, CSV/PDF exports, migrations and demo data. The suite also runs against PostgreSQL: `TEST_DATABASE_URL=postgresql://user:pass@localhost/db pytest`. GitHub Actions runs both on every push (`.github/workflows/ci.yml`).

## Project structure

```
app/
  main.py          app setup, security headers, serves the frontend
  config.py        settings from environment variables
  models.py        tables: users, activities, status_history
  enums.py         role / type / status / product enums
  security.py      password hashing, session tokens, password rules, rate limiter
  deps.py          "who is logged in" and role checks
  errors.py        one error type -> consistent HTTP status codes
  schemas/         request validation and response shapes
  crud/            business rules and database queries (users, activities, stats)
  routers/         API endpoints (auth, users, activities, stats, reports, health)
  services/        CSV and PDF generation
  bootstrap.py     startup: migrations, first admin, demo data
alembic/           database migrations
static/            the web app (HTML, CSS, JavaScript modules, no build step)
tests/             automated tests
docs/              ER diagram, schema.sql, screenshots
scripts/           diagram generator
```

## API overview

All endpoints are under `/api`. Interactive docs are at `/docs` (log in first with `POST /api/auth/login`; the session cookie is then used automatically).

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `POST /auth/change-password`, `GET /auth/config` |
| Users (admin) | `GET/POST /users`, `GET/PATCH /users/{id}`, `POST /users/{id}/reset-password`, `POST /users/{id}/unlock`; `GET /users/options` (any role: people you may filter by) |
| Activities | `GET/POST /activities`, `GET/PATCH /activities/{id}`, `POST /activities/{id}/status`, `GET /activities/{id}/history` |
| Dashboard | `GET /stats/overview`, `GET /stats/team` (manager, admin) |
| Reports | `GET /reports/summary`, `GET /reports/activities.csv`, `GET /reports/activities.pdf` |
| Health | `GET /health` |

### HTTP status codes

| Code | When |
|---|---|
| 200 / 201 / 204 | OK / created / done with no content (logout) |
| 401 | Not logged in, expired session, wrong email or password (always the same message) |
| 403 | Logged in but not allowed (e.g. a salesperson changing status), deactivated account, must change password first |
| 404 | Doesn't exist **or isn't yours** (so IDs can't be probed) |
| 409 | Conflict: duplicate activity, duplicate email, status moving backwards or to the same value |
| 422 | Invalid data (bad format, dates in the future, end date before start, weak password) |
| 429 | Too many attempts: login lockout, per-IP login limit, too many writes or exports. Includes `Retry-After` |

## Security

| Area | What is done |
|---|---|
| Passwords | Argon2id hashes; minimum 10 characters with letters and numbers; common passwords rejected; never returned or logged |
| Login | Same error for wrong password and unknown email (and the same response time); account lock after 5 failures for 15 minutes; per-IP rate limit; a deactivated account is only revealed after the correct password |
| Sessions | Signed token in an **HttpOnly, Secure, SameSite=Strict** cookie (JavaScript can't read it; not sent on cross-site requests). The user is re-checked in the database on every request, so deactivating someone or changing a password logs out all their sessions immediately |
| Authorization | Every query is scoped by role on the server. Other people's records return 404. The UI only hides things for convenience |
| IDs | UUIDs everywhere, so nobody can guess an ID or count your records |
| Data integrity | Real database enums, CHECK constraints, a unique rule that blocks duplicates, foreign keys |
| Input / output | Pydantic validation; ORM parameterised queries (no SQL injection); text rendered with `textContent` (no XSS); CSV cells starting with `= + - @` are neutralised (formula injection) |
| Browser protections | Content-Security-Policy (scripts and styles only from the app itself), `X-Frame-Options: DENY`, `nosniff`, HSTS in production, `no-store` on API responses |
| Secrets | `SECRET_KEY` and `DATABASE_URL` only in environment variables. The app refuses to start in production without a strong `SECRET_KEY` |

**Known limits:** rate limits are kept in memory (one server instance; use Redis for several); no two-factor login; sessions can't be revoked individually (changing the password revokes them all); passwords can't be self-reset by email.

## Database

![ER diagram](docs/er-diagram.png)

Full diagram, Mermaid version and tool links: [docs/ER_DIAGRAM.md](docs/ER_DIAGRAM.md). SQL: [docs/schema.sql](docs/schema.sql). DBML for dbdiagram.io: [docs/schema.dbml](docs/schema.dbml).

- **Three tables:** `users`, `activities`, `status_history`.
- **UUID primary keys** on all tables.
- **Enums:** `user_role`, `activity_type`, `activity_status`, `product` are real PostgreSQL enum types (text + CHECK on SQLite).
- **Timestamps (UTC):** `users` and `activities` have `created_at` and `updated_at`; activities also record `created_by` / `updated_by`. `status_history` is an append-only log, so each row has a single `changed_at`. The UI shows times in local time.
- **Duplicate rule:** unique on (salesperson, customer, activity type, start date). Customer names are compared ignoring capitals and extra spaces. A call and a visit to the same restaurant on one day are different; the same salesperson logging the same visit twice is a duplicate (409).
- **Migrations:** managed with Alembic (`alembic/versions`). The app applies them automatically on startup (`AUTO_MIGRATE`, default on). Run manually with `alembic upgrade head`.

## Reports and exports

The Reports page filters by start-date range, person, status and type, shows a preview, and downloads **CSV** (opens in Excel; up to 5,000 rows) or **PDF** (summary tables plus the first 500 activities). Exports only contain what the logged-in user is allowed to see. PDF uses a built-in font, so unusual non-Latin characters may not print.

## Deployment (Render + PostgreSQL)

Why this setup: Render deploys a Python service straight from GitHub, FastAPI serves both the API and the frontend (one service, no CORS), and a separate managed PostgreSQL database keeps data safe across restarts and redeploys (the free web service's disk is temporary, so SQLite would lose data).

1. Push the repository to GitHub.
2. In Render create a **PostgreSQL** database (free plan). Copy its **Internal Database URL**.
3. Create a **Web Service** from the repo, in the same region:
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Health check path: `/api/health`
4. Add environment variables:

| Variable | Value |
|---|---|
| `SECRET_KEY` | **required.** A long random string: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DATABASE_URL` | the Internal Database URL |
| `PYTHON_VERSION` | `3.12.7` |
| `SEED_DEMO` | `true` for a demo site (creates demo accounts when the database is empty) |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | for a real site, instead of `SEED_DEMO`: creates the first admin |

Render sets `RENDER=true`, which switches the app to production mode (secure cookies, HSTS, strict `SECRET_KEY` check). Tables are created by the migrations on first start. Pushing to `main` redeploys; data is kept.

### Upgrading an existing version 1 deployment

Version 1 used a table with integer IDs, which can't be converted in place. If it only holds demo data:

1. Add `SECRET_KEY` and `RESET_LEGACY_SCHEMA=true` (plus `SEED_DEMO=true` for demo accounts).
2. Deploy. The old table is dropped and the new schema is created.
3. **Remove `RESET_LEGACY_SCHEMA`** and redeploy once more.

(Or recreate the Render database, which gives the same result.)

### Checking persistence

Log in, add an activity, restart the service in Render, then redeploy. The activity is still there, because data lives in PostgreSQL and the app only seeds an empty database.

## Design decisions

- **Rules on the server, hints in the UI:** the API decides who may do what and returns the permission flags for each activity, so the browser never has to guess.
- **Status approval:** salespeople record work; a manager or admin confirms progress, which makes time-to-complete a trustworthy measure.
- **Start date vs created time:** salespeople often log a visit a day later, so the business date (start date) is separate from the technical timestamp, and dashboards use the start date.
- **Business timezone:** "today" is computed in `APP_TIMEZONE` (India by default), not the server's UTC date.
- **Soft removal:** people are deactivated, not deleted, so history stays intact.
- **No build step:** plain ES modules; nothing to compile.

## Roadmap

A `customers` table with a lead pipeline; reminders by email or WhatsApp; sales targets; scheduled report emails; GPS check-in and photo attachments; surveys; offline mode (PWA); two-factor login or SSO; Redis-backed rate limits; multi-level management hierarchy; comments on activities.
