# Sales CRM – FreeBees

**Live demo:** https://sales-crm-qfdc.onrender.com

*Free hosting: the first load after a period of inactivity can take about a minute while the server wakes up.*

A simple, mobile-friendly Sales CRM for recording and tracking daily sales activities related to restaurant customers.

The application includes a dashboard, activity management form, REST API, and database integration.

![Sales CRM Dashboard](docs/screenshots/dashboard.png)

| Activities | Add / Edit Form |
|---|---|
| ![Activities](docs/screenshots/activities.png) | ![Mobile Form](docs/screenshots/form-mobile.png) |

## Features

- Dashboard with activity counts, completion rate, charts, and recent activities.
- Add, view, and edit sales activities.
- Search by customer name and filter by status or date period.
- Track Calls, Visits, Demos, and Follow-ups.
- Dashboard "Time to complete" card showing average, fastest, and slowest days from start date to end date.
- Record start dates, notes, and optional contact details, location, product interest, and end dates.
- Validate inputs on both the frontend and backend.
- Enforce activity status and date rules on the server.
- Responsive layout for desktop and mobile.
- Automated API tests using pytest.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, FastAPI |
| ORM and validation | SQLAlchemy, Pydantic |
| Database | SQLite for local development; PostgreSQL for deployment |

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/zehrahshameer07/sales-crm.git
cd sales-crm
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
```

On Windows PowerShell:

```powershell
venv\Scripts\Activate.ps1
```

On macOS/Linux:

```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the application

```bash
uvicorn app.main:app --reload
```

Open the application at http://127.0.0.1:8000.

The application creates database tables automatically when it starts. To add sample activities locally, run `python seed.py` in a separate terminal with the virtual environment activated.

### 5. Run the tests

```bash
pytest
```

Interactive API documentation is available at http://127.0.0.1:8000/docs.

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/activities` | Create an activity |
| `GET` | `/api/activities` | Retrieve and filter activities |
| `PATCH` | `/api/activities/{id}` | Edit an activity |
| `GET` | `/api/stats` | Retrieve dashboard statistics |

## Business Rules

- Activity status progresses from Pending to In Progress to Completed.
- Completed activities cannot be reopened.
- Start dates can be backdated but cannot be in the future.
- End dates are optional and apply only to completed activities.
- The server validates inputs and enforces business rules.

## Project Structure

```text
sales-crm/
├── app/
│   ├── main.py
│   ├── crud.py
│   ├── models.py
│   ├── schemas.py
│   ├── database.py
│   └── demo_data.py
├── static/
├── tests/
├── docs/
│   ├── schema.sql
│   └── screenshots/
├── seed.py
├── requirements.txt
└── README.md
```

## Database Schema

The application uses SQLite for local development and PostgreSQL for deployment when configured with a PostgreSQL `DATABASE_URL`. The SQL schema is available in [`docs/schema.sql`](docs/schema.sql).

The `activities` table stores the customer name, activity type, status, contact details, location, product interest, notes, start date, end date, and record creation time.

## Implementation Approach

- **Layered backend:** API routes, database operations, models, and validation schemas are separated into modules.
- **Server-side validation:** Business rules are enforced by the backend rather than relying only on the frontend.
- **Database-driven dashboard:** Statistics are provided through the dashboard API.
- **Single application:** FastAPI serves both the API and frontend, so no separate frontend build step is required.
- **Safer rendering:** User-provided text is rendered using `textContent` rather than `innerHTML`.

## Scope and Limitations

This version focuses on activity management, dashboard statistics, API functionality, and database integration.

It does not currently include authentication or separate admin and salesperson accounts. The profile and logout controls are demonstration-only.

## Future Improvements

- Authentication and role-based access.
- Assign activities to individual salespeople.
- Follow-up reminders, reports, and CSV export.

## Deployment on Render

**Live URL:** https://sales-crm-qfdc.onrender.com

### Why Render with PostgreSQL?

- **Fits the stack:** Render runs a Python web service from a GitHub repository, allowing FastAPI to serve the API and frontend from one service.
- **Persistent data:** A separate PostgreSQL database is suitable for deployed records because a web service's local filesystem should not be relied on for persistent application data.
- **Secrets stay out of Git:** The database connection string should be stored as an environment variable in the Render dashboard, not committed to the repository.
- **Simple deployment:** Pushing to `main` can trigger an automatic redeploy when automatic deploys are enabled. Render provides HTTPS for the service URL.

### Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | Yes for PostgreSQL deployment | PostgreSQL connection string. If omitted, the application may use its local SQLite default. Configure the actual value in Render and keep it secret. |
| `SEED_DEMO` | Optional | If supported by the application, setting this to `true` can populate an empty database with sample activities. |
| `PYTHON_VERSION` | Optional | Can be used to configure the Python version used by Render. |

An `.env.example` file can document variable names without containing real credentials. Keep `.env` files and other files containing secrets out of Git.

### Deployment Steps

1. Push the repository to GitHub.
2. In Render, create a PostgreSQL database.
3. Create a Web Service from the GitHub repository in the same region as the database.
4. Set the build command to:

   ```bash
   pip install -r requirements.txt
   ```

5. Set the start command to:

   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

6. Configure `DATABASE_URL` in the Render service's environment settings using the database's internal connection URL.
7. Deploy the service and check the logs to confirm it starts successfully.

### Data Persistence

The intended production setup stores data in a separate PostgreSQL database so records can survive web-service restarts and redeployments. Confirm the Render service is connected to PostgreSQL and test persistence before relying on this behavior.

### Redeploying

When automatic deploys are enabled, pushing to `main` can trigger a new deployment. Database records should remain intact when stored in the external PostgreSQL database. Future schema changes may require a migration tool such as Alembic.

### Free-Plan Limitations

- The free web service can sleep after inactivity, so the first request may take about a minute.
- Free PostgreSQL databases have time limits and resource restrictions. Check Render's current plan terms before using the service for long-term data.