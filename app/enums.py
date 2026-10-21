"""Fixed value sets. Used by the database (real enum types), the API and the tests."""
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    SALESPERSON = "salesperson"


class ActivityType(str, Enum):
    CALL = "call"
    VISIT = "visit"
    DEMO = "demo"
    FOLLOW_UP = "follow_up"


class ActivityStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class Product(str, Enum):
    FREEBEES_MENU = "freebees_menu"
    FREEBEES_PLAY = "freebees_play"
    BOTH = "both"


# Status can only move forward. Completed is final.
ALLOWED_STATUS_CHANGES = {
    ActivityStatus.PENDING: {ActivityStatus.IN_PROGRESS, ActivityStatus.COMPLETED},
    ActivityStatus.IN_PROGRESS: {ActivityStatus.COMPLETED},
    ActivityStatus.COMPLETED: set(),
}
