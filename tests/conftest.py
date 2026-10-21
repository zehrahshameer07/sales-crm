"""Test setup. Each test gets an empty database and four ready-made logged-in clients."""
import os
import tempfile
from pathlib import Path

# Settings must be in place BEFORE the app is imported
os.environ["APP_ENV"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-test-secret-key-0123456789"
os.environ["ARGON2_TIME_COST"] = "1"      # fast hashing for tests only
os.environ["ARGON2_MEMORY_KIB"] = "8"
os.environ["AUTO_MIGRATE"] = "false"
os.environ["SEED_DEMO"] = "false"
os.environ["ADMIN_EMAIL"] = ""
os.environ["ADMIN_PASSWORD"] = ""
_tmp = Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL") or f"sqlite:///{_tmp}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402,F401
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.enums import UserRole  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.security import hash_password, reset_all_limiters  # noqa: E402

PASSWORD = "Sup3r-Secret-99"


@pytest.fixture(autouse=True)
def fresh_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_all_limiters()
    yield


@pytest.fixture()
def db():
    with SessionLocal() as session:
        yield session


def make_user(db, name, role, manager=None, *, email=None, password=PASSWORD, **extra) -> User:
    user = User(
        full_name=name,
        email=email or f"{name.split()[0].lower()}@example.com",
        role=role,
        manager_id=manager.id if manager else None,
        password_hash=hash_password(password),
        **extra,
    )
    db.add(user)
    db.commit()
    return user


def client_for(user: User, password: str = PASSWORD) -> TestClient:
    client = TestClient(app)
    response = client.post("/api/auth/login", json={"email": user.email, "password": password})
    assert response.status_code == 200, response.text
    return client


@pytest.fixture()
def people(db):
    """admin; manager Maya with reps Ravi and Riya; manager Mohan with rep Rohan."""
    admin = make_user(db, "Alice Admin", UserRole.ADMIN)
    maya = make_user(db, "Maya Manager", UserRole.MANAGER, admin)
    mohan = make_user(db, "Mohan Manager", UserRole.MANAGER, admin)
    ravi = make_user(db, "Ravi Rep", UserRole.SALESPERSON, maya)
    riya = make_user(db, "Riya Rep", UserRole.SALESPERSON, maya)
    rohan = make_user(db, "Rohan Rep", UserRole.SALESPERSON, mohan)
    return dict(admin=admin, maya=maya, mohan=mohan, ravi=ravi, riya=riya, rohan=rohan)


@pytest.fixture()
def clients(people):
    return {key: client_for(person) for key, person in people.items()}


def activity_payload(name="Spice Garden", **overrides):
    payload = {"customer_name": name, "activity_type": "visit"}
    payload.update(overrides)
    return payload


def create_activity(client, name="Spice Garden", **overrides):
    response = client.post("/api/activities", json=activity_payload(name, **overrides))
    assert response.status_code == 201, response.text
    return response.json()
