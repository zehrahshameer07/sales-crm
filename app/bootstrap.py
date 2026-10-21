"""Startup tasks: database migrations, the first admin account, and optional demo data."""
import logging
import random
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal, engine
from .enums import ActivityStatus, ActivityType, Product, UserRole
from .models import Activity, StatusHistory, User
from .security import hash_password, password_problems
from .timeutil import local_zone, today, utcnow

log = logging.getLogger("sales_crm")
BASE_DIR = Path(__file__).resolve().parent.parent

LEGACY_MESSAGE = (
    "This database contains the OLD version of the app (a table called 'activities' without migration history). "
    "The new version uses UUIDs and a users table, so the old table can't be upgraded in place. "
    "If it only holds demo data: locally delete crm.db; on a host, either recreate the database or set the "
    "environment variable RESET_LEGACY_SCHEMA=true for one deploy (it drops the old table), then remove the variable."
)


# ---------------------------------------------------------------- migrations
def run_migrations() -> None:
    tables = set(inspect(engine).get_table_names())
    if "activities" in tables and "alembic_version" not in tables:
        if not settings.reset_legacy_schema:
            raise RuntimeError(LEGACY_MESSAGE)
        log.warning("RESET_LEGACY_SCHEMA is on: dropping the old 'activities' table.")
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE activities"))

    config = Config(str(BASE_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BASE_DIR / "alembic"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


# --------------------------------------------------------------------- admin
def bootstrap_admin(db: Session) -> None:
    """Create the first admin from ADMIN_EMAIL / ADMIN_PASSWORD when there are no users yet."""
    if not (settings.admin_email and settings.admin_password):
        return
    if db.scalar(select(User.id).limit(1)) is not None:
        return
    problems = password_problems(settings.admin_password, email=settings.admin_email, name=settings.admin_name)
    if problems:
        raise RuntimeError("ADMIN_PASSWORD is too weak: " + " ".join(problems))
    db.add(User(
        full_name=settings.admin_name, email=settings.admin_email, role=UserRole.ADMIN,
        password_hash=hash_password(settings.admin_password), designation="Administrator",
    ))
    db.commit()
    log.info("Created the first admin account (%s).", settings.admin_email)


# ----------------------------------------------------------------- demo data
DEMO_PASSWORD = "Demo@12345"
DEMO_DOMAIN = "freebees-demo.com"

DEMO_USERS = [
    {"key": "admin", "name": "Aarav Sharma", "role": "admin", "email": f"admin@{DEMO_DOMAIN}",
     "region": "Head office", "designation": "Operations Head", "manager": None},
    {"key": "priya", "name": "Priya Nair", "role": "manager", "email": f"priya.nair@{DEMO_DOMAIN}",
     "region": "Bengaluru South", "designation": "Regional Sales Manager", "manager": "admin"},
    {"key": "rahul", "name": "Rahul Menon", "role": "manager", "email": f"rahul.menon@{DEMO_DOMAIN}",
     "region": "Bengaluru North", "designation": "Regional Sales Manager", "manager": "admin"},
    {"key": "ananya", "name": "Ananya Rao", "role": "salesperson", "email": f"ananya.rao@{DEMO_DOMAIN}",
     "region": "Koramangala", "designation": "Sales Executive", "manager": "priya"},
    {"key": "karthik", "name": "Karthik Shetty", "role": "salesperson", "email": f"karthik.shetty@{DEMO_DOMAIN}",
     "region": "Jayanagar", "designation": "Sales Executive", "manager": "priya"},
    {"key": "meera", "name": "Meera Iyer", "role": "salesperson", "email": f"meera.iyer@{DEMO_DOMAIN}",
     "region": "HSR Layout", "designation": "Sales Executive", "manager": "priya"},
    {"key": "vikram", "name": "Vikram Hegde", "role": "salesperson", "email": f"vikram.hegde@{DEMO_DOMAIN}",
     "region": "Indiranagar", "designation": "Sales Executive", "manager": "rahul"},
    {"key": "sneha", "name": "Sneha Kulkarni", "role": "salesperson", "email": f"sneha.kulkarni@{DEMO_DOMAIN}",
     "region": "Whitefield", "designation": "Sales Executive", "manager": "rahul"},
    {"key": "arjun", "name": "Arjun Reddy", "role": "salesperson", "email": f"arjun.reddy@{DEMO_DOMAIN}",
     "region": "Malleshwaram", "designation": "Sales Executive", "manager": "rahul"},
]

RESTAURANTS = [
    "Spice Garden", "Tandoor Tales", "Cafe Brew House", "Dosa Corner", "Biryani Junction", "Green Leaf Bistro",
    "The Coffee Lab", "Pizza Palace", "Chai Point Corner", "Meghana Foods", "Truffles Cafe", "Udupi Residency",
    "Toit Taproom", "Smoke House Deli", "Vidyarthi Bhavan", "CTR Dosa House", "Empire Kitchen", "Nagarjuna Meals",
    "Barbeque Nation", "Mavalli Tiffin Room", "Third Wave Coffee", "Corner House", "Church Street Social",
    "Beijing Bites", "Taco Fiesta", "Kerala Kitchen", "Punjabi Dhaba", "Sagar Fast Food", "Rameshwaram Cafe",
]
LOCATIONS = ["Indiranagar", "Koramangala", "HSR Layout", "Jayanagar", "Whitefield", "Malleshwaram", "Basavanagudi",
             "MG Road", "JP Nagar", "Marathahalli"]
NOTES = [
    "Owner liked the video menu", "Asked for pricing details", "Wants a Kannada and English menu",
    "Manager will decide next week", "Interested in game rewards for diners", "Signed up for a trial",
    "Needs a demo for the head chef", "Busy lunch hour, call after 3 pm", "Sent the proposal on WhatsApp",
    "Wants to compare with another vendor",
]
FOLLOW_UP_NOTES = ["Call back with revised pricing", "Share the demo video", "Confirm the trial start date",
                   "Meet the owner in person", "Send the contract draft"]


def _at(day, hour: int, minute: int) -> datetime:
    """A local business time (e.g. 11:30 IST on `day`) as a UTC timestamp."""
    return datetime.combine(day, time(hour, minute), tzinfo=local_zone()).astimezone(timezone.utc)


def seed_demo(db: Session) -> bool:
    """Create demo accounts and sample activities. Does nothing if users already exist."""
    if db.scalar(select(User.id).limit(1)) is not None:
        return False

    rng = random.Random(2026)
    people: dict[str, User] = {}
    password_hash = hash_password(DEMO_PASSWORD)
    for spec in DEMO_USERS:
        person = User(
            full_name=spec["name"], email=spec["email"], role=UserRole(spec["role"]), region=spec["region"],
            designation=spec["designation"], password_hash=password_hash,
            manager_id=people[spec["manager"]].id if spec["manager"] else None,
            phone=f"98{rng.randint(10000000, 99999999)}",
        )
        db.add(person)
        db.flush()
        people[spec["key"]] = person

    day = today()
    approver_for = {key: people[spec["manager"]] for key, spec in ((s["key"], s) for s in DEMO_USERS) if spec["manager"]}
    types = list(ActivityType)
    products = list(Product) + [None]

    for spec in DEMO_USERS:
        owner = people[spec["key"]]
        if spec["role"] == "admin":
            continue
        approver = approver_for[spec["key"]]
        used: set = set()
        count = rng.randint(9, 13) if spec["role"] == "salesperson" else rng.randint(3, 4)
        for _ in range(count):
            for _attempt in range(30):
                name = rng.choice(RESTAURANTS)
                kind = rng.choice(types)
                start = day - timedelta(days=rng.randint(0, 32))
                if (name.casefold(), kind, start) not in used:
                    used.add((name.casefold(), kind, start))
                    break
            else:
                continue

            age = (day - start).days
            roll = rng.random()
            if age >= 6:
                status = ActivityStatus.COMPLETED if roll < 0.7 else (
                    ActivityStatus.IN_PROGRESS if roll < 0.85 else ActivityStatus.PENDING)
            elif age >= 2:
                status = ActivityStatus.COMPLETED if roll < 0.4 else (
                    ActivityStatus.IN_PROGRESS if roll < 0.7 else ActivityStatus.PENDING)
            else:
                status = ActivityStatus.IN_PROGRESS if roll < 0.25 else ActivityStatus.PENDING

            end = None
            if status == ActivityStatus.COMPLETED:
                end = start + timedelta(days=min(age, rng.choice([0, 1, 1, 2, 2, 3, 4, 6, 8])))
            follow_up = None
            if status != ActivityStatus.COMPLETED and rng.random() < 0.5:
                follow_up = max(start, day + timedelta(days=rng.randint(-4, 7)))

            # Build the status timeline: logged -> (in progress) -> (completed), always increasing, never in the future
            reviewer = approver if spec["role"] == "salesperson" else people["admin"]
            moments = [(None, ActivityStatus.PENDING, owner, _at(start, rng.randint(9, 17), rng.randint(0, 59)))]
            if status == ActivityStatus.IN_PROGRESS or (status == ActivityStatus.COMPLETED and rng.random() < 0.5):
                moments.append((ActivityStatus.PENDING, ActivityStatus.IN_PROGRESS, reviewer,
                                moments[-1][3] + timedelta(hours=rng.randint(1, 20))))
            if status == ActivityStatus.COMPLETED:
                finished = max(moments[-1][3] + timedelta(hours=1), _at(end, 18, rng.randint(0, 59)))
                moments.append((moments[-1][1], ActivityStatus.COMPLETED, reviewer, finished))

            now = utcnow()
            previous_time = None
            fixed = []
            for old, new, who, when in moments:
                when = min(when, now - timedelta(minutes=2))
                if previous_time is not None and when <= previous_time:
                    when = previous_time + timedelta(minutes=1)
                previous_time = when
                fixed.append((old, new, who, when))

            activity = Activity(
                owner_id=owner.id, customer_name=name, activity_type=kind, status=status,
                product_interested=rng.choice(products), contact=f"9{rng.randint(100000000, 999999999)}",
                location=rng.choice(LOCATIONS), notes=rng.choice(NOTES), start_date=start, end_date=end,
                follow_up_date=follow_up, follow_up_notes=rng.choice(FOLLOW_UP_NOTES) if follow_up else None,
                created_by_id=owner.id, updated_by_id=fixed[-1][2].id,
                created_at=fixed[0][3], updated_at=fixed[-1][3],
            )
            db.add(activity)
            for old, new, who, when in fixed:
                db.add(StatusHistory(activity=activity, changed_by_id=who.id, from_status=old,
                                     to_status=new, changed_at=when))
    db.commit()
    log.info("Demo data created. Demo password for every account: %s", DEMO_PASSWORD)
    return True


def startup() -> None:
    if settings.auto_migrate:
        run_migrations()
    with SessionLocal() as db:
        bootstrap_admin(db)
        if settings.seed_demo:
            seed_demo(db)
