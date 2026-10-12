# Sales CRM (FreeBees)

A simple, mobile-friendly Sales CRM for logging and viewing daily sales activities for restaurant customers.
Built as a small end-to-end application: dashboard, form, REST API and database.

![Dashboard](docs/screenshots/dashboard.png)

| Activities | Add / edit form (mobile) |
|---|---|
| ![Activities](docs/screenshots/activities.png) | ![Form](docs/screenshots/form-mobile.png) |

## Features
- **Dashboard:** KPI cards (Total, Pending, In progress, Completed), completion rate, activities per day for the last 7 days, breakdown by activity type and product interest, a **time-to-complete** card (average / fastest / slowest days) and a recent-activity list
- Period filter on the dashboard: Today / Week / Month / All (based on the activity **start date**)
- **Add and edit activities** (modal on desktop, bottom sheet on mobile): customer/restaurant name, activity type, status, start date, notes, plus optional end date, contact number, location and product interested in
- **Start date can be backdated** (for example, a visit made yesterday and logged today); the **end date** is optional and set when an activity is completed
- **Status rules:** status only moves forward (Pending, then In Progress, then Completed). A completed activity's status is locked. The server enforces this, not just the UI
- **Activities page:** full list (newest start date first) with name search, status filter and period filter
- Validation in the browser and on the server, with errors shown next to the right field
- Mobile-first responsive layout: bottom navigation and a floating add button on phones, top navigation on desktop
- User menu with a demo profile and a logout button (demo only, see "Login" below)
- Automated API tests (pytest)

## Tech stack
| Layer | Choice |
|---|---|
| Frontend | HTML, CSS, vanilla JavaScript (served by the backend, no build step) |
| Backend | Python, FastAPI |
| ORM / validation | SQLAlchemy, Pydantic |
| Database | SQLite by default; MySQL/PostgreSQL via `DATABASE_URL` |

## Project structure
```
sales-crm/
├── app/
│   ├── main.py       # API routes + serves the frontend
│   ├── crud.py       # database queries and business rules
│   ├── models.py     # table definition
│   ├── schemas.py    # validation rules and response shapes
│   └── database.py   # DB connection (configurable)
├── static/           # index.html, style.css, app.js
├── tests/            # pytest API tests
├── docs/             # schema.sql and screenshots
├── seed.py           # optional demo data
├── migrate.py        # upgrades an older crm.db (see below)
├── requirements.txt
└── README.md
```

## Setup and run
```bash
git clone https://github.com/zehrahshameer07/sales-crm.git
cd sales-crm
python -m venv venv
venv\Scripts\activate            # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python seed.py                   # optional: add demo data
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000  (interactive API docs: http://127.0.0.1:8000/docs)

The SQLite file `crm.db` and the table are created automatically on first run.

### Run tests
```bash
pytest
```

### Login / demo credentials
There is **no login** in this version, as agreed in the revised scope, so no credentials are needed.
The user icon in the header shows a static demo profile ("Demo User") with a logout button for demonstration only. It stores nothing.

## API
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/activities` | Create an activity (201; 422 for invalid data; 400 if a business rule is broken) |
| GET | `/api/activities` | List activities, newest start date first. Query: `period` (today/week/month/all), `status`, `search` |
| PATCH | `/api/activities/{id}` | Edit an activity or change its status. Send only the fields that changed (404 if not found; 400 if a rule is broken) |
| GET | `/api/stats` | Dashboard data: status counts, completion rate, time-to-complete, counts by type and product, last 7 days. Query: `period` |

Example request:
```json
POST /api/activities
{
  "customer_name": "Spice Garden",
  "activity_type": "Visit",
  "status": "Pending",
  "start_date": "2026-10-11",
  "contact": "9876543210",
  "location": "Indiranagar",
  "product_interested": "FreeBees-Menu",
  "notes": "Owner liked the video menu"
}
```

### Business rules (enforced by the server)
- Status can only move forward: Pending, then In Progress, then Completed. Completed cannot be changed back.
- Start date defaults to today, can be backdated, and cannot be in the future.
- End date is optional, only allowed on completed activities, cannot be before the start date or in the future. Completing an activity without an end date sets it to today.

## Database schema: `activities`
The full SQL is in [`docs/schema.sql`](docs/schema.sql).

| Column | Type | Rules |
|---|---|---|
| id | Integer | Primary key, auto-generated |
| customer_name | String(120) | Required, 2-120 characters |
| activity_type | String(30) | Required: Call, Visit, Demo, Follow-up |
| status | String(30) | Required: Pending, In Progress, Completed |
| contact | String(20) | Optional, valid phone format |
| location | String(120) | Optional |
| product_interested | String(30) | Optional: FreeBees-Menu, FreeBees-Play, Both |
| notes | Text | Optional, max 500 characters |
| start_date | Date | Required, defaults to today, not in the future |
| end_date | Date | Optional, completed activities only |
| created_at | DateTime | Set automatically when the record is logged |

## Approach and design decisions
- **Layered backend:** routes (`main.py`) call query functions (`crud.py`), which use models (`models.py`). Validation lives in `schemas.py`. Each concern can change without touching the others.
- **Validation twice:** the browser gives instant feedback; the server is the real safety check. Bad formats are rejected with 422 and broken business rules with 400.
- **Rules live on the server:** the status and date rules are in `crud.py`, so they hold no matter what client calls the API. The UI only mirrors them for convenience.
- **Dates, not timestamps:** salespeople often log work a day later, so activities have an explicit start date. The dashboard uses it, and start-to-end time gives a simple measure of how fast an activity is converted.
- **Dashboard data comes from one endpoint:** `GET /api/stats` aggregates in the database, so the browser never downloads every record to count them.
- **Single deployable:** FastAPI serves the API and the frontend, so there is one command to run and no CORS configuration.
- **XSS-safe rendering:** user text is rendered with `textContent`, never `innerHTML`.
- **Extensible:** changing the database is one environment variable; new fields or endpoints follow the same model, schema, crud, route pattern.
- **Tested:** 25 API tests cover creation, validation, filters, editing, status rules, dates and stats.
- **Scope:** a single-user app with no login, as agreed in the revised scope.

## Possible next steps
- Login and roles (admin / salesperson), with each activity linked to its salesperson, so time-to-complete can be compared per person
- Separate `customers` table so one restaurant has many activities
- Delete activities, pagination
- Follow-up reminders, reports and CSV export
