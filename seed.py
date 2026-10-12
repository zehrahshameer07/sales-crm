"""Optional: fill the database with demo data.  Run: python seed.py"""
from datetime import date, datetime, timedelta

from app import models
from app.database import Base, SessionLocal, engine

Base.metadata.create_all(bind=engine)

SAMPLES = [
    # name, type, status, contact, location, product, notes, days_ago (start), days_taken (completed only)
    ("Spice Garden", "Visit", "Completed", "9876543210", "Indiranagar", "FreeBees-Menu", "Owner liked the video menu", 0, 0),
    ("Tandoor Tales", "Call", "Pending", "9123456780", "Koramangala", "FreeBees-Play", "Call back after lunch rush", 0, None),
    ("Cafe Brew House", "Demo", "In Progress", "9988776655", "HSR Layout", "Both", "Demo done, waiting for manager approval", 1, None),
    ("Dosa Corner", "Follow-up", "Completed", None, "Jayanagar", "FreeBees-Menu", "Signed up for trial", 1, 1),
    ("Biryani Junction", "Visit", "Pending", "9090909090", "Whitefield", "Both", None, 2, None),
    ("Green Leaf Bistro", "Call", "Completed", "9812345670", "Indiranagar", "FreeBees-Play", "Interested in game rewards", 2, 1),
    ("The Coffee Lab", "Demo", "Completed", "9845012345", "Koramangala", "FreeBees-Menu", "Wants Kannada and English menu", 3, 2),
    ("Pizza Palace", "Follow-up", "In Progress", "9900112233", "HSR Layout", "Both", "Sent pricing on WhatsApp", 3, None),
    ("Chai Point Corner", "Call", "Pending", "9871234560", "Malleshwaram", None, None, 4, None),
    ("Meghana Foods", "Visit", "Completed", "9777788888", "Jayanagar", "FreeBees-Menu", "Manager agreed to a pilot", 5, 3),
    ("Truffles Cafe", "Demo", "Pending", "9666655555", "Indiranagar", "FreeBees-Play", "Reschedule demo for next week", 6, None),
    ("Udupi Residency", "Visit", "Completed", None, "Basavanagudi", "FreeBees-Menu", "Signed up", 20, 6),
]

db = SessionLocal()
today = date.today()
for name, typ, status, contact, loc, product, notes, days_ago, days_taken in SAMPLES:
    start = today - timedelta(days=days_ago)
    db.add(models.Activity(
        customer_name=name, activity_type=typ, status=status, contact=contact,
        location=loc, product_interested=product, notes=notes,
        start_date=start,
        end_date=start + timedelta(days=days_taken) if days_taken is not None else None,
        created_at=datetime.now() - timedelta(days=days_ago),
    ))
db.commit()
db.close()
print("Added", len(SAMPLES), "demo activities")