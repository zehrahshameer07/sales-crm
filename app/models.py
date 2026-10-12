"""Database table definition."""
from datetime import date, datetime

from sqlalchemy import Column, Date, DateTime, Integer, String, Text

from .database import Base


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String(120), nullable=False, index=True)  # customer / restaurant
    contact = Column(String(20), nullable=True)
    location = Column(String(120), nullable=True)
    product_interested = Column(String(30), nullable=True)
    activity_type = Column(String(30), nullable=False)
    status = Column(String(30), nullable=False, index=True)
    notes = Column(Text, nullable=True)
    start_date = Column(Date, default=date.today, nullable=False, index=True)  # when the work started
    end_date = Column(Date, nullable=True)                                      # when it was completed
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)  # when it was logged