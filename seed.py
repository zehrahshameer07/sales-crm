"""Create demo accounts and sample activities for local use.

    python seed.py            # only if the database has no users yet
    python seed.py --reset    # wipe users, activities and history first, then seed (local use only)
"""
import sys

from app.bootstrap import DEMO_PASSWORD, DEMO_USERS, run_migrations, seed_demo
from app.config import settings
from app.database import SessionLocal
from app.models import Activity, StatusHistory, User

if __name__ == "__main__":
    reset = "--reset" in sys.argv
    if reset and settings.is_production:
        raise SystemExit("Refusing to --reset in production.")

    run_migrations()
    with SessionLocal() as db:
        if reset:
            db.query(StatusHistory).delete()
            db.query(Activity).delete()
            db.query(User).delete()
            db.commit()
        if seed_demo(db):
            print(f"Demo data created. Password for every demo account: {DEMO_PASSWORD}\n")
            for person in DEMO_USERS:
                print(f"  {person['role']:<12} {person['email']}")
        else:
            print("The database already has users, so nothing was added. Use --reset to start over.")
