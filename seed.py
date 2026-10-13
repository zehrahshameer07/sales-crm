"""Optional: fill the database with demo data.  Run: python seed.py"""
from app.demo_data import add_demo_activities

print("Added", add_demo_activities(), "demo activities")