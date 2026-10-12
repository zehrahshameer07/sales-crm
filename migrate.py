"""One-time upgrade for an EXISTING database (crm.db) created before start/end dates existed.

Run once:  python migrate.py
Safe to run again: it only adds what is missing.
Not needed if you delete crm.db and start fresh (the app recreates the table itself).
"""
from sqlalchemy import inspect, text

from app.database import engine

columns = {c["name"] for c in inspect(engine).get_columns("activities")}

with engine.begin() as conn:
    if "start_date" not in columns:
        conn.execute(text("ALTER TABLE activities ADD COLUMN start_date DATE"))
        # Old activities: use the day they were logged as their start date
        if engine.dialect.name == "sqlite":
            conn.execute(text("UPDATE activities SET start_date = DATE(created_at)"))
        else:
            conn.execute(text("UPDATE activities SET start_date = CAST(created_at AS DATE)"))
        print("Added start_date (filled from the day each activity was logged)")
    else:
        print("start_date already exists")

    if "end_date" not in columns:
        conn.execute(text("ALTER TABLE activities ADD COLUMN end_date DATE"))
        print("Added end_date (empty for old activities; set it with Edit)")
    else:
        print("end_date already exists")

print("Done.")