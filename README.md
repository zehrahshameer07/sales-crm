# FreeBees Sales CRM

A mobile-friendly Sales CRM designed to help manage restaurant sales activities. Salespeople can record calls, visits, demos, and follow-ups; managers can monitor team progress; and administrators can manage employees and review company-wide activity.

**Live Demo:** [https://sales-crm-qfdc.onrender.com](https://sales-crm-qfdc.onrender.com)

*Note: The first load may take around a minute if the hosted service has been inactive.*

## Screenshots

| Manager Dashboard | Mobile Dashboard |
| ----------------- | ---------------- |
|                   |                  |

## Features

- **Role-based authentication:** Separate access for administrators, managers, and salespeople.
- **Role-specific dashboards:** Personal activity summaries, team progress, and company-wide statistics.
- **Activity management:** Create, view, and edit sales activities with restaurant or customer details, activity type, product interest, dates, contact information, location, and notes.
- **Status tracking:** Manage the workflow from Pending to In progress to Completed, subject to role permissions.
- **Activity history:** Review recorded status changes.
- **Follow-up management:** Record follow-up dates and details and monitor upcoming or overdue follow-ups.
- **Reports and exports:** Filter activity data and download reports as CSV or PDF.
- **Employee management:** Administrators can create accounts, assign managers, deactivate employees, reset passwords, and unlock accounts.
- **Responsive interface:** Designed for desktop and mobile screens.
- **Database persistence:** Supports SQLite for local development and PostgreSQL for hosted deployment.

## Demo Accounts

The following accounts are intended for demo and review purposes. They are available only when the corresponding demo users have been configured in the database and demo login details are enabled.

| Role        | Email                          | Access                                          |
| ----------- | ------------------------------ | ----------------------------------------------- |
| Admin       | `admin@freebees-demo.com`      | Company-wide activities and employee management |
| Manager     | `priya.nair@freebees-demo.com` | Own activities and team progress                |
| Salesperson | `ananya.rao@freebees-demo.com` | Own activities                                  |

**Password for all demo accounts:** `Demo@12345`

These credentials are public for demonstration purposes.&#x20;

## Roles and Permissions

| Capability             | Salesperson                  | Manager                      | Admin                                |
| ---------------------- | ---------------------------- | ---------------------------- | ------------------------------------ |
| View activities        | Own activities               | Own and team activities      | All activities                       |
| Create activities      | For self                     | For self                     | According to application permissions |
| Edit activity details  | Own, subject to status rules | Own, subject to status rules | According to admin permissions       |
| Change activity status | Not permitted                | Team activities              | All activities                       |
| Dashboard              | Personal                     | Team                         | Company-wide                         |
| Team page              | No                           | Yes                          | Yes                                  |
| Reports and exports    | Permitted data               | Permitted team data          | Company data                         |
| Manage employees       | No                           | No                           | Yes                                  |

The backend enforces access permissions. Hiding an option in the interface is not a substitute for server-side authorization.

## Technology Stack

- **Backend:** Python, FastAPI
- **Database:** SQLite and PostgreSQL
- **ORM:** SQLAlchemy
- **Frontend:** HTML, CSS, JavaScript
- **Validation:** Pydantic
- **Testing:** Pytest
- **Deployment:** Render

## Quick Start — Local Setup

### Requirements

- Python 3.11 or later
- Git, if cloning the repository

### 1. Clone the repository

```bash
git clone https://github.com/zehrahshameer07/sales-crm.git
cd sales-crm
```

If the project is already on your computer, open a terminal in the project directory instead.

### 2. Create a virtual environment

On Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Configure local demo settings

For local demo testing, the login page can be configured to display the demo account details:

```powershell
$env:SHOW_DEMO_LOGINS = "true"
```

Demo-user seeding is a separate setting. Enable it only when you intend to create demo data and have confirmed how the current application handles database initialization:

```powershell
$env:SEED_DEMO = "true"
```

Do not enable demo seeding against a database containing real company data.

### 5. Run the application

```powershell
uvicorn app.main:app --reload --port 8000
```

Open the following URLs:

- **Web application:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **API documentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health check:** [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

If port 8000 is already occupied, use another port, such as `8001`, and open the corresponding URL.

## Project Structure

```text
app/
  main.py          Application setup and frontend serving
  config.py        Environment-based configuration
  models.py        Database models
  security.py      Authentication and security logic
  deps.py          Authentication dependencies and access checks
  schemas/         Request and response validation
  crud/            Database queries and business logic
  routers/         API endpoints
  services/        Supporting services and report generation

static/
  HTML, CSS, and JavaScript frontend

tests/             Automated tests
docs/              Database schemas, diagrams, and screenshots
requirements.txt   Python dependencies
```

## API Overview

The API is available under `/api`. Visit `/docs` while the application is running to view the available endpoints and request schemas.

| Area           | Purpose                                                                            |
| -------------- | ---------------------------------------------------------------------------------- |
| Authentication | Login, logout, current-user information, password changes, and login configuration |
| Users          | Employee and account management                                                    |
| Activities     | Create, retrieve, edit, update status, and view activity history                   |
| Dashboard      | Activity summaries and team statistics                                             |
| Reports        | Summary data and CSV/PDF exports                                                   |
| Health         | Application health check                                                           |

### Common HTTP Status Codes

| Code  | Meaning                                        |
| ----- | ---------------------------------------------- |
| `200` | Request successful                             |
| `201` | Resource created                               |
| `204` | Request successful with no response body       |
| `401` | Authentication required or credentials invalid |
| `403` | Authenticated user lacks permission            |
| `404` | Resource not found or not accessible           |
| `409` | Conflict, such as a duplicate record           |
| `422` | Request validation failed                      |
| `429` | Too many requests                              |

## Security

The application includes authentication, server-side permission checks, input validation, and protections for account operations.

Security measures documented for the project include:

- Password hashing.
- Session-cookie-based authentication.
- Login lockout and rate limiting.
- Role-based access enforcement.
- Validation of incoming data.
- Database constraints and duplicate prevention.
- Protection of application secrets through environment configuration.

For production deployment, use a strong private `SECRET_KEY`, secure account passwords, and the correct database connection string. Do not commit credentials or environment files to GitHub.

**Known limitations:** The application's protections and deployment configuration should be reviewed against the current code before production use. In-memory rate limiting may not be suitable for multiple application instances, and email-based password recovery or multi-factor authentication may require additional implementation.

## Database

The application uses a relational database to store user accounts, sales activities, and related activity history.

- SQLite can be used for local development.
- PostgreSQL is suitable for the hosted application.
- Database connection settings should be supplied through environment variables.
- Database migrations should be applied using the migration mechanism configured in the project.
- Database credentials must not be committed to source control.

The database schema and diagrams available in the repository's `docs/` directory provide additional implementation details.

## Reports and Exports

The reporting functionality supports filtering activity data and generating downloadable CSV and PDF reports.

The information available to a user should follow their assigned role and permissions. Export behaviour and record limits should be verified against the current implementation.

## Deployment — Render and PostgreSQL

The application can be hosted as a Render web service connected to the GitHub repository, with PostgreSQL configured as the database.

### Typical Render configuration

**Build command**

```bash
pip install -r requirements.txt
```

**Start command**

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**Health check path**

```text
/api/health
```

Configure the required environment variables in the Render service settings. These typically include:

| Variable           | Purpose                                                                                         |
| ------------------ | ----------------------------------------------------------------------------------------------- |
| `SECRET_KEY`       | Secret used by the application                                                                  |
| `DATABASE_URL`     | Database connection URL                                                                         |
| `PYTHON_VERSION`   | Supported Python runtime version                                                                |
| `SHOW_DEMO_LOGINS` | Controls whether demo login information is displayed, if supported by the current configuration |
| `SEED_DEMO`        | Demo-data initialization setting, if supported by the current configuration                     |

Use demo-related settings only when appropriate for the environment. Never enable demo seeding on a database containing real data without first understanding its effects.

### Deploying updates

When the repository is connected to Render:

1. Save and test changes locally.
2. Commit and push the changes to the connected GitHub branch.
3. Wait for automatic deployment, or start a manual deployment in Render.
4. Confirm the deployment succeeds.
5. Test the live login, dashboards, activities, history, and reports.

**Important:** A normal code deployment should not require deleting or recreating the PostgreSQL database. Do not enable database-reset settings as part of routine UI or documentation updates.

## Testing

Run the project's available tests from the repository root:

```powershell
python -m pytest
```

Tests requiring a separate database or additional environment variables may need further configuration. Use the test results and the current test suite to confirm coverage.

## Future Enhancements

Potential future improvements include a dedicated restaurant and lead pipeline, automated follow-up reminders, sales targets, scheduled report delivery, and additional integrations.

---

**Repository:** [https://github.com/zehrahshameer07/sales-crm](https://github.com/zehrahshameer07/sales-crm)
**Live Demo:** [https://sales-crm-qfdc.onrender.com](https://sales-crm-qfdc.onrender.com)
