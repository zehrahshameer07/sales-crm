"""Small validation helpers shared by the schemas."""
import re
from typing import Any

PHONE_PATTERN = re.compile(r"^[0-9+\-\s()]{7,20}$")


def blank_to_none(value: Any) -> Any:
    """Treat empty form fields as 'not provided'."""
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def clean_name(value: str) -> str:
    """Trim and collapse repeated spaces."""
    return " ".join(value.split())


def check_phone(value):
    if value is not None and not PHONE_PATTERN.match(value):
        raise ValueError("Enter a valid phone number (digits, +, -, spaces, brackets).")
    return value
